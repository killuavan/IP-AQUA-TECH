"""
Firebase Admin SDK client for IP Aqua Tech.

Setup:
1. Create a Firebase project at https://console.firebase.google.com
2. Enable Realtime Database
3. Project Settings → Service accounts → Generate new private key
4. Save the JSON file as: firebase-service-account.json (project root)
5. Set FIREBASE_DATABASE_URL in settings / .env

Realtime Database structure expected:

ipaquatech/
  devices/
    {device_id}/
      meta: { name, type, firmware, last_seen }
  sensors/
    water_quality/
      latest: { ph, tds, turbidity, flow_rate, water_level, water_level_status, water_dirty, timestamp, device_id }
    solar/
      latest: { panel_voltage, panel_current, power_output, power_consumption, irradiance, timestamp, device_id }
    battery/
      latest: { voltage, percentage, charging_status, temperature, device_id, timestamp }
    tank/
      latest: { level_percent, volume_liters, capacity_liters, device_id, timestamp }
    pump/
      latest: { pump_status, flow_status, water_level_status, water_dirty, level_sensor_fault, device_id, timestamp }
"""
from __future__ import annotations

import json
import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

_app = None
_db = None
_firestore = None


class FirebaseNotConfigured(Exception):
    """Raised when Firebase credentials are missing."""


def is_firebase_configured() -> bool:
    cred_path = Path(getattr(settings, 'FIREBASE_CREDENTIALS_PATH', '') or '')
    db_url = getattr(settings, 'FIREBASE_DATABASE_URL', '') or ''
    return bool(cred_path and cred_path.exists() and db_url)


def get_firebase_app():
    """Initialize and return the Firebase app (singleton)."""
    global _app
    if _app is not None:
        return _app

    if not is_firebase_configured():
        raise FirebaseNotConfigured(
            'Firebase is not configured. Place firebase-service-account.json '
            'in the project root and set FIREBASE_DATABASE_URL in settings.'
        )

    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        _app = firebase_admin.get_app()
        return _app

    cred_path = Path(settings.FIREBASE_CREDENTIALS_PATH)
    cred = credentials.Certificate(str(cred_path))
    _app = firebase_admin.initialize_app(cred, {
        'databaseURL': settings.FIREBASE_DATABASE_URL,
    })
    logger.info('Firebase Admin initialized: %s', settings.FIREBASE_DATABASE_URL)
    return _app


def get_rtdb():
    """Return Firebase Realtime Database reference root."""
    global _db
    if _db is not None:
        return _db
    get_firebase_app()
    from firebase_admin import db
    root = getattr(settings, 'FIREBASE_RTDB_ROOT', 'ipaquatech')
    _db = db.reference(root)
    return _db


def get_firestore():
    """Return the Firestore client using the same Firebase Admin app."""
    global _firestore
    if _firestore is not None:
        return _firestore
    get_firebase_app()
    from firebase_admin import firestore
    _firestore = firestore.client()
    return _firestore


def mirror_to_firestore(path: str, data: Any, record_history: bool = True) -> None:
    """Mirror an RTDB path into Firestore without interrupting RTDB ingestion."""
    try:
        from firebase_admin import firestore

        payload = json.loads(json.dumps(data, default=str))
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
        ).hexdigest()
        document_id = path.strip('/').replace('/', '__') or 'root'
        client = get_firestore()
        current = client.collection('rtdb_mirror_current').document(document_id)
        current.set({
            'path': path.strip('/'),
            'data': payload,
            'fingerprint': fingerprint,
            'updated_at': firestore.SERVER_TIMESTAMP,
        })
        if record_history:
            history_id = hashlib.sha256(
                f'{path.strip("/")}:{fingerprint}'.encode()
            ).hexdigest()
            client.collection('rtdb_mirror_history').document(history_id).set({
                'path': path.strip('/'),
                'data': payload,
                'fingerprint': fingerprint,
                'received_at': firestore.SERVER_TIMESTAMP,
            })
    except Exception:
        logger.exception('Firestore mirror failed for RTDB path %s', path)


def read_path(path: str) -> Any:
    """Read a path under the project root. path e.g. 'sensors/water_quality/latest'."""
    ref = get_rtdb().child(path)
    return ref.get()


def write_path(path: str, data: dict) -> None:
    """Write/overwrite a path under the project root."""
    get_rtdb().child(path).set(data)
    mirror_to_firestore(path, data)


def update_path(path: str, data: dict) -> None:
    """Update fields at a path."""
    get_rtdb().child(path).update(data)


def push_path(path: str, data: dict) -> str:
    """Push a new child under path; returns generated key."""
    ref = get_rtdb().child(path).push(data)
    return ref.key


def get_web_config() -> dict:
    """Public Firebase web config for browser clients (safe to expose)."""
    return {
        'apiKey': getattr(settings, 'FIREBASE_WEB_API_KEY', ''),
        'authDomain': getattr(settings, 'FIREBASE_WEB_AUTH_DOMAIN', ''),
        'databaseURL': getattr(settings, 'FIREBASE_DATABASE_URL', ''),
        'projectId': getattr(settings, 'FIREBASE_PROJECT_ID', ''),
        'storageBucket': getattr(settings, 'FIREBASE_WEB_STORAGE_BUCKET', ''),
        'messagingSenderId': getattr(settings, 'FIREBASE_WEB_MESSAGING_SENDER_ID', ''),
        'appId': getattr(settings, 'FIREBASE_WEB_APP_ID', ''),
        'rtdbRoot': getattr(settings, 'FIREBASE_RTDB_ROOT', 'ipaquatech'),
        'enabled': bool(
            getattr(settings, 'FIREBASE_WEB_API_KEY', '')
            and getattr(settings, 'FIREBASE_DATABASE_URL', '')
        ),
    }


def load_service_account_preview() -> Optional[dict]:
    """Return non-secret metadata from credentials file if present."""
    path = Path(getattr(settings, 'FIREBASE_CREDENTIALS_PATH', '') or '')
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return {
            'project_id': data.get('project_id'),
            'client_email': data.get('client_email'),
            'type': data.get('type'),
        }
    except Exception:
        return None
