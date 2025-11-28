import csv
import json
import os
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.db import transaction
from apps.stations.models import FuelStation
import openrouteservice
from openrouteservice.geocode import pelias_search
from django.conf import settings
import time


class Command(BaseCommand):
    help = 'Import fuel stations from CSV with optimized batch geocoding and duplicate removal'

    # US states only (excluding Canadian provinces and territories)
    US_STATES = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    }

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file with fuel stations')
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Batch size for bulk insert (default: 500)'
        )
        parser.add_argument(
            '--skip-geocoding',
            action='store_true',
            help='Skip geocoding step (import only - stations will have no coordinates)'
        )
        parser.add_argument(
            '--cache-file',
            type=str,
            default='geocode_cache.json',
            help='Path to geocoding cache file (default: geocode_cache.json)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Delay between geocoding requests in seconds (default: 1.0)'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        batch_size = options['batch_size']
        skip_geocoding = options['skip_geocoding']
        cache_file = options['cache_file']
        delay = options['delay']

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Fuel Station Import with Batch Geocoding'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')

        # Step 1: Load and deduplicate CSV data
        self.stdout.write(self.style.WARNING('Step 1: Loading and deduplicating CSV data...'))
        unique_stations = self._load_and_deduplicate(csv_file)
        self.stdout.write(self.style.SUCCESS(f'✓ Loaded {len(unique_stations)} unique stations'))
        self.stdout.write('')

        # Step 2: Filter US stations only
        self.stdout.write(self.style.WARNING('Step 2: Filtering US stations only...'))
        us_stations = self._filter_us_stations(unique_stations)
        self.stdout.write(self.style.SUCCESS(
            f'✓ Filtered to {len(us_stations)} US stations '
            f'(excluded {len(unique_stations) - len(us_stations)} non-US)'
        ))
        self.stdout.write('')

        # Step 3: Geocode stations
        if not skip_geocoding:
            self.stdout.write(self.style.WARNING('Step 3: Geocoding stations...'))
            self.stdout.write(f'Using OpenRouteService Pelias with {delay}s delay between requests')
            self.stdout.write(f'Cache file: {cache_file}')
            self.stdout.write(f'Free tier limit: 2,000 requests/day (~3 hours at 1 req/sec)')
            geocoded_stations = self._geocode_batch(us_stations, cache_file, delay)
            self.stdout.write(self.style.SUCCESS(
                f'✓ Geocoded {len(geocoded_stations)} stations successfully'
            ))
            self.stdout.write('')
        else:
            self.stdout.write(self.style.WARNING('Step 3: Skipping geocoding (--skip-geocoding flag)'))
            geocoded_stations = us_stations
            self.stdout.write('')

        # Step 4: Clear existing data and import
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
        self.stdout.write('')

    def _load_and_deduplicate(self, csv_file):
        """
        Load CSV and remove duplicates, keeping lowest price per station.
        Returns dict: {opis_id: {price, row_data}}
        """
        seen_ids = {}

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    opis_id = int(row['OPIS Truckstop ID'])
                    price = Decimal(row['Retail Price'])

                    # Keep only lowest price per station (handles duplicates)
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

        # Extract just the data dicts
        return [item['data'] for item in seen_ids.values()]

    def _filter_us_stations(self, stations):
        """Filter to keep only US stations."""
        us_stations = []
        for station in stations:
            state = station['state'].strip().upper()
            if state in self.US_STATES:
                us_stations.append(station)
        return us_stations

    def _geocode_batch(self, stations, cache_file, delay):
        """
        Geocode stations using OpenRouteService Pelias with caching and resume capability.
        """
        # Load cache
        cache = self._load_cache(cache_file)
        geocoded_count = 0
        failed_count = 0
        cached_count = 0

        # Initialize ORS client
        try:
            client = openrouteservice.Client(key=settings.ORS_API_KEY)
        except Exception as e:
            self.stderr.write(f'Error initializing ORS client: {e}')
            self.stderr.write('Make sure ORS_API_KEY is set in .env file')
            return stations

        total = len(stations)

        for i, station in enumerate(stations, 1):
            # Create cache key
            cache_key = f"{station['address']}, {station['city']}, {station['state']}"

            # Check cache first
            if cache_key in cache:
                coords = cache[cache_key]
                if coords:  # coords could be None for failed geocodes
                    station['latitude'] = coords['lat']
                    station['longitude'] = coords['lon']
                    cached_count += 1
                else:
                    failed_count += 1
                continue

            # Geocode using ORS Pelias
            try:
                address_query = f"{station['address']}, {station['city']}, {station['state']}, USA"
                result = pelias_search(client, address_query, size=1)

                if result and result.get('features') and len(result['features']) > 0:
                    coords = result['features'][0]['geometry']['coordinates']
                    # ORS returns [lon, lat]
                    station['longitude'] = coords[0]
                    station['latitude'] = coords[1]
                    cache[cache_key] = {'lat': coords[1], 'lon': coords[0]}
                    geocoded_count += 1
                else:
                    # No result found
                    cache[cache_key] = None
                    failed_count += 1

            except Exception as e:
                self.stderr.write(f'Geocoding error for {station["name"]}: {str(e)[:100]}')
                cache[cache_key] = None
                failed_count += 1

            # Progress update
            if i % 50 == 0 or i == total:
                self.stdout.write(
                    f'  Progress: {i}/{total} '
                    f'(Geocoded: {geocoded_count}, Cached: {cached_count}, Failed: {failed_count})'
                )
                # Save cache periodically
                self._save_cache(cache, cache_file)

            # Rate limiting - ORS free tier allows 40 requests/minute
            # We'll use 1 req/sec to be safe
            if geocoded_count > 0:
                time.sleep(delay)

        # Final cache save
        self._save_cache(cache, cache_file)

        return stations

    def _load_cache(self, cache_file):
        """Load geocoding cache from JSON file."""
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.stderr.write(f'Warning: Could not load cache file {cache_file}')
                return {}
        return {}

    def _save_cache(self, cache, cache_file):
        """Save geocoding cache to JSON file."""
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            self.stderr.write(f'Warning: Could not save cache file: {e}')

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
