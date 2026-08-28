from django import forms

from .claude import MAX_INPUT_CHARS

# The languages offered in the dropdown. Claude handles far more than this --
# add any language here by name and it will work, no other code changes needed.
LANGUAGES = [
    "Arabic", "Bengali", "Chinese (Simplified)", "Chinese (Traditional)", "Czech",
    "Danish", "Dutch", "English", "Finnish", "French", "German", "Greek", "Hausa",
    "Hebrew", "Hindi", "Hungarian", "Igbo", "Indonesian", "Italian", "Japanese",
    "Korean", "Malay", "Norwegian", "Persian", "Polish", "Portuguese (Brazil)",
    "Portuguese (Portugal)", "Romanian", "Russian", "Spanish", "Swahili", "Swedish",
    "Tagalog", "Thai", "Turkish", "Ukrainian", "Urdu", "Vietnamese", "Yoruba", "Zulu",
]

LANGUAGE_CHOICES = [(name, name) for name in LANGUAGES]


class TranslateForm(forms.Form):
    text = forms.CharField(
        label="Text to translate",
        max_length=MAX_INPUT_CHARS,
        widget=forms.Textarea(attrs={
            "rows": 10,
            "placeholder": "Paste or type anything. The source language is detected for you.",
            "autofocus": True,
        }),
    )
    target_language = forms.ChoiceField(
        label="Translate into",
        choices=LANGUAGE_CHOICES,
        initial="English",
    )
