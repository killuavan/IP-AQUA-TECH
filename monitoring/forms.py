"""
Water quality, tank, pump, and production forms.
"""
from django import forms
from .models import MonitoringThreshold, WaterQuality, WaterTank, Pump, WaterProduction


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control', 'rows': 3})
            else:
                field.widget.attrs.update({'class': 'form-control'})


class WaterQualityForm(BootstrapModelForm):
    class Meta:
        model = WaterQuality
        fields = [
            'ph', 'tds', 'turbidity', 'temperature',
            'flow_rate', 'water_pressure', 'water_level', 'notes', 'recorded_at',
        ]
        widgets = {
            'recorded_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'},
                format='%Y-%m-%dT%H:%M',
            ),
        }


class MonitoringThresholdForm(BootstrapModelForm):
    class Meta:
        model = MonitoringThreshold
        exclude = ['updated_at']
        widgets = {
            name: forms.NumberInput(attrs={'step': '0.1'})
            for name in [
                'ph_normal_min', 'ph_normal_max', 'ph_danger_min', 'ph_danger_max',
                'tds_normal_max', 'tds_danger_max', 'turbidity_normal_max',
                'turbidity_danger_max', 'battery_warning_percent',
                'battery_critical_percent', 'battery_empty_voltage',
                'battery_full_voltage', 'device_offline_seconds',
            ]
        }

    def clean(self):
        cleaned = super().clean()
        checks = [
            ('ph_danger_min', 'ph_normal_min', 'pH danger minimum must be below normal minimum.'),
            ('ph_normal_max', 'ph_danger_max', 'pH danger maximum must be above normal maximum.'),
            ('tds_normal_max', 'tds_danger_max', 'TDS danger maximum must be above normal maximum.'),
            ('turbidity_normal_max', 'turbidity_danger_max', 'Turbidity danger maximum must be above normal maximum.'),
            ('battery_critical_percent', 'battery_warning_percent', 'Battery warning must be above critical.'),
            ('battery_empty_voltage', 'battery_full_voltage', 'Battery full voltage must be above empty voltage.'),
        ]
        for lower, upper, message in checks:
            if cleaned.get(lower) is not None and cleaned.get(upper) is not None:
                if cleaned[lower] >= cleaned[upper]:
                    raise forms.ValidationError(message)
        for field_name in ('ph_danger_min', 'ph_normal_min', 'ph_normal_max', 'ph_danger_max'):
            value = cleaned.get(field_name)
            if value is not None and not 0 <= value <= 14:
                self.add_error(field_name, 'pH must be between 0 and 14.')
        for field_name in ('battery_critical_percent', 'battery_warning_percent'):
            value = cleaned.get(field_name)
            if value is not None and not 0 <= value <= 100:
                self.add_error(field_name, 'Battery percentage must be between 0 and 100.')
        if cleaned.get('device_offline_seconds') is not None:
            if cleaned['device_offline_seconds'] < 10:
                self.add_error('device_offline_seconds', 'Use at least 10 seconds.')
        return cleaned


class WaterTankForm(BootstrapModelForm):
    class Meta:
        model = WaterTank
        fields = [
            'name', 'capacity_liters', 'current_level_percent', 'location',
        ]


class PumpForm(BootstrapModelForm):
    class Meta:
        model = Pump
        fields = [
            'name', 'pump_status', 'uv_sterilizer_status',
            'system_pressure', 'flow_status', 'power_consumption',
            'runtime_hours', 'notes',
        ]


class WaterProductionForm(BootstrapModelForm):
    class Meta:
        model = WaterProduction
        fields = ['date', 'daily_production_liters', 'target_liters', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
