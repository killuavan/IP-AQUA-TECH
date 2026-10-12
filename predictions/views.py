"""Prediction dashboard views — next month only + auto-predict."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required

from .models import MonthlyRainPrediction, WeatherSnapshot
from .services import (
    dashboard_context,
    ensure_auto_monthly_prediction,
    run_monthly_rain_prediction,
    train_all_ml_models,
)


@login_required
def prediction_dashboard(request):
    """
    Open Predictions page and auto-run next-month ML once per day
    (if PREDICTION_AUTO_MONTHLY is enabled).
    """
    auto_pred = None
    try:
        auto_pred = ensure_auto_monthly_prediction(user=request.user)
    except Exception as exc:
        messages.warning(request, f'Auto-predict skipped: {exc}')

    ctx = dashboard_context()
    if auto_pred is not None:
        messages.info(
            request,
            f'Auto-predicted {auto_pred.month_label}: {auto_pred.rain_level} · '
            f'~{auto_pred.predicted_total_mm:.0f} mm · '
            f'cloudy chance ~{auto_pred.spring_dirt_probability_pct:.0f}%.',
        )
        ctx['auto_predicted'] = True
        ctx['auto_prediction'] = auto_pred
    else:
        ctx['auto_predicted'] = False

    return render(request, 'predictions/dashboard.html', ctx)


@login_required
@require_POST
def run_monthly(request):
    """Manual predict next month only (e.g. July now → August only)."""
    try:
        pred = run_monthly_rain_prediction(
            user=request.user,
            force_next_month_only=True,
            auto=False,
        )
        level = pred.rain_level
        dirt_pct = pred.spring_dirt_probability_pct
        msg = (
            f'{pred.month_label}: {level} · ~{pred.predicted_total_mm:.0f} mm · '
            f'~{pred.predicted_rainy_days} rainy days · '
            f'cloudy chance ~{dirt_pct:.0f}%.'
        )
        if pred.predicted_dirty_spring or level == 'WET':
            messages.warning(request, msg)
        elif level == 'DRY':
            messages.success(request, msg)
        else:
            messages.info(request, msg)
    except Exception as exc:
        messages.error(request, f'Prediction failed: {exc}')
    return redirect('predictions:dashboard')


@admin_required
@require_POST
def train_ml(request):
    try:
        result = train_all_ml_models()
        monthly = result['monthly_rain']
        cloud = result.get('spring_cloud') or monthly.get('spring_cloud') or {}
        messages.success(
            request,
            f'ML trained — Rain: acc {monthly["accuracy_level"]:.1%}; '
            f'Cloudy chance: acc {cloud.get("accuracy", 0):.1%} '
            f'(AUC {cloud.get("roc_auc", "n/a")}).',
        )
    except Exception as exc:
        messages.error(request, f'ML training failed: {exc}')
    return redirect('predictions:dashboard')


@login_required
def monthly_history(request):
    qs = MonthlyRainPrediction.objects.select_related('created_by')
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'predictions/monthly_history.html', {
        'page_obj': page,
        'predictions': page,
    })


@login_required
def weather_history(request):
    qs = WeatherSnapshot.objects.all()
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'predictions/weather_history.html', {
        'page_obj': page,
        'snapshots': page,
    })
