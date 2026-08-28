from django.contrib import admin

from .models import Translation


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ["preview", "detected_language", "target_language", "created_at"]
    list_filter = ["target_language", "detected_language"]
    search_fields = ["source_text", "translated_text"]
    readonly_fields = ["created_at"]
