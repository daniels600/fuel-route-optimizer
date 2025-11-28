"""
Import pre-geocoded demo data.
No API calls needed - coordinates already included!
"""

import csv
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.db import transaction
from apps.stations.models import FuelStation


class Command(BaseCommand):
    help = 'Import pre-geocoded demo data (NO API calls needed!)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to demo CSV file')

    def handle(self, *args, **options):
        csv_file = options['csv_file']

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Importing Pre-Geocoded Demo Data'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')
        self.stdout.write('✅ No API calls needed - coordinates included!')
        self.stdout.write('')

        # Clear existing
        deleted = FuelStation.objects.count()
        FuelStation.objects.all().delete()
        if deleted > 0:
            self.stdout.write(f'Cleared {deleted} existing stations')

        # Import
        stations_to_create = []

        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    lat = float(row['Latitude'])
                    lon = float(row['Longitude'])

                    station = FuelStation(
                        opis_id=int(row['OPIS Truckstop ID']),
                        name=row['Truckstop Name'],
                        address=row['Address'],
                        city=row['City'],
                        state=row['State'],
                        rack_id=int(row['Rack ID']) if row.get('Rack ID') else None,
                        retail_price=float(row['Retail Price']),
                        latitude=lat,
                        longitude=lon,
                        location=Point(lon, lat, srid=4326)
                    )
                    stations_to_create.append(station)

                except (ValueError, KeyError) as e:
                    self.stderr.write(f'Skipping invalid row: {e}')
                    continue

        # Bulk create
        with transaction.atomic():
            FuelStation.objects.bulk_create(stations_to_create)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Import Complete!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f'✅ Imported {len(stations_to_create)} stations')
        self.stdout.write(f'✅ All stations have coordinates')
        self.stdout.write(f'✅ Ready for demo!')
        self.stdout.write('')
        self.stdout.write('Test routes that work:')
        self.stdout.write('  • Los Angeles, CA → San Francisco, CA')
        self.stdout.write('  • Houston, TX → San Antonio, TX')
        self.stdout.write('  • Phoenix, AZ → Las Vegas, NV')
        self.stdout.write('')
