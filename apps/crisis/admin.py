from django.contrib import admin

from .models import CrisisResource, CrisisResourceText


class CrisisResourceTextInline(admin.TabularInline):
    model = CrisisResourceText
    extra = 1


@admin.register(CrisisResource)
class CrisisResourceAdmin(admin.ModelAdmin):
    list_display = (
        'country', 'phone', 'kind', 'priority', 'is_active', 'verified_at', 'verified',
    )
    list_editable = ('priority', 'is_active')
    list_filter = ('country', 'kind', 'is_active')
    inlines = [CrisisResourceTextInline]

    @admin.display(boolean=True, description='Verified')
    def verified(self, obj):
        return obj.verified_at is not None