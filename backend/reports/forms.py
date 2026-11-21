from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Claim, Profile, Report


class AccountRegistrationForm(UserCreationForm):
    email = forms.EmailField()
    full_name = forms.CharField(max_length=100)
    ram_id = forms.CharField(max_length=9, required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'full_name', 'ram_id', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if not email.endswith('@farmingdale.edu'):
            raise ValidationError('Use an @farmingdale.edu email address.')
        return email

    def clean_ram_id(self):
        ram_id = self.cleaned_data['ram_id'].strip().upper()
        if ram_id:
            import re
            if not re.fullmatch(r'R\d{8}', ram_id):
                raise ValidationError('RAM ID must be R followed by 8 digits.')
        return ram_id

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            Profile.objects.create(
                user=user,
                full_name=self.cleaned_data['full_name'],
                ram_id=self.cleaned_data['ram_id'],
            )
        return user


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = (
            'report_type', 'full_name', 'email', 'student_id', 'phone',
            'category', 'item_name', 'description', 'estimated_value',
            'incident_date', 'incident_time', 'campus_location',
            'location_details', 'liability_accepted',
        )
        widgets = {
            'incident_date': forms.DateInput(attrs={'type': 'date'}),
            'incident_time': forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 5}),
            'location_details': forms.Textarea(attrs={'rows': 4}),
        }


class ClaimForm(forms.ModelForm):
    class Meta:
        model = Claim
        fields = ('match', 'verification_answers')
