"""
Weather client for rain forecast.

Primary: Open-Meteo (free, no API key)
Fallback: deterministic stub (offline demo)
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _location_config() -> dict:
    return {
        'name': getattr(settings, 'PREDICTION_LOCATION_NAME', 'Philippines'),
        'latitude': float(getattr(settings, 'PREDICTION_LATITUDE', 14.5995)),
        'longitude': float(getattr(settings, 'PREDICTION_LONGITUDE', 120.9842)),
        'timezone': getattr(settings, 'PREDICTION_TIMEZONE', 'Asia/Manila'),
    }


def fetch_weather(
    force_stub: bool = False,
    allow_fallback: bool = True,
    allow_stub_setting: bool = True,
) -> dict[str, Any]:
    """
    Return a normalized weather dict ready to save as WeatherSnapshot.

    Keys:
      source, location_name, latitude, longitude,
      rain_last_1h_mm, rain_last_24h_mm, rain_next_24h_mm,
      rain_probability_max_pct, will_rain_next_24h,
      humidity_pct, cloud_cover_pct, temperature_c, raw_payload
    """
    if force_stub or (
        allow_stub_setting and getattr(settings, 'PREDICTION_WEATHER_STUB', False)
    ):
        return _stub_weather()

    try:
        return _fetch_open_meteo()
    except Exception as exc:
        if not allow_fallback:
            raise
        logger.warning('Open-Meteo failed (%s); using stub weather.', exc)
        data = _stub_weather()
        data['details_error'] = str(exc)
        data['raw_payload'] = {
            **(data.get('raw_payload') or {}),
            'fallback_reason': str(exc),
        }
        return data


def _fetch_open_meteo() -> dict[str, Any]:
    loc = _location_config()
    params = {
        'latitude': loc['latitude'],
        'longitude': loc['longitude'],
        'hourly': 'precipitation,precipitation_probability,relative_humidity_2m,cloud_cover,temperature_2m',
        'timezone': loc['timezone'],
        'forecast_days': 2,
        'past_days': 1,
    }
    url = 'https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers={'User-Agent': 'IPAquaTech/1.0'})
    with urllib.request.urlopen(req, timeout=12) as resp:
        payload = json.loads(resp.read().decode('utf-8'))

    hourly = payload.get('hourly') or {}
    times = hourly.get('time') or []
    precip = hourly.get('precipitation') or []
    probs = hourly.get('precipitation_probability') or []
    humidity = hourly.get('relative_humidity_2m') or []
    clouds = hourly.get('cloud_cover') or []
    temps = hourly.get('temperature_2m') or []

    tz = ZoneInfo(loc['timezone'])
    now = datetime.now(tz)

    def parse_t(s: str) -> datetime:
        # Open-Meteo: "2026-07-22T14:00"
        return datetime.fromisoformat(s).replace(tzinfo=tz)

    last_1h = 0.0
    last_24h = 0.0
    next_24h = 0.0
    max_prob = 0.0
    cur_hum = None
    cur_cloud = None
    cur_temp = None

    for i, t_str in enumerate(times):
        try:
            t = parse_t(t_str)
        except ValueError:
            continue
        p = float(precip[i]) if i < len(precip) and precip[i] is not None else 0.0
        pr = float(probs[i]) if i < len(probs) and probs[i] is not None else 0.0

        delta_h = (t - now).total_seconds() / 3600.0
        if -1.0 <= delta_h <= 0.0:
            last_1h += p
        if -24.0 <= delta_h <= 0.0:
            last_24h += p
        if 0.0 < delta_h <= 24.0:
            next_24h += p
            max_prob = max(max_prob, pr)
        if abs(delta_h) < 0.6:
            if i < len(humidity) and humidity[i] is not None:
                cur_hum = float(humidity[i])
            if i < len(clouds) and clouds[i] is not None:
                cur_cloud = float(clouds[i])
            if i < len(temps) and temps[i] is not None:
                cur_temp = float(temps[i])

    rain_threshold = float(getattr(settings, 'PREDICTION_RAIN_MM_THRESHOLD', 1.0))
    will_rain = next_24h >= rain_threshold or max_prob >= float(
        getattr(settings, 'PREDICTION_RAIN_PROB_THRESHOLD', 50)
    )

    return {
        'source': 'open_meteo',
        'location_name': loc['name'],
        'latitude': loc['latitude'],
        'longitude': loc['longitude'],
        'rain_last_1h_mm': round(last_1h, 2),
        'rain_last_24h_mm': round(last_24h, 2),
        'rain_next_24h_mm': round(next_24h, 2),
        'rain_probability_max_pct': round(max_prob, 1),
        'will_rain_next_24h': will_rain,
        'humidity_pct': cur_hum,
        'cloud_cover_pct': cur_cloud,
        'temperature_c': cur_temp,
        'raw_payload': {
            'url': url,
            'timezone': loc['timezone'],
            'fetched_local': now.isoformat(),
        },
    }


def _stub_weather() -> dict[str, Any]:
    """Offline demo weather – cycles lightly by hour so UI is not static."""
    loc = _location_config()
    hour = timezone.localtime().hour
    # Mild demo pattern: more rain in afternoon hours
    base_next = 0.5 + (hour % 6) * 1.2
    base_past = 0.2 + (hour % 4) * 0.8
    prob = min(95.0, 20.0 + hour * 2.5)
    will = base_next >= 1.0 or prob >= 50

    return {
        'source': 'stub',
        'location_name': loc['name'] + ' (demo)',
        'latitude': loc['latitude'],
        'longitude': loc['longitude'],
        'rain_last_1h_mm': round(base_past / 8.0, 2),
        'rain_last_24h_mm': round(base_past, 2),
        'rain_next_24h_mm': round(base_next, 2),
        'rain_probability_max_pct': round(prob, 1),
        'will_rain_next_24h': will,
        'humidity_pct': 70.0 + (hour % 10),
        'cloud_cover_pct': 40.0 + (hour % 20),
        'temperature_c': 26.0 + (hour % 5) * 0.3,
        'raw_payload': {
            'note': 'Stub weather for offline demo',
            'hour': hour,
        },
    }
