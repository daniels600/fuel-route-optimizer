from typing import List, Dict, Any, Tuple
from decimal import Decimal
from django.contrib.gis.geos import Point, LineString
from django.contrib.gis.measure import D  # Distance
from django.contrib.gis.db.models.functions import Distance
from apps.stations.models import FuelStation
from django.conf import settings
import math


class FuelOptimizer:
    """
    Implements the fixed-path gas station problem optimization.

    Algorithm Overview:
    1. Find all stations within buffer distance of route
    2. Project stations onto route to get mile markers
    3. Use greedy look-ahead to select cheapest reachable stations

    Key insight from research: For a fixed path, optimal strategy is:
    - If current station is cheaper than next, fill up completely
    - If current station is more expensive, fill only enough to reach next

    Reference: "To Fill or not to Fill: The Gas Station Problem" (Khuller et al.)
    """

    def __init__(
        self,
        max_range_miles: float = None,
        mpg: float = None,
        buffer_miles: float = None
    ):
        self.max_range = max_range_miles or settings.VEHICLE_MAX_RANGE_MILES
        self.mpg = mpg or settings.VEHICLE_MPG
        self.buffer_miles = buffer_miles or settings.ROUTE_BUFFER_MILES
        self.tank_capacity_gallons = self.max_range / self.mpg

    def find_optimal_stops(
        self,
        route_coords: List[List[float]],
        total_distance_miles: float
    ) -> Dict[str, Any]:
        """
        Find optimal fuel stops along a route.

        Args:
            route_coords: List of [lon, lat] coordinates from route geometry
            total_distance_miles: Total route distance

        Returns:
            Dict with fuel_stops list, total_cost, and summary
        """
        # Step 1: Create LineString from route
        route_line = LineString(route_coords, srid=4326)

        # Step 2: Find all stations near route using ST_DWithin (fast!)
        # Convert miles to meters for geography query
        buffer_meters = self.buffer_miles * 1609.34

        nearby_stations = FuelStation.objects.filter(
            location__dwithin=(route_line, D(m=buffer_meters))
        ).annotate(
            distance_to_route=Distance('location', route_line)
        ).order_by('retail_price')

        if not nearby_stations.exists():
            return self._no_stations_result(total_distance_miles)

        # Step 3: Calculate mile markers for each station
        stations_with_markers = self._calculate_mile_markers(
            nearby_stations, route_coords, total_distance_miles
        )

        # Step 4: Run optimization algorithm
        fuel_stops = self._optimize_stops(
            stations_with_markers, total_distance_miles
        )

        # Step 5: Calculate costs
        return self._calculate_results(fuel_stops, total_distance_miles)

    def _calculate_mile_markers(
        self,
        stations,
        route_coords: List[List[float]],
        total_distance: float
    ) -> List[Dict[str, Any]]:
        """
        Calculate the mile marker (distance along route) for each station.
        Uses projection onto route line.
        """
        route_line = LineString(route_coords, srid=4326)
        results = []

        for station in stations:
            if not station.location:
                continue

            # Project station onto route
            # locate_point returns fraction along line (0-1)
            fraction = route_line.project_normalized(station.location)
            mile_marker = fraction * total_distance

            results.append({
                'station': station,
                'mile_marker': mile_marker,
                'price': float(station.retail_price),
                'distance_to_route_miles': station.distance_to_route.mi if station.distance_to_route else 0,
            })

        # Sort by mile marker
        results.sort(key=lambda x: x['mile_marker'])
        return results

    def _optimize_stops(
        self,
        stations: List[Dict[str, Any]],
        total_distance: float
    ) -> List[Dict[str, Any]]:
        """
        Greedy optimization algorithm with look-ahead.

        Strategy:
        1. Start with full tank (or find first station if trip > max_range)
        2. At each decision point, look ahead within remaining range
        3. If cheaper station exists ahead and reachable, get just enough fuel to reach it
        4. If current is cheapest within range, fill up completely
        """
        stops = []
        current_position = 0.0
        current_fuel_gallons = self.tank_capacity_gallons  # Start full

        # If total distance > max range, we need at least one stop
        if total_distance <= self.max_range:
            # Can complete trip without stopping
            gallons_needed = total_distance / self.mpg
            return [{
                'type': 'no_stop_needed',
                'total_gallons': gallons_needed,
                'start_fuel': self.tank_capacity_gallons,
            }]

        while current_position < total_distance:
            remaining_distance = total_distance - current_position
            current_range = current_fuel_gallons * self.mpg

            # Can we reach the end?
            if current_range >= remaining_distance:
                break

            # Find reachable stations
            max_reachable_position = current_position + current_range

            reachable = [
                s for s in stations
                if current_position < s['mile_marker'] <= max_reachable_position
            ]

            if not reachable:
                # No stations in range - this is a problem
                # Find the closest station ahead even if out of range
                ahead = [s for s in stations if s['mile_marker'] > current_position]
                if ahead:
                    # Take closest - user may need to find intermediate fuel
                    reachable = [min(ahead, key=lambda x: x['mile_marker'])]
                else:
                    break  # No stations ahead at all

            # Find cheapest reachable station
            # But also consider: is there a cheaper station just beyond our range?
            cheapest_reachable = min(reachable, key=lambda x: x['price'])

            # Look ahead: any cheaper stations within 2x range?
            look_ahead_position = current_position + (self.max_range * 2)
            future_stations = [
                s for s in stations
                if max_reachable_position < s['mile_marker'] <= look_ahead_position
            ]

            cheaper_future = [
                s for s in future_stations
                if s['price'] < cheapest_reachable['price']
            ]

            if cheaper_future:
                # There's a cheaper station ahead
                # Fill just enough to reach the cheapest reachable, then reassess
                target = cheapest_reachable
                distance_to_target = target['mile_marker'] - current_position
                fuel_needed = distance_to_target / self.mpg
                gallons_to_buy = max(0, fuel_needed - current_fuel_gallons + 5)  # +5 gallon buffer
            else:
                # Current cheapest is the best option - fill up
                target = cheapest_reachable
                distance_to_target = target['mile_marker'] - current_position
                fuel_needed = distance_to_target / self.mpg
                gallons_to_buy = self.tank_capacity_gallons - (current_fuel_gallons - fuel_needed)

            # Record the stop
            fuel_used_to_reach = (target['mile_marker'] - current_position) / self.mpg

            stops.append({
                'station': target['station'],
                'mile_marker': target['mile_marker'],
                'price_per_gallon': target['price'],
                'gallons_purchased': round(gallons_to_buy, 2),
                'cost': round(gallons_to_buy * target['price'], 2),
                'distance_from_route_miles': target['distance_to_route_miles'],
            })

            # Update state
            current_position = target['mile_marker']
            current_fuel_gallons = current_fuel_gallons - fuel_used_to_reach + gallons_to_buy

        return stops

    def _calculate_results(
        self,
        stops: List[Dict[str, Any]],
        total_distance: float
    ) -> Dict[str, Any]:
        """Calculate final results with costs."""

        total_gallons = total_distance / self.mpg

        if stops and stops[0].get('type') == 'no_stop_needed':
            # No stops needed
            return {
                'fuel_stops': [],
                'summary': {
                    'total_distance_miles': round(total_distance, 2),
                    'total_fuel_gallons': round(total_gallons, 2),
                    'total_fuel_cost': None,  # Unknown - depends on where they fueled
                    'number_of_stops': 0,
                    'message': 'Trip can be completed without fueling'
                }
            }

        total_cost = sum(s['cost'] for s in stops)

        formatted_stops = []
        for stop in stops:
            station = stop['station']
            formatted_stops.append({
                'station_name': station.name,
                'address': station.address,
                'city': station.city,
                'state': station.state,
                'latitude': station.latitude,
                'longitude': station.longitude,
                'mile_marker': round(stop['mile_marker'], 1),
                'price_per_gallon': stop['price_per_gallon'],
                'gallons_to_purchase': stop['gallons_purchased'],
                'estimated_cost': stop['cost'],
                'distance_from_route_miles': round(stop['distance_from_route_miles'], 1),
            })

        return {
            'fuel_stops': formatted_stops,
            'summary': {
                'total_distance_miles': round(total_distance, 2),
                'total_fuel_gallons': round(total_gallons, 2),
                'total_fuel_cost': round(total_cost, 2),
                'number_of_stops': len(formatted_stops),
                'average_price_per_gallon': round(
                    total_cost / sum(s['gallons_purchased'] for s in stops), 3
                ) if stops else None,
            }
        }

    def _no_stations_result(self, total_distance: float) -> Dict[str, Any]:
        """Return result when no stations found near route."""
        return {
            'fuel_stops': [],
            'summary': {
                'total_distance_miles': round(total_distance, 2),
                'total_fuel_gallons': round(total_distance / self.mpg, 2),
                'total_fuel_cost': None,
                'number_of_stops': 0,
                'message': 'No fuel stations found within buffer distance of route'
            },
            'error': 'No fuel stations found along route'
        }
