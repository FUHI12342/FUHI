from django.contrib import admin
from .models import PostDraft, PostResult, PostTemplate


@admin.register(PostTemplate)
class PostTemplateAdmin(admin.ModelAdmin):
    list_display = ('store', 'name', 'is_active')
    list_filter = ('store',)


class PostResultInline(admin.TabularInline):
    model = PostResult
    extra = 0
    readonly_fields = ('platform', 'status', 'external_url', 'detail', 'created_at')


@admin.register(PostDraft)
class PostDraftAdmin(admin.ModelAdmin):
    list_display = ('store', 'date', 'status', 'approved_by', 'approved_at')
    list_filter = ('store', 'status')
    inlines = [PostResultInline]
