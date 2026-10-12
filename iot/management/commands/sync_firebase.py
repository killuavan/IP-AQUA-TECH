"""
Sync latest sensor data from Firebase Realtime Database into Django.

Usage:
    python manage.py sync_firebase
    python manage.py sync_firebase --demo   # local demo ingest (no Firebase)
"""
from django.core.management.base import BaseCommand

from iot.services import create_demo_local_ingest, sync_from_firebase


class Command(BaseCommand):
    help = 'Sync sensor data from Firebase RTDB (or run local demo ingest)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--demo',
            action='store_true',
            help='Ingest local demo data without calling Firebase',
        )

    def handle(self, *args, **options):
        if options['demo']:
            results = create_demo_local_ingest()
            self.stdout.write(self.style.SUCCESS(f'Demo ingest: {results}'))
            return

        log = sync_from_firebase()
        style = self.style.SUCCESS if log.status == 'SUCCESS' else self.style.WARNING
        if log.status == 'FAILED':
            style = self.style.ERROR
        self.stdout.write(style(f'[{log.status}] {log.message}'))
        if log.details:
            self.stdout.write(f'Details: {log.details}')
