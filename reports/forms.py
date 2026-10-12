"""
Report generation forms.
"""
from django import forms
from .models import Report, ReportType, ReportFormat


class ReportGenerateForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    report_type = forms.ChoiceField(
        choices=ReportType.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    report_format = forms.ChoiceField(
        choices=ReportFormat.choices,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and start > end:
            raise forms.ValidationError('Start date must be before or equal to end date.')
        return cleaned
