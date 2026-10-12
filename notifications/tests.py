"""Notification tests."""
from django.test import TestCase
from accounts.models import User
from .models import Notification, AlertType, AlertSeverity


class NotificationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='nuser', password='pass12345', role=User.Role.OPERATOR,
        )

    def test_mark_read_and_resolve(self):
        n = Notification.objects.create(
            title='Test Alert',
            message='Something happened',
            alert_type=AlertType.SYSTEM,
            severity=AlertSeverity.WARNING,
        )
        self.assertFalse(n.is_read)
        n.mark_read()
        self.assertTrue(n.is_read)
        n.resolve(self.user)
        self.assertTrue(n.is_resolved)
        self.assertEqual(n.resolved_by, self.user)
