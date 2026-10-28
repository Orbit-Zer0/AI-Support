from django.urls import path

from .account_views import (
    AccountView,
    AvatarView,
    ChangeEmailView,
    ChangePasswordView,
    DeleteAccountView,
    ExportDataView,
    ExportReadableView,
    ImportDataView,
    LogoutAllView,
)
from .views import (
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
    path('email/verify/', VerifyEmailView.as_view(), name='email-verify'),
    path('email/resend/', ResendVerificationView.as_view(), name='email-resend'),
    path('password/forgot/', ForgotPasswordView.as_view(), name='password-forgot'),
    path('password/reset/', ResetPasswordView.as_view(), name='password-reset'),

    path('account/', AccountView.as_view(), name='account'),
    path('account/avatar/', AvatarView.as_view(), name='account-avatar'),
    path('account/email/', ChangeEmailView.as_view(), name='account-email'),
    path('account/password/', ChangePasswordView.as_view(), name='account-password'),
    path('account/export/', ExportDataView.as_view(), name='account-export'),
    path('account/export/readable/', ExportReadableView.as_view(), name='account-export-readable'),
    path('account/import/', ImportDataView.as_view(), name='account-import'),
    path('account/logout-all/', LogoutAllView.as_view(), name='account-logout-all'),
    path('account/delete/', DeleteAccountView.as_view(), name='account-delete'),
]