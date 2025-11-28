from django.contrib.gis.db import models
from django.contrib.gis.geos import Point


class FuelStation(models.Model):
    """
    Fuel station with geospatial location.
    Uses PointField for efficient spatial queries with PostGIS.
    """
    opis_id = models.IntegerField(db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.IntegerField(null=True, blank=True)
    retail_price = models.DecimalField(max_digits=6, decimal_places=5)

    # Spatial field - CRITICAL for performance
    # geography=True enables proper distance calculations in meters
    location = models.PointField(geography=True, srid=4326, null=True, blank=True)

    # Denormalized lat/lon for quick access without geo operations
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['state', 'retail_price']),
            models.Index(fields=['retail_price']),
        ]
        # Spatial index is automatically created for PointField

    def save(self, *args, **kwargs):
        # Sync Point with lat/lon
        if self.latitude and self.longitude and not self.location:
            self.location = Point(self.longitude, self.latitude, srid=4326)
        elif self.location and not self.latitude:
            self.longitude = self.location.x
            self.latitude = self.location.y
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state} (${self.retail_price})"
