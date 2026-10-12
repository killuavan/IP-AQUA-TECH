"""Filter management views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from notifications.models import Notification, AlertType, AlertSeverity
from .forms import FilterForm
from .models import Filter


def _filter_alerts(filt):
    if filt.needs_replacement:
        Notification.objects.create(
            title='Filter Needs Replacement',
            message=(
                f'Filter "{filt.name}" ({filt.get_filter_type_display()}) '
                f'life remaining: {filt.life_percentage}%.'
            ),
            alert_type=AlertType.FILTER,
            severity=AlertSeverity.CRITICAL,
        )
    elif float(filt.life_percentage) <= 25:
        Notification.objects.create(
            title='Filter Life Low',
            message=(
                f'Filter "{filt.name}" life remaining: {filt.life_percentage}%.'
            ),
            alert_type=AlertType.FILTER,
            severity=AlertSeverity.WARNING,
        )


@login_required
def filter_list(request):
    q = request.GET.get('q', '').strip()
    ftype = request.GET.get('type', '')
    qs = Filter.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(notes__icontains=q))
    if ftype:
        qs = qs.filter(filter_type=ftype)
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'filters/filter_list.html', {
        'page_obj': page,
        'q': q,
        'ftype': ftype,
        'filter_types': Filter.FilterType,
    })


@login_required
def filter_detail(request, pk):
    obj = get_object_or_404(Filter, pk=pk)
    return render(request, 'filters/filter_detail.html', {'object': obj})


@login_required
@require_http_methods(['GET', 'POST'])
def filter_create(request):
    form = FilterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        filt = form.save()
        _filter_alerts(filt)
        messages.success(request, 'Filter added.')
        return redirect('filters:filter_list')
    return render(request, 'filters/filter_form.html', {
        'form': form, 'title': 'Add Filter',
    })


@login_required
@require_http_methods(['GET', 'POST'])
def filter_edit(request, pk):
    obj = get_object_or_404(Filter, pk=pk)
    form = FilterForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        filt = form.save()
        _filter_alerts(filt)
        messages.success(request, 'Filter updated.')
        return redirect('filters:filter_list')
    return render(request, 'filters/filter_form.html', {
        'form': form, 'title': 'Edit Filter', 'object': obj,
    })


@login_required
@require_http_methods(['POST'])
def filter_delete(request, pk):
    obj = get_object_or_404(Filter, pk=pk)
    obj.delete()
    messages.success(request, 'Filter deleted.')
    return redirect('filters:filter_list')
