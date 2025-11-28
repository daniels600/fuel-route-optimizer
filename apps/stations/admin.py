from django.contrib.gis import admin
from .models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.GISModelAdmin):
    list_display = ['name', 'city', 'state', 'retail_price', 'latitude', 'longitude']
    list_filter = ['state', 'retail_price']
    search_fields = ['name', 'city', 'address']
    ordering = ['retail_price']
