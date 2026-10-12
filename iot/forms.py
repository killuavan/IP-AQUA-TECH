from django import forms
from .models import IoTDevice, SensorCalibration


class IoTDeviceForm(forms.ModelForm):
    class Meta:
        model = IoTDevice
        fields = [
            'name', 'device_id', 'device_type', 'firebase_path',
            'location', 'status', 'is_active', 'firmware_version', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_active':
                field.widget.attrs.update({'class': 'form-check-input'})
            elif name in ('device_type', 'status'):
                field.widget.attrs.update({'class': 'form-select'})
            elif name != 'notes':
                field.widget.attrs.update({'class': 'form-control'})


class SensorCalibrationForm(forms.ModelForm):
    class Meta:
        model = SensorCalibration
        fields = [
            'device', 'sensor_key', 'scale', 'offset',
            'min_value', 'max_value', 'is_active', 'notes',
        ]
        widgets = {
            'device': forms.Select(attrs={'class': 'form-select'}),
            'sensor_key': forms.Select(attrs={'class': 'form-select'}),
            'scale': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.0001', 'placeholder': '1.0',
            }),
            'offset': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.0001', 'placeholder': '0.0',
            }),
            'min_value': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.0001', 'placeholder': 'optional',
            }),
            'max_value': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.0001', 'placeholder': 'optional',
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. TDS offset after clean water test',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hidden_sensor_keys = {'temperature', 'water_level'}
        self.fields['sensor_key'].choices = [
            choice for choice in self.fields['sensor_key'].choices
            if choice[0] not in hidden_sensor_keys
        ]
        self.fields['device'].required = False
        self.fields['device'].empty_label = 'All devices (global)'
        self.fields['device'].queryset = IoTDevice.objects.filter(is_active=True)
        self.fields['min_value'].required = False
        self.fields['max_value'].required = False
        self.fields['notes'].required = False
