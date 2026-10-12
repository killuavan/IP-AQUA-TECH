"""Notification / alert views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.decorators import admin_required
from .forms import NotificationForm
from .models import Notification, AlertSeverity, AlertType


@login_required
def notification_list(request):
    severity = request.GET.get('severity', '')
    alert_type = request.GET.get('type', '')
    show = request.GET.get('show', 'active')

    qs = Notification.objects.filter(
        Q(recipient__isnull=True) | Q(recipient=request.user)
    )
    if show == 'active':
        qs = qs.filter(is_resolved=False)
    elif show == 'resolved':
        qs = qs.filter(is_resolved=True)
    if severity:
        qs = qs.filter(severity=severity)
    if alert_type:
        qs = qs.filter(alert_type=alert_type)

    paginator = Paginator(qs, 15)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'notifications/notification_list.html', {
        'page_obj': page,
        'severity': severity,
        'alert_type': alert_type,
        'show': show,
        'severity_choices': AlertSeverity,
        'type_choices': AlertType,
    })


@login_required
@require_http_methods(['POST'])
def notification_mark_read(request, pk):
    obj = get_object_or_404(Notification, pk=pk)
    obj.mark_read()
    return redirect(request.META.get('HTTP_REFERER', 'notifications:notification_list'))


@login_required
@require_http_methods(['POST'])
def notification_resolve(request, pk):
    obj = get_object_or_404(Notification, pk=pk)
    obj.resolve(request.user)
    messages.success(request, 'Alert resolved.')
    return redirect('notifications:notification_list')


@login_required
@require_http_methods(['POST'])
def notification_mark_all_read(request):
    Notification.objects.filter(
        Q(recipient__isnull=True) | Q(recipient=request.user),
        is_read=False,
    ).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notifications:notification_list')


@admin_required
@require_http_methods(['GET', 'POST'])
def notification_create(request):
    form = NotificationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Alert created.')
        return redirect('notifications:notification_list')
    return render(request, 'notifications/notification_form.html', {
        'form': form, 'title': 'Create Alert',
    })
