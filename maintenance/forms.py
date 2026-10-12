"""
Maintenance task forms.
"""
from django import forms
from .models import Maintenance


class MaintenanceForm(forms.ModelForm):
    class Meta:
        model = Maintenance
        fields = [
            'title', 'maintenance_type', 'description', 'status', 'priority',
            'scheduled_date', 'completed_date', 'assigned_technician',
            'related_filter', 'cost', 'notes',
        ]
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'completed_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in (
                'maintenance_type', 'status', 'priority',
                'assigned_technician', 'related_filter',
            ):
                field.widget.attrs.update({'class': 'form-select'})
            elif name not in ('description', 'notes', 'scheduled_date', 'completed_date'):
                field.widget.attrs.update({'class': 'form-control'})
