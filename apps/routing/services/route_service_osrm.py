"""
Route service using self-hosted OSRM (Open Source Routing Machine).

OSRM provides unlimited routing with no API keys needed.
Run OSRM server with: docker-compose up osrm

Benefits:
- Unlimited requests
- No rate limits
- Fast response times
- Production-ready
"""

import requests
from django.conf import settings
from django.core.cache import cache
from typing import Tuple, List, Dict, Any
import hashlib
import polyline


class RouteServiceOSRM:
    """
    Handles routing with self-hosted OSRM server.
    No API keys needed - runs locally via Docker.
    """

    def __init__(self):
        # OSRM server URL (default: localhost:5000)
        self.base_url = getattr(settings, 'OSRM_BASE_URL', 'http://localhost:5000')

    def get_route(
        self,
        start_coords: Tuple[float, float],
        end_coords: Tuple[float, float],
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Get route between two points using OSRM.

        Args:
            start_coords: (longitude, latitude)
            end_coords: (longitude, latitude)
            use_cache: Whether to cache results

        Returns:
            Dict with route geometry, distance, duration
        """
        # Cache key
        cache_key = self._make_cache_key(start_coords, end_coords)

        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        # OSRM route endpoint
        # Format: /route/v1/driving/{lon},{lat};{lon},{lat}
        url = (
            f"{self.base_url}/route/v1/driving/"
            f"{start_coords[0]},{start_coords[1]};"
            f"{end_coords[0]},{end_coords[1]}"
        )

        params = {
            'overview': 'full',
            'geometries': 'polyline',  # or 'geojson'
            'steps': 'false'
        }

        response = requests.get(url, params=params, timeout=30)

        if response.status_code != 200:
            raise Exception(f"OSRM error: {response.status_code} - {response.text}")

        data = response.json()

        if data['code'] != 'Ok':
            raise Exception(f"OSRM routing failed: {data.get('message', 'Unknown error')}")

        # Extract route data
        route = data['routes'][0]

        # Decode polyline to coordinates
        coordinates = polyline.decode(route['geometry'])
        # Convert to [lon, lat] format
        coordinates = [[lon, lat] for lat, lon in coordinates]

        # Calculate bounding box
        lons = [coord[0] for coord in coordinates]
        lats = [coord[1] for coord in coordinates]
        bbox = [min(lons), min(lats), max(lons), max(lats)]

        result = {
            'geometry': {
                'type': 'LineString',
                'coordinates': coordinates
            },
            'coordinates': coordinates,
            'distance_meters': route['distance'],
            'distance_miles': route['distance'] * 0.000621371,
            'duration_seconds': route['duration'],
            'bbox': bbox,
        }

        if use_cache:
            cache.set(cache_key, result, timeout=86400)  # Cache 24 hours

        return result

    def geocode_location(self, address: str) -> Tuple[float, float]:
        """
        Geocode an address to coordinates using LocationIQ.

        LocationIQ provides 10,000 requests/day on the free tier.
        """
        api_key = getattr(settings, 'LOCATIONIQ_API_KEY', None)
        if not api_key:
            raise Exception("LOCATIONIQ_API_KEY not configured")

        url = "https://us1.locationiq.com/v1/search"

        params = {
            'key': api_key,
            'q': address,
            'format': 'json',
            'limit': 1
        }

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            raise Exception(f"Geocoding failed: {response.status_code}")

        results = response.json()

        if not results:
            raise Exception(f"Could not geocode address: {address}")

        lat = float(results[0]['lat'])
        lon = float(results[0]['lon'])

        return (lon, lat)

    def _make_cache_key(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> str:
        """Generate cache key from coordinates."""
        key_str = f"{start_coords[0]},{start_coords[1]}|{end_coords[0]},{end_coords[1]}"
        return f"route:osrm:{hashlib.md5(key_str.encode()).hexdigest()}"
