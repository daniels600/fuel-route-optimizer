FROM python:3.11-slim

# Install system dependencies for PostGIS
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    binutils \
    libproj-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations and start server
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
