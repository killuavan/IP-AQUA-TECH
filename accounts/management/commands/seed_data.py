"""
Seed sample data for IP Aqua Tech monitoring system.

Usage:
    python manage.py seed_data
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from dashboard.models import SystemConfig
from filters.models import Filter
from maintenance.models import Maintenance, MaintenanceType, MaintenanceStatus, MaintenancePriority
from monitoring.models import WaterQuality, WaterTank, Pump, WaterProduction
from notifications.models import Notification, AlertType, AlertSeverity
from solar.models import SolarSystem, Battery, SolarEnergyLog, ChargingStatus


class Command(BaseCommand):
    help = 'Seed sample data for IP Aqua Tech'

    def handle(self, *args, **options):
        self.stdout.write('Seeding IP Aqua Tech sample data...')

        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@ipaquatech.local',
                'first_name': 'System',
                'last_name': 'Administrator',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(self.style.SUCCESS('  Created admin / admin123'))
        else:
            self.stdout.write('  Admin already exists')

        operator, created = User.objects.get_or_create(
            username='operator',
            defaults={
                'email': 'operator@ipaquatech.local',
                'first_name': 'Juan',
                'last_name': 'Operator',
                'role': User.Role.OPERATOR,
                'phone': '+63-912-345-6789',
            },
        )
        if created:
            operator.set_password('operator123')
            operator.save()
            self.stdout.write(self.style.SUCCESS('  Created operator / operator123'))

        tech, created = User.objects.get_or_create(
            username='technician',
            defaults={
                'email': 'tech@ipaquatech.local',
                'first_name': 'Maria',
                'last_name': 'Santos',
                'role': User.Role.OPERATOR,
                'phone': '+63-917-111-2222',
            },
        )
        if created:
            tech.set_password('tech123')
            tech.save()

        SystemConfig.objects.get_or_create(
            name='IP Aqua Tech System',
            defaults={
                'overall_status': SystemConfig.OverallStatus.OPERATIONAL,
                'location': 'Barangay Sample Site, Philippines',
                'description': 'Solar-powered drinking water filtration monitoring system.',
                'is_active': True,
            },
        )

        # Filters
        if not Filter.objects.exists():
            filters_data = [
                ('Sediment Pre-Filter', 'SEDIMENT', 78, 180),
                ('Activated Carbon Filter', 'CARBON', 62, 180),
                ('RO Membrane', 'RO', 45, 365),
                ('UV Lamp', 'UV', 88, 365),
                ('Post-Carbon Filter', 'CARBON', 15, 90),
            ]
            today = timezone.now().date()
            for name, ftype, life, days in filters_data:
                Filter.objects.create(
                    name=name,
                    filter_type=ftype,
                    life_percentage=life,
                    install_date=today - timedelta(days=int(days * (100 - life) / 100)),
                    expected_lifespan_days=days,
                    last_cleaned=today - timedelta(days=14),
                    system_pressure=round(random.uniform(0.5, 2.5), 2),
                    flow_status='Normal' if life > 25 else 'Reduced',
                    is_active=True,
                )
            self.stdout.write(self.style.SUCCESS('  Created filters'))

        # Tank
        if not WaterTank.objects.exists():
            WaterTank.objects.create(
                name='Main Storage Tank',
                capacity_liters=2000,
                current_level_percent=72,
                location='Rooftop Reservoir',
            )
            WaterTank.objects.create(
                name='Distribution Tank',
                capacity_liters=500,
                current_level_percent=55,
                location='Ground Level',
            )
            self.stdout.write(self.style.SUCCESS('  Created water tanks'))

        # Pump
        if not Pump.objects.exists():
            Pump.objects.create(
                name='Main Feed Pump',
                pump_status='ON',
                uv_sterilizer_status='ON',
                system_pressure=3.2,
                flow_status='ON',
                power_consumption=180,
                runtime_hours=1240,
            )
            self.stdout.write(self.style.SUCCESS('  Created pumps'))

        # Battery
        if not Battery.objects.exists():
            Battery.objects.create(
                name='Main Battery Bank',
                voltage=24.6,
                percentage=78,
                charging_status=ChargingStatus.CHARGING,
                capacity_ah=200,
                temperature=28.5,
                health_percent=94,
                cycle_count=312,
            )
            self.stdout.write(self.style.SUCCESS('  Created batteries'))

        # Historical water quality (14 days)
        if WaterQuality.objects.count() < 10:
            now = timezone.now()
            for i in range(20):
                ts = now - timedelta(hours=i * 8)
                ph = round(random.uniform(6.3, 8.2), 2)
                tds = round(random.uniform(80, 420), 1)
                turb = round(random.uniform(0.1, 3.5), 2)
                WaterQuality.objects.create(
                    ph=ph,
                    tds=tds,
                    turbidity=turb,
                    temperature=round(random.uniform(22, 34), 1),
                    flow_rate=round(random.uniform(5, 25), 1),
                    water_pressure=round(random.uniform(1.5, 4.5), 2),
                    water_level=round(random.uniform(40, 95), 1),
                    recorded_by=operator,
                    recorded_at=ts,
                )
            # One critical sample
            WaterQuality.objects.create(
                ph=5.5,
                tds=620,
                turbidity=6.2,
                temperature=36,
                flow_rate=2.1,
                water_pressure=0.8,
                water_level=35,
                recorded_by=admin,
                recorded_at=now - timedelta(hours=2),
                notes='Simulated abnormal reading for demo',
            )
            self.stdout.write(self.style.SUCCESS('  Created water quality readings'))

        # Solar readings
        if SolarSystem.objects.count() < 5:
            now = timezone.now()
            for i in range(15):
                ts = now - timedelta(hours=i * 4)
                v = round(random.uniform(18, 36), 1)
                a = round(random.uniform(2, 12), 2)
                SolarSystem.objects.create(
                    panel_voltage=v,
                    panel_current=a,
                    power_output=round(v * a, 1),
                    power_consumption=round(random.uniform(80, 200), 1),
                    irradiance=round(random.uniform(200, 1000), 0),
                    panel_temperature=round(random.uniform(30, 55), 1),
                    recorded_by=operator,
                    recorded_at=ts,
                )
            self.stdout.write(self.style.SUCCESS('  Created solar readings'))

        # Production + energy logs (14 days)
        today = timezone.now().date()
        for i in range(14):
            d = today - timedelta(days=i)
            WaterProduction.objects.get_or_create(
                date=d,
                defaults={
                    'daily_production_liters': round(random.uniform(350, 650), 1),
                    'target_liters': 500,
                    'recorded_by': operator,
                },
            )
            SolarEnergyLog.objects.get_or_create(
                date=d,
                defaults={
                    'energy_generated_kwh': round(random.uniform(2.5, 8.5), 3),
                    'peak_power_w': round(random.uniform(250, 450), 1),
                    'average_power_w': round(random.uniform(100, 250), 1),
                    'sunshine_hours': round(random.uniform(4, 10), 1),
                },
            )
        self.stdout.write(self.style.SUCCESS('  Created production & energy logs'))

        # Maintenance
        if not Maintenance.objects.exists():
            Maintenance.objects.create(
                title='Replace Post-Carbon Filter',
                maintenance_type=MaintenanceType.FILTER_REPLACEMENT,
                description='Post-carbon filter life below 20%. Schedule replacement.',
                status=MaintenanceStatus.SCHEDULED,
                priority=MaintenancePriority.HIGH,
                scheduled_date=today + timedelta(days=3),
                assigned_technician=tech,
                related_filter=Filter.objects.filter(life_percentage__lte=25).first(),
                created_by=admin,
            )
            Maintenance.objects.create(
                title='Monthly System Cleaning',
                maintenance_type=MaintenanceType.CLEANING,
                description='Clean sediment housing and check O-rings.',
                status=MaintenanceStatus.SCHEDULED,
                priority=MaintenancePriority.MEDIUM,
                scheduled_date=today + timedelta(days=7),
                assigned_technician=operator,
                created_by=admin,
            )
            Maintenance.objects.create(
                title='UV Lamp Inspection',
                maintenance_type=MaintenanceType.UV_SERVICE,
                description='Quarterly UV sterilizer inspection.',
                status=MaintenanceStatus.COMPLETED,
                priority=MaintenancePriority.LOW,
                scheduled_date=today - timedelta(days=10),
                completed_date=today - timedelta(days=9),
                assigned_technician=tech,
                created_by=admin,
                cost=Decimal('1500.00'),
            )
            Maintenance.objects.create(
                title='Sensor Calibration',
                maintenance_type=MaintenanceType.CALIBRATION,
                description='Calibrate pH and TDS sensors.',
                status=MaintenanceStatus.OVERDUE,
                priority=MaintenancePriority.URGENT,
                scheduled_date=today - timedelta(days=5),
                assigned_technician=tech,
                created_by=admin,
            )
            self.stdout.write(self.style.SUCCESS('  Created maintenance tasks'))

        # Notifications
        if Notification.objects.count() < 3:
            Notification.objects.create(
                title='Filter Life Low – Post-Carbon',
                message='Post-Carbon Filter life remaining is 15%. Schedule replacement soon.',
                alert_type=AlertType.FILTER,
                severity=AlertSeverity.WARNING,
            )
            Notification.objects.create(
                title='Water Quality Critical Reading',
                message='Abnormal pH and TDS detected in latest sensor reading. Investigate immediately.',
                alert_type=AlertType.WATER_QUALITY,
                severity=AlertSeverity.CRITICAL,
            )
            Notification.objects.create(
                title='Maintenance Overdue',
                message='Sensor Calibration task is overdue by 5 days.',
                alert_type=AlertType.MAINTENANCE,
                severity=AlertSeverity.WARNING,
            )
            Notification.objects.create(
                title='System Operational',
                message='All primary systems are online and producing water normally.',
                alert_type=AlertType.SYSTEM,
                severity=AlertSeverity.INFO,
                is_read=True,
            )
            self.stdout.write(self.style.SUCCESS('  Created notifications'))

        self.stdout.write(self.style.SUCCESS('\nSample data seeded successfully!'))
        self.stdout.write('Login credentials:')
        self.stdout.write('  Admin:    admin / admin123')
        self.stdout.write('  Operator: operator / operator123')
        self.stdout.write('  Tech:     technician / tech123')
