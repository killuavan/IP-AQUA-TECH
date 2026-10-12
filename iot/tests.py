"""IoT / Firebase integration tests (no live Firebase required)."""
import json
from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from monitoring.models import WaterQuality
from notifications.models import Notification
from solar.models import Battery, SolarSystem
from .models import IoTDevice, SensorCalibration
from .services import (
    create_demo_local_ingest, ingest_payload, mark_stale_devices_offline,
    pull_latest_from_firebase,
)
from .firebase_client import is_firebase_configured, get_web_config


class IoTServiceTest(TestCase):
    def test_demo_ingest(self):
        results = create_demo_local_ingest()
        self.assertTrue(results.get('water_quality'))
        self.assertGreaterEqual(WaterQuality.objects.count(), 1)

    def test_ingest_payload_flat(self):
        device = IoTDevice.objects.create(
            name='T', device_id='t-1', device_type='MULTI',
        )
        results = ingest_payload({
            'device_id': 't-1',
            'ph': 7.2,
            'tds': 100,
            'turbidity': 0.3,
            'temperature': 25,
            'flow_rate': 10,
            'water_pressure': 2,
            'water_level': 50,
        }, source='test')
        self.assertTrue(results.get('water_quality'))
        device.refresh_from_db()
        self.assertEqual(device.status, IoTDevice.DeviceStatus.ONLINE)

    def test_four_sensor_payload(self):
        device = IoTDevice.objects.create(
            name='Four Sensor Node', device_id='esp32-001', device_type='MULTI',
        )
        results = ingest_payload({
            'device_id': device.device_id,
            'water_quality': {
                'ph': 7.1,
                'tds': 145,
                'turbidity': 0.6,
                'temperature': 25,
                'flow_rate': 0,
                'water_pressure': 0,
                'water_level': 0,
            },
            'solar': {
                'dc_voltage': 12.4,
                'panel_current': 0,
                'power_output': 0,
                'power_consumption': 0,
            },
        }, source='api')

        self.assertTrue(results['water_quality'])
        self.assertTrue(results['solar'])
        self.assertAlmostEqual(float(WaterQuality.objects.first().ph), 7.1)
        self.assertAlmostEqual(float(SolarSystem.objects.first().panel_voltage), 12.4)

    def test_battery_sensor_payload_is_saved(self):
        results = ingest_payload({
            'device_id': 'esp32-battery',
            'battery': {
                'voltage': 12.45,
                'percentage': 72,
                'charging_status': 'DISCHARGING',
            },
        }, source='firebase')
        self.assertTrue(results['battery'])
        self.assertAlmostEqual(float(Battery.objects.get().voltage), 12.45)
        self.assertEqual(float(Battery.objects.get().percentage), 72)

    def test_solar_voltage_updates_battery_and_creates_critical_alert(self):
        Battery.objects.create(
            name='Main Battery Bank', voltage=24, percentage=71,
        )
        ingest_payload({
            'device_id': 'esp32-001',
            'solar': {
                'panel_voltage': 0.01,
                'panel_current': 0,
                'power_output': 0,
            },
        }, source='firebase')

        battery = Battery.objects.get()
        self.assertEqual(battery.status, 'CRITICAL')
        self.assertEqual(float(battery.percentage), 0)
        self.assertTrue(Notification.objects.filter(alert_type='BATTERY').exists())

    def test_level_sensor_fault_marks_device_error(self):
        device = IoTDevice.objects.create(
            name='Fault Test', device_id='fault-1', device_type='MULTI',
        )
        ingest_payload({
            'device_id': device.device_id,
            'water_quality': {
                'ph': 7,
                'tds': 100,
                'turbidity': 0.3,
                'level_sensor_fault': True,
            },
        }, source='firebase')
        device.refresh_from_db()
        self.assertEqual(device.status, IoTDevice.DeviceStatus.ERROR)

    def test_stale_device_is_marked_offline(self):
        device = IoTDevice.objects.create(
            name='Stale', device_id='stale-1', device_type='MULTI',
            status=IoTDevice.DeviceStatus.ONLINE,
            last_seen=timezone.now() - timedelta(minutes=5),
        )
        self.assertEqual(mark_stale_devices_offline(), 1)
        device.refresh_from_db()
        self.assertEqual(device.status, IoTDevice.DeviceStatus.OFFLINE)

    @patch('iot.services.read_path')
    def test_firebase_pull_imports_changed_payload_only_once(self, read_path):
        payload = {
            'ph': 7.1,
            'tds': 145,
            'turbidity': 0.6,
            'flow_rate': 9.5,
            'device_id': 'esp32-001',
            'timestamp': '2026-08-24T10:30:00Z',
        }
        read_path.return_value = {
            'water_quality': {'latest': payload},
        }

        first = pull_latest_from_firebase()
        second = pull_latest_from_firebase()

        self.assertEqual(first['imported'], 1)
        self.assertEqual(second['imported'], 0)
        self.assertEqual(second['details']['water_quality'], 'unchanged')
        self.assertEqual(WaterQuality.objects.count(), 1)


class IoTAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.device = IoTDevice.objects.create(
            name='API Device',
            device_id='api-1',
            device_type='MULTI',
        )
        self.user = User.objects.create_user(
            username='iotuser', password='pass12345', role=User.Role.OPERATOR,
        )

    def test_ingest_requires_api_key(self):
        response = self.client.post(
            reverse('iot:api_ingest'),
            data=json.dumps({'ph': 7}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401)

    def test_ingest_with_api_key(self):
        response = self.client.post(
            reverse('iot:api_ingest'),
            data=json.dumps({
                'water_quality': {
                    'ph': 7.1,
                    'tds': 120,
                    'turbidity': 0.4,
                    'temperature': 26,
                    'flow_rate': 11,
                    'water_pressure': 2.5,
                    'water_level': 60,
                }
            }),
            content_type='application/json',
            HTTP_X_API_KEY=self.device.api_key,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['ok'])

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('iot:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_loads(self):
        self.client.login(username='iotuser', password='pass12345')
        response = self.client.get(reverse('iot:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="liveFlowRate"')
        self.assertContains(response, 'id="liveWaterLevel"')
        self.assertContains(response, 'id="livePumpStatus"')
        self.assertContains(response, 'id="liveWaterAlert"')

    @patch('iot.views.is_firebase_configured', return_value=True)
    @patch('iot.views.pull_latest_from_firebase')
    def test_latest_api_returns_firebase_water_reading(self, pull_latest, _configured):
        pull_latest.return_value = {
            'readings': {
                'water_quality': {
                    'ph': 7.2,
                    'tds': 150,
                    'turbidity': 0.4,
                    'flow_rate': 12.5,
                    'water_level': 25,
                    'water_level_status': 'LOW',
                    'water_dirty': True,
                    'device_id': 'esp32-001',
                    'timestamp': '2026-08-24T10:30:00Z',
                },
                'pump': {
                    'pump_status': 'ON',
                    'flow_status': 'ON',
                    'water_level_status': 'LOW',
                    'water_dirty': True,
                    'device_id': 'esp32-001',
                    'timestamp': '2026-08-24T10:30:00Z',
                },
            },
            'imported': 1,
            'details': {'water_quality': 'imported'},
        }
        self.client.login(username='iotuser', password='pass12345')

        response = self.client.get(reverse('iot:latest_live'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['readings']['water_quality']['payload']['flow_rate'],
            12.5,
        )
        self.assertTrue(response.json()['firebase_live'])
        self.assertEqual(
            response.json()['readings']['pump']['payload']['pump_status'],
            'ON',
        )
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_adjust_sensors_hides_temperature_and_water_level(self):
        SensorCalibration.objects.create(sensor_key='temperature')
        SensorCalibration.objects.create(sensor_key='water_level')
        self.client.login(username='iotuser', password='pass12345')

        response = self.client.get(reverse('iot:sensor_calibration_list'))

        self.assertEqual(response.status_code, 200)
        visible_keys = [row['cal'].sensor_key for row in response.context['rows']]
        self.assertNotIn('temperature', visible_keys)
        self.assertNotIn('water_level', visible_keys)
        self.assertContains(response, 'Flow Rate')

    def test_adjust_sensor_form_excludes_temperature_and_water_level(self):
        self.client.login(username='iotuser', password='pass12345')

        response = self.client.get(reverse('iot:sensor_calibration_create'))

        choices = dict(response.context['form'].fields['sensor_key'].choices)
        self.assertNotIn('temperature', choices)
        self.assertNotIn('water_level', choices)

    @override_settings(FIREBASE_CREDENTIALS_PATH='missing-firebase-credentials.json')
    def test_web_config(self):
        cfg = get_web_config()
        self.assertIn('databaseURL', cfg)
        # Without credentials file, configured flag for admin is false
        self.assertFalse(is_firebase_configured())
