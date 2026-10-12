"""Seed default IoT devices for IP Aqua Tech."""
from django.core.management.base import BaseCommand
from iot.models import IoTDevice


class Command(BaseCommand):
    help = 'Create default IoT device entries'

    def handle(self, *args, **options):
        devices = [
            {
                'device_id': 'esp32-001',
                'name': 'Main Multi-Sensor Node',
                'device_type': IoTDevice.DeviceType.MULTI,
                'location': 'Filtration Unit',
                'firmware_version': '1.0.0',
            },
            {
                'device_id': 'esp32-demo',
                'name': 'Demo ESP32 Node',
                'device_type': IoTDevice.DeviceType.MULTI,
                'location': 'Lab / Demo',
                'firmware_version': 'demo-1.0',
            },
        ]
        for data in devices:
            obj, created = IoTDevice.objects.get_or_create(
                device_id=data['device_id'],
                defaults=data,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f'Created {obj.device_id} | API Key: {obj.api_key}'
                ))
            else:
                self.stdout.write(
                    f'Exists {obj.device_id} | API Key: {obj.api_key}'
                )
