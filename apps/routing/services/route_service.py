import openrouteservice
from openrouteservice import convert
from django.conf import settings
from django.core.cache import cache
from typing import Tuple, List, Dict, Any
import hashlib


class RouteService:
    """
    Handles all interactions with OpenRouteService API.
    Goal: Minimize API calls (ideally 1 per request).
    """

    def __init__(self):
        self.client = openrouteservice.Client(key=settings.ORS_API_KEY)

    def get_route(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float],
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get route between two points.

        Args:
            start_coords: (longitude, latitude) - NOTE: ORS uses lon,lat order
            end_coords: (longitude, latitude)
            use_cache: Whether to cache results

        Returns:
            Dict with route geometry, distance, duration
        """
        # Cache key based on coordinates
        cache_key = self._make_cache_key(start_coords, end_coords)

        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        # Single API call to get full route
        coords = [start_coords, end_coords]

        route_response = self.client.directions(
            coordinates=coords,
            profile='driving-car',
            format='geojson',
            instructions=False,  # We don't need turn-by-turn
            geometry=True,
            radiuses=[-1, -1],  # No snapping radius limit
        )

        # Extract route data
        route_feature = route_response['features'][0]
        geometry = route_feature['geometry']
        properties = route_feature['properties']

        # Get route summary
        summary = properties['summary']

        result = {
            'geometry': geometry,  # GeoJSON LineString
            'coordinates': geometry['coordinates'],  # List of [lon, lat] points
            'distance_meters': summary['distance'],
            'distance_miles': summary['distance'] * 0.000621371,
            'duration_seconds': summary['duration'],
            'bbox': route_response.get('bbox'),
        }

        if use_cache:
            cache.set(cache_key, result, timeout=86400)  # Cache 24 hours

        return result

    def geocode_location(self, address: str) -> Tuple[float, float]:
        """
        Geocode an address to coordinates.

        Returns:
            (longitude, latitude) tuple
        """
        cache_key = f"geocode:{hashlib.md5(address.encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        result = self.client.pelias_search(text=address, size=1)

        if not result.get('features'):
            raise ValueError(f"Could not geocode address: {address}")

        coords = result['features'][0]['geometry']['coordinates']
        result_tuple = (coords[0], coords[1])  # (lon, lat)

        cache.set(cache_key, result_tuple, timeout=86400 * 30)  # Cache 30 days
        return result_tuple

    def _make_cache_key(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float]
    ) -> str:
        """Create deterministic cache key for route."""
        key_str = f"{start[0]:.5f},{start[1]:.5f}-{end[0]:.5f},{end[1]:.5f}"
        return f"route:{hashlib.md5(key_str.encode()).hexdigest()}"
