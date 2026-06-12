from django import forms
from .models import (
    Attendance,
    Intervention,
    Appointment,
    RiskThreshold,
    Case
)


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ["date", "present"]
        widgets = {
            "date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control"
            }),
            "present": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }


class InterventionForm(forms.ModelForm):
    class Meta:
        model = Intervention
        fields = [
            "title",
            "description",
            "recommendation_reason",
            "status"
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-control"
            }),

            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4
            }),

            "recommendation_reason": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": (
                    "Explain why this intervention is recommended."
                )
            }),

            "status": forms.Select(attrs={
                "class": "form-control"
            }),
        }


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["date", "attended", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control"
            }),
            "attended": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4
            }),
        }


class RiskThresholdForm(forms.ModelForm):
    class Meta:
        model = RiskThreshold
        fields = [
            "high_risk_threshold",
            "medium_risk_threshold"
        ]

        widgets = {
            "high_risk_threshold": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.1"
            }),
            "medium_risk_threshold": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.1"
            }),
        }


class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ["student", "title", "description", "assigned_to"]
        widgets = {
            "student": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "assigned_to": forms.Select(attrs={"class": "form-control"}),
        }


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Select CSV file",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".csv"})
    )