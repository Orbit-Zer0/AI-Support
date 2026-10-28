from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

class AuthThrottle(AnonRateThrottle):
    scope = 'auth'

class SettingsThrottle(UserRateThrottle):
    scope = 'settings'

class EmailResendThrottle(UserRateThrottle):
    scope = 'email_resend'

class SensitiveActionThrottle(UserRateThrottle):
    scope = 'sensitive'

class ExportThrottle(UserRateThrottle):
    scope = 'export'

class ImportThrottle(UserRateThrottle):
    scope = 'import'

class AvatarThrottle(UserRateThrottle):
    scope = 'avatar'
    scope = 'import'