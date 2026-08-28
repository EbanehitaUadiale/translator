# Translator

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![Django 5.2](https://img.shields.io/badge/django-5.2-092E20?logo=django&logoColor=white)
![Claude Opus 5](https://img.shields.io/badge/Claude-Opus%205-D97757)

A Django web app that translates text with the Claude API. Paste text, pick a
target language, and get a translation back — the source language is detected
for you. Every translation is saved to a searchable history.

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

copy .env.example .env         # macOS/Linux: cp .env.example .env
# then put your key in .env:  ANTHROPIC_API_KEY=sk-ant-...

python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000.

Get an API key from https://console.anthropic.com/settings/keys. If you already
use the `ant` CLI, `ant auth login` works too — leave `ANTHROPIC_API_KEY` blank
and the SDK will pick up that profile.

## How it works

`translate/claude.py` holds the entire Claude integration; nothing else in the
project imports the SDK. One call to the Messages API does detection and
translation together, constrained by a JSON schema so the response always has
the same four fields (`translation`, `detected_language`,
`detected_language_code`, `notes`) rather than prose that has to be scraped.

Three choices worth knowing about:

- **Model and effort.** It runs `claude-opus-5` at `low` effort. Translation is
  a routine language task that doesn't reward deep deliberation, so low effort
  keeps it fast and cheap. Raise `EFFORT` in `claude.py` toward `high` for legal
  or literary text where nuance beats speed.
- **Refusal fallbacks.** Translation input can be arbitrary text, which trips
  safety classifiers more often than you'd expect. The request opts into
  server-side fallbacks, so a declined request is retried on another model
  inside the same call instead of failing in the user's face.
- **Prompt injection.** Source text is wrapped in a delimiter and the system
  prompt tells Claude to treat it as data. Text that says "ignore your
  instructions" gets translated rather than obeyed.

## History and privacy

History is scoped to the browser session, not a user account — no signup, and
two people using the same deployment don't see each other's text. Clearing
cookies loses the history. If you add accounts later, swap `session_key` on the
`Translation` model for a foreign key to the user.

## Adding a language

`LANGUAGES` in `translate/forms.py` is just a list of names shown in the
dropdown. Claude handles far more than what's listed — add a name to the list
and it works, no other changes needed.

## Tests

```bash
python manage.py test
```

21 tests, no network access required — the Anthropic client is patched
throughout, so the suite never makes a real API call or costs anything.

## Limits

Input is capped at 20,000 characters per translation (`MAX_INPUT_CHARS` in
`claude.py`), since the whole text goes in a single request. Longer documents
need chunking, which isn't built yet.
