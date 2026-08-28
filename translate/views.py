import secrets

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .claude import TranslationError, translate
from .forms import TranslateForm
from .models import Translation


def unlock(request):
    """The shared-password gate. See translate/middleware.py for why it exists."""
    if not settings.APP_PASSWORD or request.session.get("unlocked"):
        return redirect("index")

    if request.method == "POST":
        # Constant-time compare, so the response time can't be used to guess
        # the password one character at a time.
        if secrets.compare_digest(request.POST.get("password", ""), settings.APP_PASSWORD):
            # Deliberately not cycling the session key here. History is scoped
            # by session key, so rotating it would orphan everything the
            # visitor had already translated.
            request.session["unlocked"] = True
            return redirect("index")
        messages.error(request, "That password isn't right.")

    return render(request, "translate/unlock.html")


def _session_key(request):
    """The current browser session's key, creating a session if there isn't one.

    A session only gets a key once something is stored in it, so a first-time
    visitor who has just posted a translation would otherwise have nothing to
    scope their history by.
    """
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _visible(request):
    return Translation.objects.filter(session_key=_session_key(request))


def index(request):
    if request.method == "POST":
        form = TranslateForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data["text"]
            target_language = form.cleaned_data["target_language"]
            try:
                result = translate(text, target_language)
            except TranslationError as exc:
                messages.error(request, str(exc))
            else:
                translation = Translation.objects.create(
                    session_key=_session_key(request),
                    source_text=text,
                    translated_text=result.translation,
                    target_language=target_language,
                    detected_language=result.detected_language,
                    detected_language_code=result.detected_language_code,
                    notes=result.notes,
                )
                # Redirect rather than render, so a refresh on the result page
                # doesn't re-run (and re-bill) the translation.
                return redirect("detail", pk=translation.pk)
    else:
        form = TranslateForm()

    return render(request, "translate/index.html", {
        "form": form,
        "recent": _visible(request)[:5],
    })


def detail(request, pk):
    translation = get_object_or_404(_visible(request), pk=pk)
    return render(request, "translate/detail.html", {"translation": translation})


def history(request):
    query = request.GET.get("q", "").strip()
    translations = _visible(request)
    if query:
        translations = translations.filter(
            Q(source_text__icontains=query)
            | Q(translated_text__icontains=query)
            | Q(target_language__icontains=query)
            | Q(detected_language__icontains=query)
        )

    return render(request, "translate/history.html", {
        "translations": translations,
        "query": query,
    })


@require_POST
def delete(request, pk):
    translation = get_object_or_404(_visible(request), pk=pk)
    translation.delete()
    messages.success(request, "Translation deleted.")
    return redirect("history")


def reuse(request, pk):
    """Load an old translation's source text back into the form to edit and rerun."""
    translation = get_object_or_404(_visible(request), pk=pk)
    form = TranslateForm(initial={
        "text": translation.source_text,
        "target_language": translation.target_language,
    })
    return render(request, "translate/index.html", {
        "form": form,
        "recent": _visible(request)[:5],
    })
