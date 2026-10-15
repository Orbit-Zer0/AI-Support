from django.contrib import admin

from .models import Country, Language, UserProfile


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    list_editable = ('is_active',)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('code', 'name')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'country', 'language', 'created_at')