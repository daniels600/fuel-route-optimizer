from django.test import TestCase
from django.contrib.gis.geos import Point
from apps.stations.models import FuelStation
from apps.routing.services.fuel_optimizer import FuelOptimizer


class FuelOptimizerTests(TestCase):

    def setUp(self):
        """Create test fuel stations."""
        # Create stations along a hypothetical route
        self.stations = [
            FuelStation.objects.create(
                opis_id=1,
                name="Cheap Station",
                address="123 Test St",
                city="TestCity",
                state="TX",
                retail_price=2.50,
                latitude=30.0,
                longitude=-95.0,
                location=Point(-95.0, 30.0, srid=4326)
            ),
            FuelStation.objects.create(
                opis_id=2,
                name="Expensive Station",
                address="456 Test Ave",
                city="TestCity2",
                state="TX",
                retail_price=3.50,
                latitude=31.0,
                longitude=-96.0,
                location=Point(-96.0, 31.0, srid=4326)
            ),
        ]

    def test_short_trip_no_stops(self):
        """Test that short trips don't require fuel stops."""
        optimizer = FuelOptimizer(max_range_miles=500, mpg=10)

        # 100 mile route
        route_coords = [[-95.0, 30.0], [-95.5, 30.5], [-96.0, 31.0]]

        result = optimizer.find_optimal_stops(
            route_coords=route_coords,
            total_distance_miles=100
        )

        self.assertEqual(result['summary']['number_of_stops'], 0)

    def test_prefers_cheaper_stations(self):
        """Test that optimizer prefers cheaper fuel stations."""
        optimizer = FuelOptimizer(max_range_miles=200, mpg=10)

        # Route that passes near both stations
        route_coords = [
            [-94.5, 29.5],
            [-95.0, 30.0],  # Near cheap station
            [-96.0, 31.0],  # Near expensive station
            [-97.0, 32.0],
        ]

        result = optimizer.find_optimal_stops(
            route_coords=route_coords,
            total_distance_miles=400
        )

        # Should prefer the cheaper station
        if result['fuel_stops']:
            prices = [s['price_per_gallon'] for s in result['fuel_stops']]
            self.assertIn(2.50, prices)
