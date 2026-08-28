from django.db import models


class Translation(models.Model):
    # History is scoped to the browser session rather than a user account, so
    # there's no signup to get through and two people on the same deployment
    # don't see each other's text. Swap this for a ForeignKey to the user model
    # if you ever add accounts.
    session_key = models.CharField(max_length=40, db_index=True)

    source_text = models.TextField()
    translated_text = models.TextField()
    target_language = models.CharField(max_length=64)
    detected_language = models.CharField(max_length=64, blank=True)
    detected_language_code = models.CharField(max_length=8, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["session_key", "-created_at"])]

    def __str__(self):
        return f"{self.detected_language or 'Unknown'} to {self.target_language}: {self.preview}"

    @property
    def preview(self):
        one_line = " ".join(self.source_text.split())
        return one_line[:80] + ("..." if len(one_line) > 80 else "")
