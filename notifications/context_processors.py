"""Context processor for unread notification count in navbar."""
from .models import Notification


def unread_notifications(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(
            is_read=False,
            is_resolved=False,
        ).filter(
            models_q(request.user)
        ).count()
        recent = Notification.objects.filter(
            is_resolved=False,
        ).filter(
            models_q(request.user)
        )[:5]
        return {
            'unread_notification_count': count,
            'recent_notifications': recent,
        }
    return {
        'unread_notification_count': 0,
        'recent_notifications': [],
    }


def models_q(user):
    from django.db.models import Q
    return Q(recipient__isnull=True) | Q(recipient=user)
