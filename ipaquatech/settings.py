"""
Django settings for IP Aqua Tech project.
Solar-Powered Drinking Water Filtration Monitoring System
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'local-development-only-change-this-secret-before-deploying-9f4c2a7e6b1d',
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        'DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1'
    ).split(',')
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip().rstrip('/')
    for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# Hosting platforms commonly terminate HTTPS before forwarding to Django.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.environ.get('DJANGO_SECURE_SSL_REDIRECT', 'False').lower() == 'true'
SESSION_COOKIE_SECURE = os.environ.get('DJANGO_COOKIE_SECURE', 'False').lower() == 'true'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_FAILURE_VIEW = 'accounts.views.csrf_failure'
SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get(
    'DJANGO_HSTS_INCLUDE_SUBDOMAINS', 'False'
).lower() == 'true'
SECURE_HSTS_PRELOAD = os.environ.get('DJANGO_HSTS_PRELOAD', 'False').lower() == 'true'

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Project apps
    'accounts',
    'dashboard',
    'monitoring',
    'solar',
    'filters',
    'maintenance',
    'reports',
    'notifications',
    'iot',
    'predictions',
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

ROOT_URLCONF = 'ipaquatech.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notifications.context_processors.unread_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'ipaquatech.wsgi.application'

# ---------------------------------------------------------------------------
# Database
# Default: SQLite. Switch to MySQL by setting USE_MYSQL=True and credentials.
# ---------------------------------------------------------------------------
USE_MYSQL = os.environ.get('USE_MYSQL', 'False').lower() == 'true'

if USE_MYSQL:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('MYSQL_DATABASE', 'ipaquatech'),
            'USER': os.environ.get('MYSQL_USER', 'root'),
            'PASSWORD': os.environ.get('MYSQL_PASSWORD', ''),
            'HOST': os.environ.get('MYSQL_HOST', 'localhost'),
            'PORT': os.environ.get('MYSQL_PORT', '3306'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                'charset': 'utf8mb4',
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Authentication
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGOUT_REDIRECT_URL = 'accounts:login'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Messages
from django.contrib.messages import constants as messages
MESSAGE_TAGS = {
    messages.DEBUG: 'secondary',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

# Water quality thresholds
WATER_QUALITY_THRESHOLDS = {
    'ph': {'min_normal': 6.5, 'max_normal': 8.5, 'min_warning': 6.0, 'max_warning': 9.0},
    'tds': {'max_normal': 300, 'max_warning': 500},  # ppm
    'turbidity': {'max_normal': 1.0, 'max_warning': 5.0},  # NTU
    'temperature': {'min_normal': 10, 'max_normal': 35, 'min_warning': 5, 'max_warning': 40},
    'flow_rate': {'min_normal': 0.5, 'max_normal': 50},  # L/min
    'pressure': {'min_normal': 1.0, 'max_normal': 6.0, 'min_warning': 0.5, 'max_warning': 8.0},  # bar
}

# Battery / solar thresholds
BATTERY_THRESHOLDS = {
    'low_warning': 30,   # %
    'low_critical': 15,  # %
}

FILTER_THRESHOLDS = {
    'life_warning': 25,   # %
    'life_critical': 10,  # %
}

# Daily production only (from sensor / today's WaterProduction) → LOW / MID / HIGH
# value < mid → LOW; mid ≤ value < high → MID; value ≥ high → HIGH (liters/day)
PRODUCTION_LEVELS = {
    'daily': {'mid': 500, 'high': 1500},
}

# ---------------------------------------------------------------------------
# Firebase / IoT Integration
# ---------------------------------------------------------------------------
# 1. Download service account JSON from Firebase Console
# 2. Save the service-account JSON in the project root (do not commit)
# 3. Set FIREBASE_DATABASE_URL to your Realtime Database URL
# 4. Optionally fill WEB_* fields for browser live listeners
# ---------------------------------------------------------------------------
FIREBASE_CREDENTIALS_PATH = os.environ.get(
    'FIREBASE_CREDENTIALS_PATH',
    str(BASE_DIR / 'waterfilter-9b08d-firebase-adminsdk-fbsvc-2c9d3dfdbd.json'),
)
FIREBASE_DATABASE_URL = os.environ.get(
    'FIREBASE_DATABASE_URL',
    'https://waterfilter-9b08d-default-rtdb.asia-southeast1.firebasedatabase.app',
)
FIREBASE_RTDB_ROOT = os.environ.get('FIREBASE_RTDB_ROOT', 'ipaquatech')
FIREBASE_PROJECT_ID = os.environ.get('FIREBASE_PROJECT_ID', 'waterfilter-9b08d')

# Public web config (Firebase Console → Project settings → Your apps → Web)
# Optional: fill these for browser live listeners (Firebase Console → Project settings → Your apps)
FIREBASE_WEB_API_KEY = os.environ.get('FIREBASE_WEB_API_KEY', '')
FIREBASE_WEB_AUTH_DOMAIN = os.environ.get(
    'FIREBASE_WEB_AUTH_DOMAIN',
    'waterfilter-9b08d.firebaseapp.com',
)
FIREBASE_WEB_STORAGE_BUCKET = os.environ.get(
    'FIREBASE_WEB_STORAGE_BUCKET',
    '',
)
FIREBASE_WEB_MESSAGING_SENDER_ID = os.environ.get('FIREBASE_WEB_MESSAGING_SENDER_ID', '')
FIREBASE_WEB_APP_ID = os.environ.get('FIREBASE_WEB_APP_ID', '')

# ---------------------------------------------------------------------------
# Predictions: rain + malabo na bukal (turbid spring water)
# ---------------------------------------------------------------------------
# Open-Meteo (free, no API key). Set lat/lon to your site.
PREDICTION_LOCATION_NAME = os.environ.get(
    'PREDICTION_LOCATION_NAME',
    'Metro Manila, Philippines',
)
PREDICTION_LATITUDE = float(os.environ.get('PREDICTION_LATITUDE', '14.5995'))
PREDICTION_LONGITUDE = float(os.environ.get('PREDICTION_LONGITUDE', '120.9842'))
PREDICTION_TIMEZONE = os.environ.get('PREDICTION_TIMEZONE', 'Asia/Manila')
# True = always use offline stub weather (no internet)
PREDICTION_WEATHER_STUB = os.environ.get('PREDICTION_WEATHER_STUB', 'False').lower() == 'true'
PREDICTION_RAIN_MM_THRESHOLD = float(os.environ.get('PREDICTION_RAIN_MM_THRESHOLD', '1.0'))
PREDICTION_RAIN_PROB_THRESHOLD = float(os.environ.get('PREDICTION_RAIN_PROB_THRESHOLD', '50'))
PREDICTION_RAIN_PAST_MEDIUM_MM = 5.0
PREDICTION_RAIN_PAST_HIGH_MM = 15.0
PREDICTION_RAIN_NEXT_MEDIUM_MM = 3.0
PREDICTION_RAIN_NEXT_HIGH_MM = 10.0
PREDICTION_MALABO_SCORE_THRESHOLD = 45.0
PREDICTION_ML_MODEL_DIR = str(BASE_DIR / 'predictions' / 'ml_models')
# Monthly rain classes (total mm in the month)
MONTHLY_RAIN_DRY_MAX_MM = 80.0
MONTHLY_RAIN_WET_MIN_MM = 250.0
# Monthly spring dirt risk: score >= this → predicted_dirty_spring = True
MONTHLY_SPRING_DIRT_THRESHOLD = 45.0
# Auto-run next-month ML prediction (once per day) when opening Predictions page
PREDICTION_AUTO_MONTHLY = os.environ.get('PREDICTION_AUTO_MONTHLY', 'True').lower() == 'true'

