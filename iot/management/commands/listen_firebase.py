"""Continuously copy Firebase RTDB sensor updates into Django monitoring."""
from __future__ import annotations

import json
import logging
import threading

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from iot.firebase_client import FirebaseNotConfigured, get_rtdb, mirror_to_firestore
from iot.models import SensorReadingCache
from iot.services import (
    ingest_battery,
    ingest_pump,
    ingest_solar,
    ingest_tank,
    ingest_water_quality,
)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Listen to Firebase RTDB and save live readings into Monitoring'

    def handle(self, *args, **options):
        try:
            root = get_rtdb()
        except FirebaseNotConfigured as exc:
            raise CommandError(str(exc)) from exc

        stop_event = threading.Event()
        fingerprints: dict[str, str] = {}
        fingerprint_lock = threading.Lock()
        listeners = []

        sources = [
            ('water_quality', 'sensors/water_quality/latest', ingest_water_quality),
            ('solar', 'sensors/solar/latest', ingest_solar),
            ('battery', 'sensors/battery/latest', ingest_battery),
            ('tank', 'sensors/tank/latest', ingest_tank),
            ('pump', 'sensors/pump/latest', ingest_pump),
        ]

        # Do not import the same /latest snapshot again after a bridge restart.
        for label, _path, _ingest in sources:
            latest = SensorReadingCache.objects.filter(
                reading_type=label,
                source='firebase',
            ).first()
            if latest and isinstance(latest.payload, dict):
                fingerprints[label] = json.dumps(
                    latest.payload, sort_keys=True, default=str,
                )

        def build_callback(label, reference, ingest):
            def callback(event):
                close_old_connections()
                try:
                    # A PUT to the /latest node normally arrives at path '/'.
                    # For a child-level event, fetch the complete latest payload.
                    data = event.data if event.path == '/' else reference.get()
                    if not isinstance(data, dict) or not data:
                        return

                    mirror_to_firestore(f'sensors/{label}/latest', data)

                    fingerprint = json.dumps(data, sort_keys=True, default=str)
                    with fingerprint_lock:
                        if fingerprints.get(label) == fingerprint:
                            return
                        fingerprints[label] = fingerprint

                    obj = ingest(data, source='firebase')
                    if obj is not None:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Firebase -> Monitoring: {label} saved (pk={obj.pk})'
                            )
                        )
                except Exception as exc:  # keep the listener alive after bad data
                    logger.exception('Firebase listener failed for %s', label)
                    self.stderr.write(self.style.ERROR(f'{label}: {exc}'))
                finally:
                    close_old_connections()

            return callback

        try:
            for label, path, ingest in sources:
                reference = root.child(path)
                listener = reference.listen(build_callback(label, reference, ingest))
                listeners.append(listener)
                self.stdout.write(f'Listening: {path}')

            self.stdout.write(
                self.style.SUCCESS(
                    'Firebase bridge is running. Press Ctrl+C to stop.'
                )
            )
            while not stop_event.wait(1):
                pass
        except KeyboardInterrupt:
            self.stdout.write('\nStopping Firebase bridge...')
        except Exception as exc:
            raise CommandError(f'Firebase listener failed: {exc}') from exc
        finally:
            for listener in listeners:
                try:
                    listener.close()
                except Exception:
                    logger.exception('Could not close Firebase listener')
