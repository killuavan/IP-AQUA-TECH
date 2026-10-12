"""
Solar and battery forms.
"""
from django import forms
from .models import SolarSystem, Battery, SolarEnergyLog


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


class SolarSystemForm(BootstrapModelForm):
    class Meta:
        model = SolarSystem
        fields = [
            'panel_voltage', 'panel_current', 'power_output',
            'power_consumption', 'irradiance', 'panel_temperature',
            'notes', 'recorded_at',
        ]
        widgets = {
            'recorded_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'},
                format='%Y-%m-%dT%H:%M',
            ),
        }


class BatteryForm(BootstrapModelForm):
    class Meta:
        model = Battery
        fields = [
            'name', 'voltage', 'percentage', 'charging_status',
            'capacity_ah', 'temperature', 'health_percent',
            'cycle_count', 'notes',
        ]


class SolarEnergyLogForm(BootstrapModelForm):
    class Meta:
        model = SolarEnergyLog
        fields = [
            'date', 'energy_generated_kwh', 'peak_power_w',
            'average_power_w', 'sunshine_hours',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
