from django.contrib import admin

from .models import MonthlyRainPrediction, TurbidityRiskPrediction, WeatherSnapshot


@admin.register(WeatherSnapshot)
class WeatherSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'fetched_at',
        'location_name',
        'source',
        'will_rain_next_24h',
        'rain_last_24h_mm',
        'rain_next_24h_mm',
        'rain_probability_max_pct',
    )
    list_filter = ('source', 'will_rain_next_24h')
    readonly_fields = ('raw_payload',)


@admin.register(TurbidityRiskPrediction)
class TurbidityRiskPredictionAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'risk_level',
        'predicted_malabo',
        'turbidity_risk_score',
        'will_rain',
        'turbidity',
        'method',
    )
    list_filter = ('risk_level', 'predicted_malabo', 'method', 'will_rain')
    readonly_fields = ('reasons', 'recommendations', 'details')


@admin.register(MonthlyRainPrediction)
class MonthlyRainPredictionAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'year',
        'month',
        'rain_level',
        'predicted_total_mm',
        'predicted_rainy_days',
        'spring_dirt_probability_pct',
        'spring_dirt_risk_level',
        'predicted_dirty_spring',
        'will_be_rainy_month',
        'method',
    )
    list_filter = (
        'rain_level',
        'spring_dirt_risk_level',
        'predicted_dirty_spring',
        'will_be_rainy_month',
        'method',
        'year',
    )
    readonly_fields = ('recommendations', 'level_probabilities', 'dirt_reasons', 'details')
