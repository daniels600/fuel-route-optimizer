"""
Geocode fuel stations using the US Census Bureau Geocoder API.

This is the BEST solution for bulk US address geocoding:
- FREE and UNLIMITED
- No API key required
- Batch processing (10,000 records at once)
- Optimized for US addresses
- Much faster than rate-limited APIs

Census API: https://geocoding.geo.census.gov/geocoder/
"""

import csv
import os
import time
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.db import transaction
from apps.stations.models import FuelStation
import requests


class Command(BaseCommand):
    help = 'Geocode fuel stations using US Census Bureau Geocoder (FREE, UNLIMITED)'

    # US states only
    US_STATES = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    }

    CENSUS_BATCH_URL = 'https://geocoding.geo.census.gov/geocoder/geographies/addressbatch'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file with fuel stations')
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Database batch size for bulk insert (default: 500)'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        batch_size = options['batch_size']

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Fuel Station Import with US Census Geocoder'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')
        self.stdout.write('✨ Using US Census Bureau API (FREE & UNLIMITED)')
        self.stdout.write('📍 Batch geocoding optimized for US addresses')
        self.stdout.write('')

        # Step 1: Load and deduplicate
        self.stdout.write(self.style.WARNING('Step 1: Loading and deduplicating CSV data...'))
        unique_stations = self._load_and_deduplicate(csv_file)
        self.stdout.write(self.style.SUCCESS(f'✓ Loaded {len(unique_stations)} unique stations'))
        self.stdout.write('')

        # Step 2: Filter US only
        self.stdout.write(self.style.WARNING('Step 2: Filtering US stations only...'))
        us_stations = self._filter_us_stations(unique_stations)
        self.stdout.write(self.style.SUCCESS(
            f'✓ Filtered to {len(us_stations)} US stations '
            f'(excluded {len(unique_stations) - len(us_stations)} non-US)'
        ))
        self.stdout.write('')

        # Step 3: Batch geocode with Census API
        self.stdout.write(self.style.WARNING('Step 3: Batch geocoding with US Census API...'))
        self.stdout.write(f'Processing {len(us_stations)} stations in one batch...')
        geocoded_stations = self._geocode_with_census(us_stations)
        self.stdout.write('')

        # Step 4: Import to database
        self.stdout.write(self.style.WARNING('Step 4: Importing to database...'))
        self._import_to_database(geocoded_stations, batch_size)
        self.stdout.write('')

        # Final summary
        total_imported = FuelStation.objects.count()
        with_coords = FuelStation.objects.filter(location__isnull=False).count()

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Import Complete!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f'Total stations imported: {total_imported}')
        self.stdout.write(f'Stations with coordinates: {with_coords}')
        self.stdout.write(f'Stations without coordinates: {total_imported - with_coords}')
        if with_coords < total_imported:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  {total_imported - with_coords} stations could not be geocoded '
                '(invalid/ambiguous addresses)'
            ))
        self.stdout.write('')

    def _load_and_deduplicate(self, csv_file):
        """Load CSV and remove duplicates, keeping lowest price."""
        seen_ids = {}

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    opis_id = int(row['OPIS Truckstop ID'])
                    price = Decimal(row['Retail Price'])

                    if opis_id not in seen_ids or price < seen_ids[opis_id]['price']:
                        seen_ids[opis_id] = {
                            'price': price,
                            'data': {
                                'opis_id': opis_id,
                                'name': row['Truckstop Name'].strip(),
                                'address': row['Address'].strip(),
                                'city': row['City'].strip(),
                                'state': row['State'].strip(),
                                'rack_id': int(row['Rack ID']) if row['Rack ID'] else None,
                                'retail_price': price,
                            }
                        }
                except (ValueError, KeyError) as e:
                    self.stderr.write(f'Skipping invalid row: {e}')
                    continue

        return [item['data'] for item in seen_ids.values()]

    def _filter_us_stations(self, stations):
        """Filter to keep only US stations."""
        return [s for s in stations if s['state'].strip().upper() in self.US_STATES]

    def _geocode_with_census(self, stations):
        """
        Geocode stations using US Census Bureau batch API.

        The Census API requires a specially formatted CSV:
        UniqueId, Street address, City, State, ZIP

        Returns the same stations list with added lat/lon coordinates.
        """
        # Create batch input file
        batch_input_file = 'census_geocode_input.csv'

        self.stdout.write(f'Creating batch file: {batch_input_file}')

        with open(batch_input_file, 'w', newline='', encoding='utf-8') as f:
            for idx, station in enumerate(stations):
                # Census format: ID, Street, City, State, ZIP (we don't have ZIP, leave empty)
                line = f"{idx},{station['address']},{station['city']},{station['state']},\n"
                f.write(line)

        self.stdout.write(f'✓ Created batch file with {len(stations)} addresses')
        self.stdout.write('Sending to US Census Geocoding API...')

        # Submit to Census API
        try:
            with open(batch_input_file, 'rb') as f:
                files = {'addressFile': (batch_input_file, f, 'text/csv')}
                data = {
                    'benchmark': 'Public_AR_Current',  # Current benchmark
                    'vintage': 'Current_Current',       # Current vintage
                }

                response = requests.post(
                    self.CENSUS_BATCH_URL,
                    files=files,
                    data=data,
                    timeout=300  # 5 minute timeout for large batches
                )

                if response.status_code != 200:
                    self.stderr.write(f'Census API error: {response.status_code}')
                    self.stderr.write(response.text[:500])
                    return stations

        except Exception as e:
            self.stderr.write(f'Error calling Census API: {e}')
            return stations

        # Parse response
        self.stdout.write('✓ Received response from Census API')
        self.stdout.write('Parsing geocoded coordinates...')

        # Debug: Save response to file
        debug_file = 'census_response_debug.csv'
        with open(debug_file, 'w') as f:
            f.write(response.text)
        self.stdout.write(f'Debug: Saved response to {debug_file}')

        geocoded_count = 0
        failed_count = 0

        # Census returns CSV: ID, Input Address, Match (Yes/No), Match Type, Output Address, Coordinates, ...
        # Format may vary, let's parse more carefully
        response_lines = response.text.strip().split('\n')

        self.stdout.write(f'Debug: Got {len(response_lines)} response lines')

        for line_num, line in enumerate(response_lines):
            if not line.strip():
                continue

            # Use CSV reader for proper parsing (handles quotes, commas in addresses)
            import csv as csv_module
            import io

            try:
                row = next(csv_module.reader(io.StringIO(line)))

                if len(row) < 3:
                    continue

                idx = int(row[0])
                match_status = row[2] if len(row) > 2 else 'No_Match'

                # Debug first few lines
                if line_num < 3:
                    self.stdout.write(f'Debug line {line_num}: match={match_status}, parts={len(row)}')

                if match_status == 'Match':
                    # Find lat/lon columns - they're usually near the end
                    # Format: ID, Input, Match, MatchType, MatchedAddress, Coords, Tiger/Line, Side, ...
                    # Coordinates are in format: "x,y" or separate columns

                    # Try to find coordinate columns (usually columns 5 and 6 or within a coordinate field)
                    if len(row) >= 7:
                        try:
                            # Try parsing as separate lon,lat columns
                            lon = float(row[5])
                            lat = float(row[6])

                            stations[idx]['longitude'] = lon
                            stations[idx]['latitude'] = lat
                            geocoded_count += 1
                        except (ValueError, IndexError):
                            # Coordinates might be in a different format
                            failed_count += 1
                else:
                    # No match found
                    failed_count += 1

            except (ValueError, IndexError) as e:
                self.stderr.write(f'Error parsing line {line_num}: {e}')
                failed_count += 1
                continue

        self.stdout.write(self.style.SUCCESS(
            f'✓ Geocoded {geocoded_count} stations successfully'
        ))
        if failed_count > 0:
            self.stdout.write(self.style.WARNING(
                f'⚠️  {failed_count} stations could not be geocoded'
            ))

        # Cleanup
        try:
            os.remove(batch_input_file)
        except:
            pass

        return stations

    def _import_to_database(self, stations, batch_size):
        """Import stations to database with bulk create."""
        # Clear existing data
        deleted_count = FuelStation.objects.count()
        FuelStation.objects.all().delete()
        self.stdout.write(f'Cleared {deleted_count} existing stations')

        # Create FuelStation objects
        stations_to_create = []

        for station in stations:
            # Create Point if we have coordinates
            location = None
            if 'latitude' in station and 'longitude' in station:
                location = Point(
                    station['longitude'],
                    station['latitude'],
                    srid=4326
                )

            fuel_station = FuelStation(
                opis_id=station['opis_id'],
                name=station['name'],
                address=station['address'],
                city=station['city'],
                state=station['state'],
                rack_id=station.get('rack_id'),
                retail_price=station['retail_price'],
                latitude=station.get('latitude'),
                longitude=station.get('longitude'),
                location=location,
            )
            stations_to_create.append(fuel_station)

        # Bulk create in batches
        total_created = 0
        for i in range(0, len(stations_to_create), batch_size):
            batch = stations_to_create[i:i + batch_size]
            with transaction.atomic():
                FuelStation.objects.bulk_create(batch, batch_size=batch_size)
            total_created += len(batch)
            self.stdout.write(f'  Imported {total_created}/{len(stations_to_create)} stations')

        self.stdout.write(self.style.SUCCESS(f'✓ Successfully imported {total_created} stations'))
