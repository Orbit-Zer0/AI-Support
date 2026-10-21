from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('', TemplateView.as_view(template_name='chat/index.html'), name='index'),
    path('admin/', admin.site.urls),
    path('api/', include('apps.chat.urls')),
    path('api/', include('apps.accounts.urls')),
    path('api/', include('apps.crisis.urls')),
]