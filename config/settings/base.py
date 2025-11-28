import os
from pathlib import Path
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# GeoDjango / GDAL Configuration for macOS
# GDAL library paths for Apple Silicon (M1/M2/M3) and Intel Macs
if os.path.exists('/opt/homebrew/lib/libgdal.dylib'):
    # Apple Silicon Macs
    GDAL_LIBRARY_PATH = '/opt/homebrew/lib/libgdal.dylib'
    GEOS_LIBRARY_PATH = '/opt/homebrew/lib/libgeos_c.dylib'
elif os.path.exists('/usr/local/lib/libgdal.dylib'):
    # Intel Macs
    GDAL_LIBRARY_PATH = '/usr/local/lib/libgdal.dylib'
    GEOS_LIBRARY_PATH = '/usr/local/lib/libgeos_c.dylib'

SECRET_KEY = config('SECRET_KEY', default='change-me-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',  # GeoDjango
    'rest_framework',
    'drf_spectacular',
    'apps.stations',
    'apps.routing',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': config('DB_NAME', default='fuel_optimizer'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='postgres'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Routing and Geocoding API Keys
ORS_API_KEY = config('ORS_API_KEY', default='')
LOCATIONIQ_API_KEY = config('LOCATIONIQ_API_KEY', default='')
OSRM_BASE_URL = config('OSRM_BASE_URL', default='http://localhost:5001')

# Vehicle Constants
VEHICLE_MAX_RANGE_MILES = 500
VEHICLE_MPG = 10
ROUTE_BUFFER_MILES = 15  # Search stations within 15 miles of route

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# API Documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'Fuel Route Optimizer API',
    'VERSION': '1.0.0',
    'DESCRIPTION': 'API for calculating fuel-optimized routes across the USA',
}

# Caching
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        # For production, use Redis:
        # 'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        # 'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}

ROUTE_CACHE_TTL = 86400  # 24 hours
GEOCODE_CACHE_TTL = 86400 * 30  # 30 days
