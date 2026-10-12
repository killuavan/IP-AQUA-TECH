"""Maintenance management views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import MaintenanceForm
from .models import Maintenance, MaintenanceStatus


@login_required
def maintenance_list(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    qs = Maintenance.objects.select_related(
        'assigned_technician', 'related_filter', 'created_by'
    ).all()
    # Auto-flag overdue
    for task in qs.filter(
        status__in=[MaintenanceStatus.SCHEDULED, MaintenanceStatus.IN_PROGRESS]
    ):
        if task.check_overdue():
            task.save(update_fields=['status'])

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if status:
        qs = qs.filter(status=status)
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'maintenance/maintenance_list.html', {
        'page_obj': page,
        'q': q,
        'status': status,
        'status_choices': MaintenanceStatus,
    })


@login_required
def maintenance_detail(request, pk):
    obj = get_object_or_404(
        Maintenance.objects.select_related(
            'assigned_technician', 'related_filter', 'created_by'
        ),
        pk=pk,
    )
    return render(request, 'maintenance/maintenance_detail.html', {'object': obj})


@login_required
@require_http_methods(['GET', 'POST'])
def maintenance_create(request):
    form = MaintenanceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        messages.success(request, 'Maintenance task created.')
        return redirect('maintenance:maintenance_list')
    return render(request, 'maintenance/maintenance_form.html', {
        'form': form, 'title': 'Schedule Maintenance',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def maintenance_edit(request, pk):
    obj = get_object_or_404(Maintenance, pk=pk)
    form = MaintenanceForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Maintenance task updated.')
        return redirect('maintenance:maintenance_list')
    return render(request, 'maintenance/maintenance_form.html', {
        'form': form, 'title': 'Edit Maintenance', 'object': obj,
    })


@login_required
@require_http_methods(['POST'])
def maintenance_complete(request, pk):
    obj = get_object_or_404(Maintenance, pk=pk)
    obj.mark_completed(request.user)
    messages.success(request, 'Maintenance marked as completed.')
    return redirect('maintenance:maintenance_detail', pk=pk)


@login_required
@require_http_methods(['POST'])
def maintenance_delete(request, pk):
    obj = get_object_or_404(Maintenance, pk=pk)
    obj.delete()
    messages.success(request, 'Maintenance task deleted.')
    return redirect('maintenance:maintenance_list')
