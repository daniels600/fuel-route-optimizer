from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    """Input serializer for route optimization request."""
    start = serializers.CharField(
        help_text="Start location (address or 'City, State')"
    )
    end = serializers.CharField(
        help_text="End location (address or 'City, State')"
    )

    # Optional overrides
    max_range_miles = serializers.FloatField(
        required=False,
        default=500,
        help_text="Vehicle maximum range in miles (default: 500)"
    )
    mpg = serializers.FloatField(
        required=False,
        default=10,
        help_text="Vehicle fuel efficiency in MPG (default: 10)"
    )


class FuelStopSerializer(serializers.Serializer):
    """Serializer for individual fuel stop."""
    station_name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    mile_marker = serializers.FloatField()
    price_per_gallon = serializers.FloatField()
    gallons_to_purchase = serializers.FloatField()
    estimated_cost = serializers.FloatField()
    distance_from_route_miles = serializers.FloatField()


class RouteSummarySerializer(serializers.Serializer):
    """Serializer for route summary."""
    total_distance_miles = serializers.FloatField()
    total_fuel_gallons = serializers.FloatField()
    total_fuel_cost = serializers.FloatField(allow_null=True)
    number_of_stops = serializers.IntegerField()
    average_price_per_gallon = serializers.FloatField(allow_null=True)
    message = serializers.CharField(required=False)


class RouteResponseSerializer(serializers.Serializer):
    """Output serializer for route optimization response."""
    route = serializers.DictField(
        help_text="Route geometry and metadata"
    )
    fuel_stops = FuelStopSerializer(many=True)
    summary = RouteSummarySerializer()
