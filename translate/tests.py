import json
from unittest.mock import MagicMock, patch

import anthropic
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .claude import MAX_INPUT_CHARS, TranslationError, TranslationResult, translate
from .models import Translation


def fake_api_response(payload, stop_reason="end_turn"):
    """A stand-in for a Messages API response carrying one JSON text block."""
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)

    response = MagicMock()
    response.content = [block]
    response.stop_reason = stop_reason
    return response


GOOD_PAYLOAD = {
    "detected_language": "Spanish",
    "detected_language_code": "es",
    "translation": "Good morning",
    "notes": "",
}


def patch_api(**kwargs):
    """Patch the Anthropic client so no test ever makes a real API call."""
    return patch("translate.claude.anthropic.Anthropic", **kwargs)


class TranslateTests(TestCase):
    def _run(self, response=None, side_effect=None, text="Buenos dias", target="English"):
        client = MagicMock()
        if side_effect is not None:
            client.beta.messages.create.side_effect = side_effect
        else:
            client.beta.messages.create.return_value = response
        with patch_api(return_value=client):
            return translate(text, target), client

    def test_returns_the_translation_and_detected_language(self):
        result, _ = self._run(fake_api_response(GOOD_PAYLOAD))
        self.assertIsInstance(result, TranslationResult)
        self.assertEqual(result.translation, "Good morning")
        self.assertEqual(result.detected_language, "Spanish")
        self.assertEqual(result.detected_language_code, "es")

    def test_sends_the_target_language_and_source_text(self):
        _, client = self._run(fake_api_response(GOOD_PAYLOAD), target="French")
        sent = client.beta.messages.create.call_args.kwargs
        content = sent["messages"][0]["content"]
        self.assertIn("French", content)
        self.assertIn("Buenos dias", content)

    def test_constrains_the_response_to_the_json_schema(self):
        _, client = self._run(fake_api_response(GOOD_PAYLOAD))
        output_config = client.beta.messages.create.call_args.kwargs["output_config"]
        self.assertEqual(output_config["format"]["type"], "json_schema")
        self.assertFalse(output_config["format"]["schema"]["additionalProperties"])

    def test_asks_for_a_fallback_model_if_the_request_is_declined(self):
        _, client = self._run(fake_api_response(GOOD_PAYLOAD))
        sent = client.beta.messages.create.call_args.kwargs
        self.assertEqual(sent["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", sent["betas"])

    def test_empty_input_is_rejected_before_calling_the_api(self):
        client = MagicMock()
        with patch_api(return_value=client), self.assertRaises(TranslationError):
            translate("   ", "English")
        client.beta.messages.create.assert_not_called()

    def test_oversized_input_is_rejected_before_calling_the_api(self):
        client = MagicMock()
        with patch_api(return_value=client), self.assertRaises(TranslationError) as ctx:
            translate("x" * (MAX_INPUT_CHARS + 1), "English")
        client.beta.messages.create.assert_not_called()
        self.assertIn("smaller pieces", str(ctx.exception))

    def test_a_refusal_is_reported_rather_than_parsed(self):
        response = fake_api_response(GOOD_PAYLOAD, stop_reason="refusal")
        with self.assertRaises(TranslationError) as ctx:
            self._run(response)
        self.assertIn("declined", str(ctx.exception))

    def test_unparseable_body_becomes_a_translation_error(self):
        block = MagicMock()
        block.type = "text"
        block.text = "not json at all"
        response = MagicMock(content=[block], stop_reason="end_turn")
        with self.assertRaises(TranslationError):
            self._run(response)

    def test_a_bad_api_key_explains_itself(self):
        error = anthropic.AuthenticationError(
            "bad key", response=MagicMock(status_code=401, headers={}), body=None
        )
        with self.assertRaises(TranslationError) as ctx:
            self._run(side_effect=error)
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    def test_missing_credentials_explain_themselves_instead_of_500ing(self):
        # The SDK raises a bare TypeError when it can't resolve any credentials.
        error = TypeError(
            "Could not resolve authentication method. Expected one of api_key, "
            "auth_token, or credentials to be set."
        )
        with self.assertRaises(TranslationError) as ctx:
            self._run(side_effect=error)
        self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))

    def test_an_unrelated_type_error_is_not_swallowed(self):
        with self.assertRaises(TypeError):
            self._run(side_effect=TypeError("unexpected keyword argument 'foo'"))

    def test_a_network_failure_explains_itself(self):
        error = anthropic.APIConnectionError(request=MagicMock())
        with self.assertRaises(TranslationError) as ctx:
            self._run(side_effect=error)
        self.assertIn("network", str(ctx.exception).lower())


@override_settings(APP_PASSWORD="hunter2", ANTHROPIC_API_KEY="sk-ant-test")
class PasswordGateTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_the_app_is_unreachable_until_unlocked(self):
        for name in ("index", "history"):
            self.assertRedirects(self.client.get(reverse(name)), reverse("unlock"))

    def test_translating_is_blocked_before_unlocking(self):
        with patch("translate.views.translate") as mock:
            self.client.post(reverse("index"), {"text": "Hola", "target_language": "English"})
        mock.assert_not_called()
        self.assertFalse(Translation.objects.exists())

    def test_the_right_password_opens_the_app(self):
        response = self.client.post(reverse("unlock"), {"password": "hunter2"})
        self.assertRedirects(response, reverse("index"))
        self.assertEqual(self.client.get(reverse("index")).status_code, 200)

    def test_the_wrong_password_does_not(self):
        response = self.client.post(reverse("unlock"), {"password": "wrong"}, follow=True)
        self.assertContains(response, "That password isn")  # apostrophe is HTML-escaped
        self.assertRedirects(self.client.get(reverse("index")), reverse("unlock"))

    def test_the_unlock_page_is_reachable(self):
        self.assertEqual(self.client.get(reverse("unlock")).status_code, 200)

    def test_static_files_bypass_the_gate(self):
        # Otherwise the unlock page renders unstyled. A blocked request would
        # redirect to /unlock/; the 404 here is just the test client not serving
        # static files, which whitenoise does in production.
        response = self.client.get("/static/css/style.css")
        self.assertNotEqual(response.status_code, 302)

    @override_settings(APP_PASSWORD="")
    def test_a_blank_password_disables_the_gate_for_local_development(self):
        self.assertEqual(self.client.get(reverse("index")).status_code, 200)


@override_settings(ANTHROPIC_API_KEY="sk-ant-test")
class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _post(self, text="Buenos dias", target="English"):
        result = TranslationResult(
            translation="Good morning",
            detected_language="Spanish",
            detected_language_code="es",
            notes="",
        )
        with patch("translate.views.translate", return_value=result) as mock:
            response = self.client.post(
                reverse("index"), {"text": text, "target_language": target}
            )
        return response, mock

    def test_translating_saves_and_redirects_to_the_result(self):
        response, _ = self._post()
        translation = Translation.objects.get()
        self.assertRedirects(response, reverse("detail", args=[translation.pk]))
        self.assertEqual(translation.translated_text, "Good morning")
        self.assertEqual(translation.detected_language, "Spanish")

    def test_the_result_page_shows_the_translation(self):
        self._post()
        translation = Translation.objects.get()
        response = self.client.get(reverse("detail", args=[translation.pk]))
        self.assertContains(response, "Good morning")

    def test_an_api_failure_is_shown_and_nothing_is_saved(self):
        with patch("translate.views.translate", side_effect=TranslationError("Claude is down.")):
            response = self.client.post(
                reverse("index"), {"text": "Hola", "target_language": "English"}, follow=True
            )
        self.assertContains(response, "Claude is down.")
        self.assertFalse(Translation.objects.exists())

    def test_an_invalid_form_does_not_call_the_api(self):
        with patch("translate.views.translate") as mock:
            self.client.post(reverse("index"), {"text": "", "target_language": "English"})
        mock.assert_not_called()

    def test_history_lists_past_translations(self):
        self._post(text="Buenos dias")
        response = self.client.get(reverse("history"))
        self.assertContains(response, "Buenos dias")

    def test_history_search_filters(self):
        self._post(text="Buenos dias")
        self.assertContains(self.client.get(reverse("history"), {"q": "Buenos"}), "Buenos dias")
        self.assertNotContains(self.client.get(reverse("history"), {"q": "zzzz"}), "Buenos dias")

    def test_reuse_prefills_the_form_with_the_original_text(self):
        self._post(text="Buenos dias")
        translation = Translation.objects.get()
        response = self.client.get(reverse("reuse", args=[translation.pk]))
        self.assertContains(response, "Buenos dias")

    def test_delete_removes_the_translation(self):
        self._post()
        translation = Translation.objects.get()
        self.client.post(reverse("delete", args=[translation.pk]))
        self.assertFalse(Translation.objects.exists())

    def test_another_browser_session_cannot_see_or_delete_your_translations(self):
        self._post()
        translation = Translation.objects.get()

        stranger = Client()
        self.assertEqual(stranger.get(reverse("detail", args=[translation.pk])).status_code, 404)
        self.assertEqual(stranger.post(reverse("delete", args=[translation.pk])).status_code, 404)
        self.assertNotContains(stranger.get(reverse("history")), "Buenos dias")
        self.assertTrue(Translation.objects.exists())
