from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock


class RouteAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('optimize-route')

    @patch('apps.routing.views.RouteService')
    @patch('apps.routing.views.FuelOptimizer')
    def test_optimize_route_success(self, mock_optimizer, mock_route_service):
        """Test successful route optimization."""
        # Mock route service
        mock_rs_instance = MagicMock()
        mock_rs_instance.geocode_location.side_effect = [
            (-95.0, 30.0),  # start
            (-100.0, 35.0),  # end
        ]
        mock_rs_instance.get_route.return_value = {
            'coordinates': [[-95.0, 30.0], [-100.0, 35.0]],
            'distance_miles': 600,
            'duration_seconds': 36000,
            'geometry': {'type': 'LineString', 'coordinates': []},
        }
        mock_route_service.return_value = mock_rs_instance

        # Mock optimizer
        mock_opt_instance = MagicMock()
        mock_opt_instance.find_optimal_stops.return_value = {
            'fuel_stops': [],
            'summary': {
                'total_distance_miles': 600,
                'total_fuel_gallons': 60,
                'total_fuel_cost': 180.0,
                'number_of_stops': 2,
            }
        }
        mock_optimizer.return_value = mock_opt_instance

        response = self.client.post(self.url, {
            'start': 'Houston, TX',
            'end': 'Dallas, TX'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('route', response.data)
        self.assertIn('fuel_stops', response.data)
        self.assertIn('summary', response.data)

    def test_optimize_route_missing_params(self):
        """Test validation for missing parameters."""
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
