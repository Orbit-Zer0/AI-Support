from django.urls import path

from .views import (
    CountryListView,
    LanguageListView,
    LoginView,
    RegisterView,
    UserSettingsView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('countries/', CountryListView.as_view(), name='countries'),
    path('languages/', LanguageListView.as_view(), name='languages'),
    path('settings/', UserSettingsView.as_view(), name='user-settings'),
]