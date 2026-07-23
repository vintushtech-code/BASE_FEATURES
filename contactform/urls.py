from django.urls import path
from .views import ContactFormView, ContactSuccessView

app_name = 'contactform'

urlpatterns = [
    path('', ContactFormView.as_view(), name='contact'),
    path('success/', ContactSuccessView.as_view(), name='success'),
]
