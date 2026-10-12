"""Maintenance tests."""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from accounts.models import User
from .models import Maintenance, MaintenanceStatus, MaintenanceType, MaintenancePriority


class MaintenanceModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tech1', password='pass12345', role=User.Role.OPERATOR,
        )

    def test_mark_completed(self):
        m = Maintenance.objects.create(
            title='Test Task',
            maintenance_type=MaintenanceType.CLEANING,
            status=MaintenanceStatus.SCHEDULED,
            priority=MaintenancePriority.MEDIUM,
            scheduled_date=timezone.localdate(),
            assigned_technician=self.user,
        )
        m.mark_completed(self.user)
        m.refresh_from_db()
        self.assertEqual(m.status, MaintenanceStatus.COMPLETED)
        self.assertEqual(m.completed_date, timezone.localdate())

    def test_is_overdue(self):
        m = Maintenance.objects.create(
            title='Overdue Task',
            maintenance_type=MaintenanceType.INSPECTION,
            status=MaintenanceStatus.SCHEDULED,
            priority=MaintenancePriority.HIGH,
            scheduled_date=timezone.localdate() - timedelta(days=3),
        )
        self.assertTrue(m.is_overdue)
