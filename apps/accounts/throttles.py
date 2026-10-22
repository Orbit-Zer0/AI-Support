from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

class AuthThrottle(AnonRateThrottle):
    scope = 'auth'

class SettingsThrottle(UserRateThrottle):
    scope = 'settings'