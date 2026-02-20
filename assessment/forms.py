from django import forms
from django.utils import timezone
from .models import Assessment

class CandidateLoginForm(forms.Form):
    email = forms.EmailField(
        label="Enter your registered email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@company.com'})
    )

class AssessmentCreateForm(forms.ModelForm):
    domain = forms.ChoiceField(choices=[], widget=forms.Select(attrs={'class': 'form-control'}))
    
    class Meta:
        model = Assessment
        fields = ['domain', 'number_of_questions', 'duration_minutes', 'start_time', 'end_time', 'cutoff_score']
        widgets = {
            'number_of_questions': forms.NumberInput(attrs={'class': 'form-control'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'cutoff_score': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        domains = kwargs.pop('domains', [])
        super().__init__(*args, **kwargs)
        self.fields['domain'].choices = [(d, d) for d in domains]
        
        # Set min date-time to current time
        now_str = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
        self.fields['start_time'].widget.attrs['min'] = now_str
        self.fields['end_time'].widget.attrs['min'] = now_str

    def clean(self):
        cleaned_data = super().clean()
        domain = cleaned_data.get('domain')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        now = timezone.now()

        if start_time and start_time < now:
            self.add_error('start_time', "Start time cannot be in the past.")

        if end_time and end_time < now:
            self.add_error('end_time', "End time cannot be in the past.")

        if start_time and end_time and end_time <= start_time:
            self.add_error('end_time', "End time must be after start time.")

        # Check for overlapping active tests for the same domain
        if domain and start_time and end_time:
            overlapping_tests = Assessment.objects.filter(
                domain=domain
            ).filter(
                # Check if new test overlaps with any existing test
                # (StartA <= EndB) and (EndA >= StartB)
                start_time__lte=end_time,
                end_time__gte=start_time
            )
            
            if overlapping_tests.exists():
                self.add_error(None, f"An active assessment already exists for '{domain}' during this time period. Please choose a different time or wait for the existing test to expire.")

        return cleaned_data
