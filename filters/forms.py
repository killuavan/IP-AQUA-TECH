"""
Filter management forms.
"""
from django import forms
from .models import Filter


class FilterForm(forms.ModelForm):
    class Meta:
        model = Filter
        fields = [
            'name', 'filter_type', 'life_percentage', 'install_date',
            'expected_lifespan_days', 'next_replacement_date', 'last_cleaned',
            'system_pressure', 'flow_status', 'is_active', 'notes',
        ]
        widgets = {
            'install_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'next_replacement_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'last_cleaned': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ('is_active',):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif name in ('filter_type',):
                field.widget.attrs.update({'class': 'form-select'})
            elif not isinstance(field.widget, forms.DateInput):
                if not isinstance(field.widget, forms.Textarea):
                    field.widget.attrs.update({'class': 'form-control'})
