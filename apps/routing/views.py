from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema
from .serializers import RouteRequestSerializer, RouteResponseSerializer
from .services.route_service import RouteService
from .services.fuel_optimizer import FuelOptimizer


class OptimizeRouteView(APIView):
    """
    V1: Optimize fuel stops using OpenRouteService (cloud-based).

    This implementation uses OpenRouteService cloud API for routing.
    Good for development and demos with 2,000 requests/day free tier.

    Given start and end locations, returns:
    - Route geometry (for map display)
    - Optimal fuel stops with prices and quantities
    - Total fuel cost estimate
    """

    @extend_schema(
        request=RouteRequestSerializer,
        responses={200: RouteResponseSerializer},
        description="Calculate optimal fuel stops using OpenRouteService (V1 - Cloud)"
    )
    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            route_service = RouteService()
            optimizer = FuelOptimizer(
                max_range_miles=data.get('max_range_miles'),
                mpg=data.get('mpg')
            )

            start_coords = route_service.geocode_location(data['start'])
            end_coords = route_service.geocode_location(data['end'])

            route = route_service.get_route(start_coords, end_coords)

            optimization_result = optimizer.find_optimal_stops(
                route_coords=route['coordinates'],
                total_distance_miles=route['distance_miles']
            )

            response_data = {
                'route': {
                    'start': data['start'],
                    'end': data['end'],
                    'start_coordinates': {
                        'longitude': start_coords[0],
                        'latitude': start_coords[1]
                    },
                    'end_coordinates': {
                        'longitude': end_coords[0],
                        'latitude': end_coords[1]
                    },
                    'distance_miles': route['distance_miles'],
                    'duration_hours': round(route['duration_seconds'] / 3600, 2),
                    'geometry': route['geometry'],
                },
                'fuel_stops': optimization_result['fuel_stops'],
                'summary': optimization_result['summary'],
                'routing_engine': 'OpenRouteService (v1)',
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Route calculation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthCheckView(APIView):
    """V1 health check endpoint."""

    def get(self, request):
        return Response({
            'status': 'healthy',
            'version': 'v1',
            'routing_engine': 'OpenRouteService'
        })
