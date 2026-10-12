"""Copy Django's SQLite records into Firestore collections."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.apps import apps
from django.core.management.base import BaseCommand

from iot.firebase_client import FirebaseNotConfigured, get_firestore


EXCLUDED_MODELS = {
    ('contenttypes', 'contenttype'),
    ('sessions', 'session'),
}
SENSITIVE_FIELDS = {'password'}


def firestore_value(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode('utf-8', errors='replace')
    if hasattr(value, 'name') and not isinstance(value, (str, dict, list)):
        return value.name
    return value


class Command(BaseCommand):
    help = 'Copy Django model records from SQLite into Firestore collections'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Show records that would be copied without writing to Firestore',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        try:
            client = None if dry_run else get_firestore()
        except FirebaseNotConfigured as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        exported = 0
        collections = 0
        for model in apps.get_models():
            key = (model._meta.app_label, model._meta.model_name)
            if key in EXCLUDED_MODELS or model._meta.abstract:
                continue

            records = model.objects.all().iterator()
            collection_name = f'django_{key[0]}_{key[1]}'
            model_count = 0
            batch = client.batch() if client else None
            batch_count = 0

            for obj in records:
                payload = {}
                for field in model._meta.concrete_fields:
                    if field.name in SENSITIVE_FIELDS:
                        continue
                    value = field.value_from_object(obj)
                    payload[field.name] = firestore_value(value)
                payload['_model'] = f'{key[0]}.{key[1]}'
                payload['_sqlite_pk'] = str(obj.pk)

                if batch is not None:
                    reference = client.collection(collection_name).document(str(obj.pk))
                    batch.set(reference, payload)
                    batch_count += 1
                    if batch_count == 400:
                        batch.commit()
                        batch = client.batch()
                        batch_count = 0
                model_count += 1
                exported += 1

            if batch is not None and batch_count:
                batch.commit()
            if model_count:
                collections += 1
                action = 'would export' if dry_run else 'exported'
                self.stdout.write(
                    f'{collection_name}: {action} {model_count} record(s)'
                )

        summary = f'{exported} record(s) across {collections} collection(s)'
        self.stdout.write(self.style.SUCCESS(
            f'Dry run complete: {summary}' if dry_run else f'Firestore export complete: {summary}'
        ))