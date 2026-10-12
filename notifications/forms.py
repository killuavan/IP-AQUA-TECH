"""
Notification forms (admin/manual alerts).
"""
from django import forms
from .models import Notification


class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['title', 'message', 'alert_type', 'severity', 'recipient']
        widgets = {
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ('alert_type', 'severity', 'recipient'):
                field.widget.attrs.update({'class': 'form-select'})
            elif name != 'message':
                field.widget.attrs.update({'class': 'form-control'})
