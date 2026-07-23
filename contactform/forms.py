import time
from django import forms
from django.core.exceptions import ValidationError
from django.core.signing import Signer, BadSignature
from django.conf import settings
from .models import ContactSubmission

class ContactForm(forms.ModelForm):
    # Honeypot field - invisible to genuine users, but attractive to bots
    # We name it 'website' to trick spam bots into filling it out.
    website = forms.CharField(
        required=False,
        label='',
        widget=forms.TextInput(attrs={
            'style': 'display:none !important;',
            'tabindex': '-1',
            'autocomplete': 'off',
        })
    )
    
    # Secure, cryptographic signed timestamp to detect instant submissions (bots)
    submission_security = forms.CharField(
        widget=forms.HiddenInput()
    )

    class Meta:
        model = ContactSubmission
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Your Name',
                'required': 'required'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'your.email@example.com',
                'required': 'required'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Subject of inquiry',
                'required': 'required'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Write your message here...',
                'rows': 5,
                'required': 'required'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sign the current time and assign to submission_security field
        signer = Signer()
        current_time = str(int(time.time()))
        self.fields['submission_security'].initial = signer.sign(current_time)

    def clean_website(self):
        """
        Check that the honeypot field is empty.
        If it contains any value, it is a bot submission.
        """
        honeypot = self.cleaned_data.get('website')
        if honeypot:
            raise ValidationError("Spam detected.")
        return honeypot

    def clean(self):
        cleaned_data = super().clean()
        
        # Verify submission time
        security_token = cleaned_data.get('submission_security')
        if not security_token:
            raise ValidationError("Security validation token missing.")

        signer = Signer()
        try:
            unsigned_time = signer.unsign(security_token)
            timestamp = int(unsigned_time)
        except (BadSignature, ValueError):
            raise ValidationError("Security validation failed.")

        current_time = int(time.time())
        duration = current_time - timestamp
        
        # Get threshold from settings or default to 3 seconds
        min_seconds = getattr(settings, 'CONTACT_FORM_MIN_SUBMIT_TIME', 3)
        if duration < min_seconds:
            raise ValidationError("Form submitted too quickly. Please try again.")
            
        return cleaned_data
