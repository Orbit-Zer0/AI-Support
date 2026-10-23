from django.urls import path

from .views import (
    AccountView,
    CountryListView,
    ForgotPasswordView,
    LanguageListView,
    LoginView,
    RegisterView,
    ResendVerificationView,
    ResetPasswordView,
    UserSettingsView,
    VerifyEmailView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('countries/', CountryListView.as_view(), name='countries'),
    path('languages/', LanguageListView.as_view(), name='languages'),
    path('settings/', UserSettingsView.as_view(), name='user-settings'),
    path('account/', AccountView.as_view(), name='account'),
    path('email/verify/', VerifyEmailView.as_view(), name='email-verify'),
    path('email/resend/', ResendVerificationView.as_view(), name='email-resend'),
    path('password/forgot/', ForgotPasswordView.as_view(), name='password-forgot'),
    path('password/reset/', ResetPasswordView.as_view(), name='password-reset'),
]