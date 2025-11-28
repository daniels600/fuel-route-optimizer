# Fuel Route Optimizer API

A Django REST API that calculates fuel-optimized routes with **two distinct implementations**: cloud-based (V1) and self-hosted (V2). Given start and end locations, the API returns optimal fuel stops along a route based on price, considering vehicle range and fuel efficiency.

## ⚡ Quick Start (One Command)

```bash
./quickstart.sh
```

This automated script will:
- ✅ Check prerequisites (Python, Docker, GDAL)
- ✅ Setup virtual environment
- ✅ Start PostgreSQL + OSRM
- ✅ Download & process California map data
- ✅ Run migrations
- ✅ Import 10 pre-geocoded I-5 demo stations
- ✅ Start Django server

**Time**: ~10 minutes (includes map download and processing)

---

## 🎯 Features

- **Two Routing Implementations**: Cloud API (V1) or self-hosted OSRM (V2)
- **Fuel-Optimized Routes**: Finds cheapest fuel stops along your route
- **PostGIS Spatial Queries**: Fast geospatial operations with GIST indexing
- **Smart Optimization**: Greedy look-ahead algorithm for minimal fuel costs
- **Intelligent Caching**: Routes (24h) and geocoding (30 days) cached
- **RESTful API**: Clean, well-documented endpoints with OpenAPI/Swagger
- **No Geocoding Delays**: Demo data pre-geocoded (no API calls needed)

---

## 🚀 V1 vs V2 Architecture

### Separate Endpoints (No Environment Variable Switching!)

| Version | Endpoint | Routing | Geocoding | Rate Limits |
|---------|----------|---------|-----------|-------------|
| **V1** | `/api/v1/route/optimize/` | OpenRouteService (cloud) | ORS Pelias | 2,000/day |
| **V2** | `/api/v2/route/optimize/` | OSRM (self-hosted) | LocationIQ | Routing: Unlimited, Geocoding: 10,000/day |

### Comparison

| Feature | V1 (Cloud) | V2 (Self-hosted) |
|---------|-----------|------------------|
| **Setup Time** | 5 minutes | 10 minutes (with quickstart.sh) |
| **API Keys** | ORS (required) | LocationIQ (required for geocoding) |
| **Routing Limits** | 2,000/day | ✅ Unlimited |
| **Response Time** | ~500-800ms | ~100-200ms (local) |
| **Disk Space** | Minimal | ~2GB (California data) |
| **Infrastructure** | None | Docker (PostgreSQL + OSRM) |
| **Best For** | Demos, development, low-volume | Production, high-volume |

**Key Difference**: Both endpoints query the **same PostgreSQL database** for fuel stations. Only routing/geocoding methods differ.

---

## 📦 Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Framework** | Django + Django REST Framework | 5.1 |
| **Database** | PostgreSQL + PostGIS | 16 + 3.4 |
| **Routing (V1)** | OpenRouteService API | Cloud |
| **Routing (V2)** | OSRM (self-hosted) | Latest |
| **Geocoding (V1)** | ORS Pelias | Cloud |
| **Geocoding (V2)** | LocationIQ | Cloud (10k/day) |
| **Spatial Library** | GeoDjango + PostGIS | - |
| **Containerization** | Docker Compose | - |

---

## 📁 Project Structure

```
spotter-project/
├── README.md
├── V1_VS_V2_ARCHITECTURE.md        # Flow diagrams
├── TEST_DATA.md                     # Test scenarios
├── QUICK_TEST_COMMANDS.md          # Copy & paste tests
├── CLEANUP_SUMMARY.md              # What was cleaned up
├── quickstart.sh                    # One-command setup
├── manage.py
│
├── apps/
│   ├── routing/
│   │   ├── views.py                # V1 endpoint
│   │   ├── views_v2.py             # V2 endpoint
│   │   ├── urls.py                 # V1 URL routing
│   │   ├── urls_v2.py              # V2 URL routing
│   │   ├── serializers.py          # Shared serializers
│   │   └── services/
│   │       ├── route_service.py           # V1: OpenRouteService
│   │       ├── route_service_osrm.py      # V2: OSRM + LocationIQ
│   │       └── fuel_optimizer.py          # Shared: Database queries
│   │
│   └── stations/
│       ├── models.py               # FuelStation (shared by V1 & V2)
│       └── management/commands/
│           └── import_demo_data.py # Import CSV to database
│
├── config/
│   ├── settings/base.py           # Caching, API keys
│   └── urls.py                    # Main routing (V1 + V2)
│
├── docs/
│   ├── SETUP_MACOS.md
│   ├── ERRORS_FIXED.md
│   └── LIMITATIONS_AND_CHALLENGES.md
│
├── fuel_prices_demo_geocoded.csv  # 10 I-5 stations (used by both V1 & V2)
├── requirements.txt
├── docker-compose.yml              # PostgreSQL + OSRM
└── .env                            # API keys
```

---

## 🛠️ Manual Setup (Alternative to quickstart.sh)

### Prerequisites

- **Python 3.10+**
- **Docker & Docker Compose**
- **GDAL** (macOS: `brew install gdal`)
- **Git**

### Step-by-Step

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start PostgreSQL + OSRM
docker-compose up -d

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys:
#   ORS_API_KEY=your-key (for V1)
#   LOCATIONIQ_API_KEY=your-key (for V2 geocoding)
#   OSRM_BASE_URL=http://localhost:5001

# 5. Run migrations
python manage.py migrate

# 6. Import demo data
python manage.py import_demo_data fuel_prices_demo_geocoded.csv

# 7. Start server
python manage.py runserver
```

Visit: **http://localhost:8000/api/docs/**

---

## 🎯 Demo Data

### 10 Pre-Geocoded Fuel Stations (I-5 Corridor)

All stations are on Interstate 5 between Los Angeles and San Francisco:

1. **TA Travel Center - Lebec** - $4.299/gal
2. **Pilot Travel Center - Grapevine** - $4.349/gal
3. **Loves Travel Stop - Buttonwillow** - $4.199/gal ⭐ Cheapest
4. **Flying J - Lost Hills** - $4.249/gal
5. **Pilot Travel Center - Coalinga** - $4.399/gal
6. **TA Travel Center - Firebaugh** - $4.299/gal
7. **Loves Travel Stop - Santa Nella** - $4.449/gal
8. **Flying J - Patterson** - $4.349/gal
9. **Pilot Travel Center - Tracy** - $4.299/gal
10. **TA Travel Center - Stockton** - $4.399/gal

**Coverage**: Optimized for Los Angeles ↔ San Francisco route testing

---

## 📡 API Usage

### Test Route: Los Angeles → San Francisco

| Vehicle Range | Fuel Stops | Test Case |
|---------------|------------|-----------|
| 400 miles | 0 stops | Trip within range ✅ |
| 200 miles | 2-3 stops | Standard truck 🚛 |
| 150 miles | 4+ stops | Short range vehicle ⛽⛽⛽ |

Distance is always ~384 miles (LA → SF)

---

### V1 Endpoint (OpenRouteService - Cloud)

```bash
curl -X POST http://localhost:8000/api/v1/route/optimize/ \
  -H "Content-Type: application/json" \
  -d '{
    "start": "Los Angeles, CA",
    "end": "San Francisco, CA",
    "max_range_miles": 200,
    "mpg": 6.5
  }'
```

### V2 Endpoint (OSRM - Self-hosted)

```bash
curl -X POST http://localhost:8000/api/v2/route/optimize/ \
  -H "Content-Type: application/json" \
  -d '{
    "start": "Los Angeles, CA",
    "end": "San Francisco, CA",
    "max_range_miles": 200,
    "mpg": 6.5
  }'
```

### Request Parameters

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `start` | string | Starting location | "Los Angeles, CA" |
| `end` | string | Ending location | "San Francisco, CA" |
| `max_range_miles` | integer | Vehicle range on full tank | 200 |
| `mpg` | float | Fuel efficiency (miles per gallon) | 6.5 |

**MPG Context**: Commercial trucks typically get 5.5-7.5 MPG. We use 6.5 as a realistic average.

---

### Response Format

Both V1 and V2 return **identical structure**, only differing in `routing_engine` field:

```json
{
  "routing_engine": "OpenRouteService (v1)" or "OSRM (v2)",
  "route": {
    "start": "Los Angeles, CA",
    "end": "San Francisco, CA",
    "start_coordinates": {
      "longitude": -118.25703,
      "latitude": 34.05513
    },
    "end_coordinates": {
      "longitude": -122.431272,
      "latitude": 37.778008
    },
    "distance_miles": 384.57,
    "duration_hours": 6.6,
    "geometry": {
      "type": "LineString",
      "coordinates": [[...], [...]]
    }
  },
  "fuel_stops": [
    {
      "name": "TA Travel Center - Lebec",
      "address": "5772 Dennis McCarthy Drive",
      "city": "Lebec",
      "state": "CA",
      "retail_price": 4.299,
      "location": {
        "longitude": -118.8689,
        "latitude": 34.8378
      },
      "distance_from_start_miles": 65.2,
      "gallons_to_fill": 10.0,
      "estimated_cost": 42.99
    }
  ],
  "summary": {
    "total_distance_miles": 384.57,
    "total_fuel_gallons": 59.16,
    "total_fuel_cost": 254.32,
    "number_of_stops": 2,
    "average_price_per_gallon": 4.299,
    "message": "Route optimized with fuel stops"
  }
}
```

---

### Health Check Endpoints

```bash
# V1 Health Check
curl http://localhost:8000/api/v1/route/health/

# V2 Health Check
curl http://localhost:8000/api/v2/route/health/
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "v1" or "v2",
  "routing_engine": "OpenRouteService" or "OSRM"
}
```

---

## 🧪 Testing

### Automated Test Script

```bash
python3 test_api_endpoints.py
```

Tests both V1 and V2 with:
- ✅ Health checks
- ✅ Long distance with fuel stops (200 mi range)
- ✅ Short distance without fuel stops (400 mi range)
- ✅ Multiple stops (150 mi range)

---

## 🔧 Algorithm Overview

The fuel optimization uses a **greedy look-ahead strategy**:

1. **Find Nearby Stations**
   - PostGIS `ST_DWithin` query (15-mile buffer around route)
   - Uses GIST spatial index for performance

2. **Project onto Route**
   - Calculate mile markers for each station
   - Determine distance from start

3. **Optimize Stops** (Greedy with Look-ahead)
   - If cheaper station exists ahead: buy just enough to reach it
   - If current station is cheapest in range: fill up completely
   - Respect vehicle `max_range_miles` constraint

4. **Calculate Costs**
   - `gallons_to_fill = miles_driven / mpg`
   - `cost = gallons_to_fill * price_per_gallon`

**Time Complexity**: O(n log n) where n = stations near route

---

## ⚡ Performance Optimizations

| Optimization | Impact | Implementation |
|--------------|--------|----------------|
| **GIST Spatial Index** | 10-30x faster | PostGIS automatic on PointField |
| **Route Caching** | 24 hours | Django cache framework |
| **Geocoding Cache** | 30 days | Saves API quota |
| **V2 Local Routing** | 5x faster | OSRM localhost vs cloud API |
| **ST_DWithin Query** | No distance calc | PostGIS geography type |

---

## 📊 Caching Strategy

| Cache Type | TTL | Purpose |
|------------|-----|---------|
| **Routes** | 24 hours | Reduces routing API calls |
| **Geocoding** | 30 days | Coordinates rarely change |
| **Backend** | LocMemCache (dev) | In-memory, per-process |
| **Production** | Redis (recommended) | Shared cache across workers |

Configure in `config/settings/base.py:125-135`

---

## 🐳 Docker Services

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart OSRM only
docker-compose restart osrm
```

**Services Running:**
- **PostgreSQL + PostGIS** - Port 5432
- **OSRM Server** - Port 5001

---

## 🔑 API Keys

### Required Keys

| Service | For | Free Tier | Get Key |
|---------|-----|-----------|---------|
| **OpenRouteService** | V1 routing | 2,000 req/day | [signup](https://openrouteservice.org/dev/#/signup) |
| **LocationIQ** | V2 geocoding | 10,000 req/day | [signup](https://locationiq.com/) |

### Configure in `.env`

```env
ORS_API_KEY=your-ors-key-here
LOCATIONIQ_API_KEY=your-locationiq-key-here
OSRM_BASE_URL=http://localhost:5001
```

---

## 📖 Documentation

| File | Description |
|------|-------------|
| `README.md` | This file - main documentation |

---

## 🚨 Troubleshooting

### "No fuel stops found"
```bash
# Verify stations imported
docker exec spotter-project-db-1 psql -U postgres -d fuel_optimizer \
  -c "SELECT COUNT(*) FROM stations_fuelstation;"
# Should show: 10

# Reimport if needed
python manage.py import_demo_data fuel_prices_demo_geocoded.csv
```

### "ORS API error" or "Rate limit exceeded"
- Switch to V2 (unlimited routing)
- Or get new ORS API key (free tier resets daily)

### "OSRM connection refused"
```bash
# Check OSRM health
curl http://localhost:5001/health
# Should return: {"code":"Ok"}

# Restart OSRM
docker-compose restart osrm
docker-compose logs osrm
```

### Port already in use
```bash
# Kill existing processes
pkill -f "manage.py runserver"
docker-compose down
```

---

## 🚀 Production Deployment

### Recommendations

✅ **Use V2 (OSRM)** for production (unlimited requests)
✅ **Redis caching** instead of LocMemCache
✅ **Gunicorn** instead of Django dev server
✅ **SSL/TLS** for HTTPS
✅ **Environment variables** for secrets
✅ **Regular map updates** (monthly for OSRM)

### Production Settings

```bash
# .env
DEBUG=False
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=generate-random-key-here
ALLOWED_HOSTS=yourdomain.com
```

---

## 🤝 Contributing

Contributions welcome! Please open issues or PRs on GitHub.

---

## 📄 License

MIT License

---

## 💡 Quick Links

- **API Docs**: http://localhost:8000/api/docs/
- **V1 Health**: http://localhost:8000/api/v1/route/health/
- **V2 Health**: http://localhost:8000/api/v2/route/health/
- **OpenAPI Schema**: http://localhost:8000/api/schema/
