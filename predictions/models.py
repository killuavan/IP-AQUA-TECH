"""
Predictions for rain and turbid spring-water (malabo na bukal).
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class RiskLevel(models.TextChoices):
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'
    CRITICAL = 'CRITICAL', 'Critical'


class WeatherSnapshot(models.Model):
    """Cached weather (from Open-Meteo or demo stub)."""

    fetched_at = models.DateTimeField(default=timezone.now, db_index=True)
    source = models.CharField(
        max_length=30,
        default='open_meteo',
        help_text='open_meteo | stub | manual',
    )
    location_name = models.CharField(max_length=120, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()

    # Recent / current
    rain_last_1h_mm = models.FloatField(default=0.0)
    rain_last_24h_mm = models.FloatField(default=0.0)
    rain_next_24h_mm = models.FloatField(default=0.0)
    rain_probability_max_pct = models.FloatField(
        default=0.0,
        help_text='Max precip probability next 24h (0-100)',
    )
    will_rain_next_24h = models.BooleanField(default=False)

    humidity_pct = models.FloatField(null=True, blank=True)
    cloud_cover_pct = models.FloatField(null=True, blank=True)
    temperature_c = models.FloatField(null=True, blank=True)

    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-fetched_at']
        verbose_name = 'Weather Snapshot'
        verbose_name_plural = 'Weather Snapshots'

    def __str__(self):
        rain = 'rain' if self.will_rain_next_24h else 'no rain'
        return f'{self.fetched_at:%Y-%m-%d %H:%M} – {rain} ({self.source})'


class TurbidityRiskPrediction(models.Model):
    """
    Prediction that spring water may become turbid (malabo na bukal),
    driven by rain forecast + latest sensor readings.
    """

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    weather = models.ForeignKey(
        WeatherSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='predictions',
    )

    # Sensor inputs at prediction time
    ph = models.FloatField(null=True, blank=True)
    tds = models.FloatField(null=True, blank=True)
    turbidity = models.FloatField(null=True, blank=True)

    # Rain features used
    rain_last_24h_mm = models.FloatField(default=0.0)
    rain_next_24h_mm = models.FloatField(default=0.0)
    rain_probability_pct = models.FloatField(default=0.0)
    will_rain = models.BooleanField(default=False)

    # Outputs
    risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
    )
    turbidity_risk_score = models.FloatField(
        default=0.0,
        help_text='0–100 composite risk score',
    )
    predicted_malabo = models.BooleanField(
        default=False,
        help_text='True if model/rules expect turbid spring water',
    )
    method = models.CharField(
        max_length=30,
        default='rules',
        help_text='rules | sklearn | hybrid',
    )
    summary = models.CharField(max_length=300, blank=True)
    reasons = models.JSONField(default=list, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    details = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='turbidity_predictions',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Turbidity Risk Prediction'
        verbose_name_plural = 'Turbidity Risk Predictions'

    def __str__(self):
        flag = 'MALABO' if self.predicted_malabo else 'CLEAR'
        return f'{self.created_at:%Y-%m-%d %H:%M} – {self.risk_level} / {flag}'


class MonthlyRainLevel(models.TextChoices):
    DRY = 'DRY', 'Dry / light rain'
    MODERATE = 'MODERATE', 'Moderate rain'
    WET = 'WET', 'Wet / heavy rain month'


class MonthlyRainPrediction(models.Model):
    """
    Prediction of rainfall for a whole calendar month (ulan sa buwan).
    """

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField(help_text='1-12')

    location_name = models.CharField(max_length=120, blank=True)
    latitude = models.FloatField(default=0.0)
    longitude = models.FloatField(default=0.0)

    climate_normal_mm = models.FloatField(
        default=0.0,
        help_text='Historical average mm for this month at site',
    )
    predicted_total_mm = models.FloatField(default=0.0)
    predicted_rainy_days = models.PositiveSmallIntegerField(default=0)
    rain_level = models.CharField(
        max_length=20,
        choices=MonthlyRainLevel.choices,
        default=MonthlyRainLevel.MODERATE,
    )
    will_be_rainy_month = models.BooleanField(default=False)

    # Chance (%) na lalabo ang tubig sa bukal kapag umulan (same month, rain-driven)
    spring_dirt_probability_pct = models.FloatField(
        default=0.0,
        help_text='0–100 chance na lalabo ang tubig sa bukal pag umulan',
    )
    spring_dirt_risk_level = models.CharField(
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.LOW,
    )
    predicted_dirty_spring = models.BooleanField(
        default=False,
        help_text='True if chance of cloudy spring water is high this month',
    )
    dirt_reasons = models.JSONField(default=list, blank=True)

    method = models.CharField(max_length=40, default='climate_heuristic')
    summary = models.CharField(max_length=400, blank=True)
    recommendations = models.JSONField(default=list, blank=True)
    level_probabilities = models.JSONField(default=dict, blank=True)
    details = models.JSONField(default=dict, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='monthly_rain_predictions',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Monthly Rain Prediction'
        verbose_name_plural = 'Monthly Rain Predictions'

    def __str__(self):
        dirt = f' dirt~{self.spring_dirt_probability_pct:.0f}%' if self.spring_dirt_probability_pct else ''
        return f'{self.year}-{self.month:02d} {self.rain_level} (~{self.predicted_total_mm} mm){dirt}'

    @property
    def month_label(self) -> str:
        from calendar import month_name
        return f'{month_name[self.month]} {self.year}'
