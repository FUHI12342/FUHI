from django.contrib import admin
from .models import BusinessDay, ChecklistTemplateItem, ChecklistTask


class ChecklistTaskInline(admin.TabularInline):
    model = ChecklistTask
    extra = 0


@admin.register(BusinessDay)
class BusinessDayAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'status', 'opened_at', 'closed_at')
    list_filter = ('store', 'status')
    inlines = [ChecklistTaskInline]


@admin.register(ChecklistTemplateItem)
class ChecklistTemplateItemAdmin(admin.ModelAdmin):
    list_display = ('store', 'title', 'order', 'is_active')
    list_filter = ('store',)
    list_editable = ('order', 'is_active')
