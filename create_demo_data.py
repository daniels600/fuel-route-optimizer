"""
Create a small demo dataset with manually geocoded stations.
This gives you a working demo in 5 minutes instead of days of API calls.
"""

import csv

# Hand-picked fuel stations along major routes with known coordinates
# Format: OPIS ID, Name, Address, City, State, Rack ID, Price, Latitude, Longitude

DEMO_STATIONS = [
    # California I-5 corridor (LA to SF)
    (7001, "PILOT TRAVEL CENTER", "I-5 Exit 257", "Buttonwillow", "CA", 900, 3.899, 35.4012, -119.4692),
    (7002, "LOVES TRAVEL STOP", "I-5 Exit 403", "Coalinga", "CA", 900, 3.799, 36.1397, -120.3604),
    (7003, "TA TRAVEL CENTER", "I-5 Exit 403", "Firebaugh", "CA", 900, 3.949, 36.8511, -120.4552),
    (7004, "FLYING J", "I-5 Exit 472", "Tracy", "CA", 900, 3.849, 37.7397, -121.4252),
    (7005, "PILOT TRAVEL CENTER", "I-5 Exit 516", "Lodi", "CA", 900, 3.899, 38.1341, -121.3044),

    # Texas I-10 corridor (Houston to San Antonio)
    (8001, "BUCCEES", "I-10 Exit 695", "Baytown", "TX", 595, 2.899, 29.7355, -94.9774),
    (8002, "LOVES TRAVEL STOP", "I-10 Exit 618", "Columbus", "TX", 595, 2.799, 29.7066, -96.5397),
    (8003, "PILOT TRAVEL CENTER", "I-10 Exit 576", "San Antonio", "TX", 595, 2.849, 29.4241, -98.4936),
    (8004, "TA TRAVEL CENTER", "I-10 Exit 543", "Seguin", "TX", 595, 2.899, 29.5688, -97.9650),

    # I-95 corridor (Florida)
    (9001, "PILOT TRAVEL CENTER", "I-95 Exit 260", "Daytona Beach", "FL", 75, 3.459, 29.2108, -81.0228),
    (9002, "LOVES TRAVEL STOP", "I-95 Exit 195", "Fort Pierce", "FL", 75, 3.399, 27.4467, -80.3256),
    (9003, "TA TRAVEL CENTER", "I-95 Exit 87", "Fort Lauderdale", "FL", 75, 3.549, 26.1224, -80.1373),

    # I-40 corridor (cross-country)
    (10001, "PILOT TRAVEL CENTER", "I-40 Exit 286", "Amarillo", "TX", 595, 2.999, 35.2220, -101.8313),
    (10002, "LOVES TRAVEL STOP", "I-40 Exit 153", "Albuquerque", "NM", 810, 3.299, 35.0844, -106.6504),
    (10003, "FLYING J", "I-40 Exit 26", "Flagstaff", "AZ", 930, 3.699, 35.1983, -111.6513),
    (10004, "TA TRAVEL CENTER", "I-40 Exit 44", "Williams", "AZ", 930, 3.649, 35.2495, -112.1910),

    # I-80 corridor (cross-country)
    (11001, "PILOT TRAVEL CENTER", "I-80 Exit 173", "Laramie", "WY", 822, 3.449, 41.3114, -105.5911),
    (11002, "LOVES TRAVEL STOP", "I-80 Exit 401", "Salt Lake City", "UT", 815, 3.549, 40.7608, -111.8910),
    (11003, "FLYING J", "I-80 Exit 173", "Elko", "NV", 820, 3.899, 40.8324, -115.7631),
    (11004, "TA TRAVEL CENTER", "I-80 Exit 78", "Reno", "NV", 820, 3.999, 39.5296, -119.8138),

    # Additional coverage
    (12001, "PILOT TRAVEL CENTER", "I-10 Exit 200", "Phoenix", "AZ", 930, 3.599, 33.4484, -112.0740),
    (12002, "LOVES TRAVEL STOP", "I-15 Exit 291", "Las Vegas", "NV", 820, 3.899, 36.1699, -115.1398),
    (12003, "FLYING J", "I-5 Exit 716", "Seattle", "WA", 850, 4.199, 47.6062, -122.3321),
    (12004, "TA TRAVEL CENTER", "I-84 Exit 177", "Portland", "OR", 845, 3.999, 45.5152, -122.6784),
]

def create_demo_csv():
    """Create demo CSV with geocoded stations."""

    output_file = 'fuel_prices_demo_geocoded.csv'

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow([
            'OPIS Truckstop ID',
            'Truckstop Name',
            'Address',
            'City',
            'State',
            'Rack ID',
            'Retail Price',
            'Latitude',
            'Longitude'
        ])

        # Write stations
        for station in DEMO_STATIONS:
            writer.writerow(station)

    print(f"✅ Created {output_file} with {len(DEMO_STATIONS)} stations")
    print(f"📊 Coverage: Major interstates (I-5, I-10, I-40, I-80, I-95)")
    print(f"🗺️  States: CA, TX, FL, AZ, NM, NV, WY, UT, WA, OR")
    print("\nTo import:")
    print(f"  python manage.py import_demo_data {output_file}")

if __name__ == '__main__':
    create_demo_csv()
