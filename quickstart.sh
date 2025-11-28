#!/bin/bash

# Fuel Route Optimizer - Comprehensive Quick Start Script
# This script sets up the entire project with both V1 and V2 implementations

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "================================================"
echo "  Fuel Route Optimizer - Quick Start"
echo "  V1: OpenRouteService (Cloud) + V2: OSRM (Self-hosted)"
echo "================================================"
echo -e "${NC}"
echo ""

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ========================================
# Step 1: Check Prerequisites
# ========================================
echo -e "${BLUE}Step 1: Checking prerequisites...${NC}"

# Check Python 3
if ! command_exists python3; then
    print_error "Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
print_success "Python $PYTHON_VERSION found"

# Check Docker
if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker Desktop."
    echo "Download from: https://www.docker.com/products/docker-desktop"
    exit 1
fi
print_success "Docker found"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker Desktop."
    exit 1
fi
print_success "Docker is running"

# Check for Homebrew (macOS only)
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command_exists brew; then
        print_error "Homebrew is not installed. Please install Homebrew first:"
        echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    print_success "Homebrew found"
fi

echo ""

# ========================================
# Step 2: Check/Install GDAL (macOS only)
# ========================================
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${BLUE}Step 2: Checking GDAL installation (required for GeoDjango)...${NC}"

    if ! command_exists gdal-config; then
        print_warning "GDAL is not installed. Installing via Homebrew..."
        print_info "This may take 5-10 minutes. Please be patient."
        brew install gdal
        print_success "GDAL installed successfully"
    else
        GDAL_VERSION=$(gdal-config --version)
        print_success "GDAL $GDAL_VERSION already installed"
    fi

    # Verify GDAL library exists
    if [ -f "/opt/homebrew/lib/libgdal.dylib" ] || [ -f "/usr/local/lib/libgdal.dylib" ]; then
        print_success "GDAL library found"
    else
        print_error "GDAL library not found. Please run: brew install gdal"
        exit 1
    fi
else
    echo -e "${BLUE}Step 2: Non-macOS system detected${NC}"
    print_info "GDAL must be installed manually on Linux/Windows."
    print_info "See README.md for installation instructions."
fi

echo ""

# ========================================
# Step 3: Create/Activate Virtual Environment
# ========================================
echo -e "${BLUE}Step 3: Setting up Python virtual environment...${NC}"

if [ ! -d "venv" ]; then
    print_info "Creating virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
else
    print_success "Virtual environment already exists"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate
print_success "Virtual environment activated"

echo ""

# ========================================
# Step 4: Install Python Dependencies
# ========================================
echo -e "${BLUE}Step 4: Installing Python dependencies...${NC}"

print_info "Upgrading pip..."
pip install --upgrade pip --quiet
print_info "Installing requirements..."
pip install -r requirements.txt --quiet

print_success "Python dependencies installed"
echo ""

# ========================================
# Step 5: Start PostgreSQL with PostGIS
# ========================================
echo -e "${BLUE}Step 5: Starting PostgreSQL database...${NC}"

# Stop existing containers if any
docker-compose down 2>/dev/null || true

# Start PostgreSQL and OSRM
print_info "Starting PostgreSQL and OSRM containers..."
docker-compose up -d db

print_success "PostgreSQL container started"
print_info "Waiting for PostgreSQL to be ready..."

# Wait for PostgreSQL to be ready (up to 30 seconds)
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec spotter-project-db-1 pg_isready -U postgres >/dev/null 2>&1; then
        print_success "PostgreSQL is ready"
        break
    fi
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        print_error "PostgreSQL failed to start within 30 seconds"
        exit 1
    fi
done

echo ""

# ========================================
# Step 6: Setup OSRM Server (V2)
# ========================================
echo -e "${BLUE}Step 6: Setting up OSRM server for V2...${NC}"

# Check if California data exists
if [ ! -d "osrm-data" ] || [ ! -f "osrm-data/california-latest.osm.pbf" ]; then
    print_info "Downloading California map data (~450MB)..."
    mkdir -p osrm-data
    cd osrm-data
    curl -L -O http://download.geofabrik.de/north-america/us/california-latest.osm.pbf
    cd ..
    print_success "California map data downloaded"
else
    print_success "California map data already exists"
fi

# Check if OSRM data is processed
if [ ! -f "osrm-data/california-latest.osrm" ]; then
    print_info "Processing map data with OSRM (this takes 2-3 minutes)..."

    docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/california-latest.osm.pbf
    docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/california-latest.osrm
    docker run -t -v "${PWD}/osrm-data:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/california-latest.osrm

    print_success "OSRM data processed successfully"
else
    print_success "OSRM data already processed"
fi

# Start OSRM server
print_info "Starting OSRM routing server on port 5001..."
docker-compose up -d osrm

# Wait for OSRM to be ready
sleep 3
if curl -s http://localhost:5001/health 2>/dev/null | grep -q "Ok\|ok"; then
    print_success "OSRM server is ready on port 5001"
else
    print_warning "OSRM server may still be starting. Check with: curl http://localhost:5001/health"
fi

echo ""

# ========================================
# Step 7: Create Database and Enable PostGIS
# ========================================
echo -e "${BLUE}Step 7: Setting up database...${NC}"

# Check if database exists
if docker exec spotter-project-db-1 psql -U postgres -lqt | cut -d \| -f 1 | grep -qw fuel_optimizer; then
    print_warning "Database 'fuel_optimizer' already exists"
    read -p "Do you want to recreate it? This will delete all data. (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Dropping and recreating database..."
        docker exec spotter-project-db-1 dropdb -U postgres fuel_optimizer
        docker exec spotter-project-db-1 createdb -U postgres fuel_optimizer
        print_success "Database recreated"
    fi
else
    print_info "Creating database 'fuel_optimizer'..."
    docker exec spotter-project-db-1 createdb -U postgres fuel_optimizer
    print_success "Database created"
fi

# Enable PostGIS extension
print_info "Enabling PostGIS extension..."
docker exec spotter-project-db-1 psql -U postgres -d fuel_optimizer -c "CREATE EXTENSION IF NOT EXISTS postgis;" >/dev/null
print_success "PostGIS extension enabled"

echo ""

# ========================================
# Step 8: Check Database Connection
# ========================================
echo -e "${BLUE}Step 8: Verifying database connection...${NC}"

if python manage.py check --database default >/dev/null 2>&1; then
    print_success "Database connection verified"
else
    print_error "Failed to connect to database"
    print_info "Check that DB_HOST in .env is set to 127.0.0.1 (not localhost)"
    exit 1
fi

echo ""

# ========================================
# Step 9: Run Migrations
# ========================================
echo -e "${BLUE}Step 9: Running database migrations...${NC}"

# Create migrations directories if they don't exist
mkdir -p apps/stations/migrations apps/routing/migrations
touch apps/stations/migrations/__init__.py apps/routing/migrations/__init__.py

# Create and apply migrations
print_info "Creating migrations..."
python manage.py makemigrations

print_info "Applying migrations..."
python manage.py migrate

print_success "Database migrations completed"
echo ""

# ========================================
# Step 10: Import Demo Fuel Station Data
# ========================================
echo -e "${BLUE}Step 10: Importing demo fuel station data...${NC}"

# Check if demo data file exists
if [ ! -f "fuel_prices_demo_geocoded.csv" ]; then
    print_error "Demo data file 'fuel_prices_demo_geocoded.csv' not found!"
    print_info "This file should be included in the repository."
    exit 1
fi

# Check if data already exists
STATION_COUNT=$(python -c "
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()
from apps.stations.models import FuelStation
print(FuelStation.objects.count())
" 2>/dev/null || echo "0")

if [ "$STATION_COUNT" -gt 0 ]; then
    print_warning "Database already contains $STATION_COUNT fuel stations"
    read -p "Do you want to reimport demo data? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Importing 24 pre-geocoded demo stations..."
        python manage.py import_demo_data fuel_prices_demo_geocoded.csv
        print_success "Demo fuel stations imported successfully"
    else
        print_info "Skipping demo data import"
    fi
else
    print_info "Importing 24 pre-geocoded demo stations (Los Angeles to San Francisco route)..."
    python manage.py import_demo_data fuel_prices_demo_geocoded.csv
    print_success "Demo fuel stations imported successfully (24 stations)"
fi

echo ""

# ========================================
# Step 11: Verify API Keys
# ========================================
echo -e "${BLUE}Step 11: Verifying API keys...${NC}"

# Check ORS API Key (for V1)
if grep -q "ORS_API_KEY=.*[a-zA-Z0-9]" .env 2>/dev/null; then
    print_success "ORS_API_KEY configured (V1 - OpenRouteService)"
else
    print_warning "ORS_API_KEY not set (V1 won't work)"
    print_info "Get free key at: https://openrouteservice.org/dev/#/signup"
fi

# Check LocationIQ API Key (for V2 geocoding)
if grep -q "LOCATIONIQ_API_KEY=.*[a-zA-Z0-9]" .env 2>/dev/null; then
    print_success "LOCATIONIQ_API_KEY configured (V2 geocoding)"
else
    print_warning "LOCATIONIQ_API_KEY not set (V2 geocoding won't work)"
    print_info "Get free key at: https://locationiq.com/ (10,000 requests/day)"
fi

# Check OSRM URL
if grep -q "OSRM_BASE_URL=.*5001" .env 2>/dev/null; then
    print_success "OSRM_BASE_URL configured (V2 routing)"
else
    print_warning "OSRM_BASE_URL not configured correctly"
    print_info "Should be: OSRM_BASE_URL=http://localhost:5001"
fi

echo ""

# ========================================
# Step 12: Final System Check
# ========================================
echo -e "${BLUE}Step 12: Running final system check...${NC}"

if python manage.py check 2>&1 | grep -q "System check identified no issues"; then
    print_success "All system checks passed"
else
    print_warning "Some non-critical issues found (this is normal for development)"
fi

echo ""

# ========================================
# Setup Complete!
# ========================================
echo -e "${GREEN}"
echo "======================================"
echo "✅ Setup Complete!"
echo "======================================"
echo -e "${NC}"
echo ""

print_success "The Fuel Route Optimizer is ready with V1 and V2!"
echo ""

echo -e "${BLUE}Architecture Overview:${NC}"
echo ""
echo "  V1 (Cloud-based):           /api/v1/route/optimize/"
echo "    • OpenRouteService routing"
echo "    • 2,000 requests/day free tier"
echo "    • Good for demos and development"
echo ""
echo "  V2 (Self-hosted):           /api/v2/route/optimize/"
echo "    • OSRM routing (unlimited)"
echo "    • LocationIQ geocoding (10,000/day)"
echo "    • Production-ready, no quotas"
echo ""

echo -e "${BLUE}Next Steps:${NC}"
echo ""
echo "1. Start the development server:"
echo -e "   ${GREEN}python manage.py runserver${NC}"
echo ""
echo "2. Open your browser and visit:"
echo -e "   ${BLUE}http://localhost:8000/api/docs/${NC} - Interactive API Documentation"
echo ""
echo "3. Check health endpoints:"
echo -e "   ${BLUE}http://localhost:8000/api/v1/route/health/${NC} - V1 Health Check"
echo -e "   ${BLUE}http://localhost:8000/api/v2/route/health/${NC} - V2 Health Check"
echo ""

echo "4. Test V1 (OpenRouteService):"
echo -e "${YELLOW}curl -X POST http://localhost:8000/api/v1/route/optimize/ \\
  -H \"Content-Type: application/json\" \\
  -d '{
    \"start\": \"Los Angeles, CA\",
    \"end\": \"San Francisco, CA\",
    \"max_range_miles\": 400,
    \"mpg\": 6.5
  }'${NC}"
echo ""

echo "5. Test V2 (OSRM):"
echo -e "${YELLOW}curl -X POST http://localhost:8000/api/v2/route/optimize/ \\
  -H \"Content-Type: application/json\" \\
  -d '{
    \"start\": \"Los Angeles, CA\",
    \"end\": \"San Francisco, CA\",
    \"max_range_miles\": 400,
    \"mpg\": 6.5
  }'${NC}"
echo ""

echo -e "${BLUE}Useful Commands:${NC}"
echo "  • Activate virtualenv:      source venv/bin/activate"
echo "  • Run Django server:        python manage.py runserver"
echo "  • Import demo data:         python manage.py import_demo_data fuel_prices_demo_geocoded.csv"
echo "  • View database:            docker exec -it spotter-project-db-1 psql -U postgres -d fuel_optimizer"
echo "  • Check OSRM health:        curl http://localhost:5001/health"
echo "  • View OSRM logs:           docker-compose logs osrm"
echo "  • Restart services:         docker-compose restart"
echo "  • Stop services:            docker-compose down"
echo ""

echo -e "${BLUE}Caching Mechanism:${NC}"
echo "  • Routes cached for 24 hours (reduces API calls)"
echo "  • Geocoding cached for 30 days (saves quota)"
echo "  • Local memory cache (clears on restart)"
echo "  • For production, configure Redis in config/settings/base.py"
echo ""

echo -e "${BLUE}Demo Data:${NC}"
echo "  • 24 pre-geocoded stations"
echo "  • Covers Los Angeles to San Francisco route"
echo "  • No geocoding API calls needed"
echo "  • Perfect for testing both V1 and V2"
echo ""

print_success "Happy routing! 🚗💨"
echo ""

# Ask if user wants to start the server now
read -p "Would you like to start the development server now? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo ""
    print_info "Starting development server..."
    print_info "Press Ctrl+C to stop the server"
    echo ""
    print_info "Once running, test the endpoints:"
    echo "  • V1: http://localhost:8000/api/v1/route/health/"
    echo "  • V2: http://localhost:8000/api/v2/route/health/"
    echo "  • API Docs: http://localhost:8000/api/docs/"
    echo ""
    sleep 2
    python manage.py runserver
fi
