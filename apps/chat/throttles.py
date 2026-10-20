from rest_framework.throttling import UserRateThrottle


class ChatBurstThrottle(UserRateThrottle):
    scope = 'chat_burst'


class ChatDailyThrottle(UserRateThrottle):
    scope = 'chat_daily'