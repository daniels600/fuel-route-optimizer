"""
Import fuel stations using LocationIQ geocoding API.

LocationIQ offers 10,000 free requests/day - 5x better than ORS!
Perfect for completing all 6,626 stations in ONE DAY.

Get free API key: https://locationiq.com/ (no credit card required)
"""

import csv
import json
import os
import time
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.db import transaction
from apps.stations.models import FuelStation
import requests


class Command(BaseCommand):
    help = 'Import fuel stations with LocationIQ geocoding (10,000 requests/day FREE)'

    # US states only
    US_STATES = {
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    }

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to CSV file')
        parser.add_argument(
            '--api-key',
            type=str,
            help='LocationIQ API key (or set LOCATIONIQ_API_KEY in .env)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Database batch size (default: 500)'
        )
        parser.add_argument(
            '--cache-file',
            type=str,
            default='locationiq_cache.json',
            help='Cache file path (default: locationiq_cache.json)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.1,
            help='Delay between requests in seconds (default: 0.1 = 10 req/sec)'
        )
        parser.add_argument(
            '--skip-geocoding',
            action='store_true',
            help='Skip geocoding (import without coordinates)'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        api_key = options['api_key'] or os.getenv('LOCATIONIQ_API_KEY')
        batch_size = options['batch_size']
        cache_file = options['cache_file']
        delay = options['delay']
        skip_geocoding = options['skip_geocoding']

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Fuel Station Import with LocationIQ'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')

        if not skip_geocoding:
            if not api_key:
                self.stderr.write(self.style.ERROR(
                    'LocationIQ API key required! Get free key at https://locationiq.com/'
                ))
                self.stderr.write('Set via --api-key or LOCATIONIQ_API_KEY environment variable')
                return

            self.stdout.write('✨ Using LocationIQ API (10,000 requests/day FREE)')
            self.stdout.write(f'📍 Processing at {1/delay:.0f} requests/second')
            self.stdout.write(f'⏱️  Est. time for 6,626 stations: {6626*delay/60:.1f} minutes')
            self.stdout.write('')

        # Step 1: Load and deduplicate
        self.stdout.write(self.style.WARNING('Step 1: Loading and deduplicating...'))
        unique_stations = self._load_and_deduplicate(csv_file)
        self.stdout.write(self.style.SUCCESS(f'✓ Loaded {len(unique_stations)} unique stations'))
        self.stdout.write('')

        # Step 2: Filter US only
        self.stdout.write(self.style.WARNING('Step 2: Filtering US stations...'))
        us_stations = self._filter_us_stations(unique_stations)
        self.stdout.write(self.style.SUCCESS(
            f'✓ Filtered to {len(us_stations)} US stations '
            f'(excluded {len(unique_stations) - len(us_stations)} non-US)'
        ))
        self.stdout.write('')

        # Step 3: Geocode
        if not skip_geocoding:
            self.stdout.write(self.style.WARNING('Step 3: Geocoding with LocationIQ...'))
            geocoded_stations = self._geocode_batch(us_stations, api_key, cache_file, delay)
            self.stdout.write('')
        else:
            self.stdout.write(self.style.WARNING('Step 3: Skipping geocoding'))
            geocoded_stations = us_stations
            self.stdout.write('')

        # Step 4: Import
        self.stdout.write(self.style.WARNING('Step 4: Importing to database...'))
        self._import_to_database(geocoded_stations, batch_size)
        self.stdout.write('')

        # Summary
        total = FuelStation.objects.count()
        with_coords = FuelStation.objects.filter(location__isnull=False).count()

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Import Complete!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f'Total stations imported: {total}')
        self.stdout.write(f'Stations with coordinates: {with_coords}')
        self.stdout.write(f'Stations without coordinates: {total - with_coords}')
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
                    continue

        return [item['data'] for item in seen_ids.values()]

    def _filter_us_stations(self, stations):
        """Filter to keep only US stations."""
        return [s for s in stations if s['state'].strip().upper() in self.US_STATES]

    def _geocode_batch(self, stations, api_key, cache_file, delay):
        """
        Geocode stations using LocationIQ API with caching.

        LocationIQ endpoint: https://us1.locationiq.com/v1/search
        Limit: 10,000 requests/day (free tier)
        """
        # Load cache
        cache = self._load_cache(cache_file)
        geocoded_count = 0
        failed_count = 0
        cached_count = 0

        total = len(stations)
        base_url = 'https://us1.locationiq.com/v1/search'

        for i, station in enumerate(stations, 1):
            # Create cache key
            cache_key = f"{station['address']}, {station['city']}, {station['state']}, USA"

            # Check cache
            if cache_key in cache:
                coords = cache[cache_key]
                if coords:
                    station['latitude'] = coords['lat']
                    station['longitude'] = coords['lon']
                    cached_count += 1
                else:
                    failed_count += 1
                continue

            # Geocode
            try:
                params = {
                    'key': api_key,
                    'q': cache_key,
                    'format': 'json',
                    'limit': 1,
                    'addressdetails': 0
                }

                response = requests.get(base_url, params=params, timeout=10)

                if response.status_code == 200:
                    results = response.json()
                    if results and len(results) > 0:
                        lat = float(results[0]['lat'])
                        lon = float(results[0]['lon'])

                        station['latitude'] = lat
                        station['longitude'] = lon
                        cache[cache_key] = {'lat': lat, 'lon': lon}
                        geocoded_count += 1
                    else:
                        cache[cache_key] = None
                        failed_count += 1
                else:
                    # API error (quota exceeded, etc.)
                    self.stderr.write(
                        f'API error {response.status_code} for {station["name"]}: '
                        f'{response.text[:100]}'
                    )
                    cache[cache_key] = None
                    failed_count += 1

            except Exception as e:
                self.stderr.write(f'Error geocoding {station["name"]}: {str(e)[:100]}')
                cache[cache_key] = None
                failed_count += 1

            # Progress update
            if i % 100 == 0 or i == total:
                self.stdout.write(
                    f'  Progress: {i}/{total} '
                    f'(Geocoded: {geocoded_count}, Cached: {cached_count}, Failed: {failed_count})'
                )
                self._save_cache(cache, cache_file)

            # Rate limiting
            if geocoded_count > 0:
                time.sleep(delay)

        # Final cache save
        self._save_cache(cache, cache_file)

        self.stdout.write(self.style.SUCCESS(
            f'✓ Geocoded {geocoded_count} new stations '
            f'(+{cached_count} from cache, {failed_count} failed)'
        ))

        return stations

    def _load_cache(self, cache_file):
        """Load geocoding cache from JSON file."""
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self, cache, cache_file):
        """Save geocoding cache to JSON file."""
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            self.stderr.write(f'Warning: Could not save cache: {e}')

    def _import_to_database(self, stations, batch_size):
        """Import stations to database with bulk create."""
        # Clear existing
        deleted_count = FuelStation.objects.count()
        FuelStation.objects.all().delete()
        self.stdout.write(f'Cleared {deleted_count} existing stations')

        # Create objects
        stations_to_create = []

        for station in stations:
            location = None
            if 'latitude' in station and 'longitude' in station:
                location = Point(station['longitude'], station['latitude'], srid=4326)

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
