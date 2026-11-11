"""Real model/form/API contracts for optional site-scoped retirement policy."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from tests.netbox_test_paths import netbox_source_roots

for root in netbox_source_roots(Path(__file__).resolve().parents[1]):
    if root.exists() and str(root) not in sys.path:
        sys.path.insert(0, str(root))

try:
    import django

    django.setup()
except Exception:
    if os.environ.get("NETBOX_PROXBOX_REQUIRE_DJANGO") == "1":
        raise
    pytest.skip("Real NetBox/Django test environment required", allow_module_level=True)

from django import forms  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402
from django.test import TestCase  # noqa: E402
from rest_framework.exceptions import ValidationError as APIValidationError  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from netbox_proxbox.api.serializers.settings import ProxboxPluginSettingsSerializer  # noqa: E402
from netbox_proxbox.forms.settings import ProxboxPluginSettingsForm  # noqa: E402
from netbox_proxbox.models import ProxboxPluginSettings  # noqa: E402
from tests.django_support import make_user  # noqa: E402


class RetirementRulesTest(TestCase):
    def test_empty_object_is_rejected_at_model_form_and_api_boundaries(self):
        row = ProxboxPluginSettings.get_solo()
        row.orphan_retirement_rules = {}
        with self.subTest(boundary="model"):
            with self.assertRaises(ValidationError) as error:
                row.full_clean()
            self.assertIn("orphan_retirement_rules", error.exception.message_dict)
        with self.subTest(boundary="form"):
            form = ProxboxPluginSettingsForm(data={"orphan_retirement_rules": "{}"})
            form.full_clean()
            self.assertIn("orphan_retirement_rules", form.errors)
        with self.subTest(boundary="api"):
            client = APIClient()
            client.force_authenticate(
                user=make_user("retirement-validation", is_superuser=True)
            )
            response = client.patch(
                f"/api/plugins/proxbox/settings/{row.pk}/",
                {"orphan_retirement_rules": {}},
                format="json",
            )
            self.assertEqual(response.status_code, 400, response.data)

    def test_settings_form_distinguishes_omitted_and_explicit_policy(self):
        row = ProxboxPluginSettings.get_solo()
        self.client.force_login(make_user("retirement-form", is_superuser=True))
        url = "/plugins/proxbox/settings/"
        for policy in ([], [{"site_id": 901, "status": "offline"}]):
            row.orphan_retirement_rules = policy
            row.save()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            payload = {}
            for bound in response.context["form"]:
                value = bound.value()
                if isinstance(bound.field, forms.BooleanField):
                    if value:
                        payload[bound.name] = "on"
                elif isinstance(bound.field, forms.JSONField):
                    payload[bound.name] = json.dumps(value)
                elif value is not None:
                    payload[bound.name] = value
            payload.pop("orphan_retirement_rules")
            with self.subTest(policy=policy, submission="omitted"):
                response = self.client.post(url, payload)
                self.assertEqual(response.status_code, 302)
                row.refresh_from_db()
                self.assertEqual(row.orphan_retirement_rules, policy)
            for explicit in ("null", "[]", ""):
                with self.subTest(policy=policy, submission=explicit):
                    payload["orphan_retirement_rules"] = explicit
                    response = self.client.post(url, payload)
                    self.assertEqual(response.status_code, 302)
                    row.refresh_from_db()
                    self.assertEqual(
                        row.orphan_retirement_rules, [] if explicit == "[]" else None
                    )

    def test_model_form_and_api_reject_ambiguous_rules(self):
        model_field = ProxboxPluginSettings._meta.get_field("orphan_retirement_rules")
        form_field = ProxboxPluginSettingsForm().fields["orphan_retirement_rules"]
        api_field = ProxboxPluginSettingsSerializer().fields["orphan_retirement_rules"]
        invalid = (
            {"site_id": 901},
            [{"site_id": True, "status": "offline"}],
            [{"site_id": 901, "status": "delete"}],
            [{"site_id": 901, "status": "offline", "tag_id": 902.5}],
            [{"site_id": 901, "status": "offline", "unknown": True}],
            [{"site_id": 901, "status": "offline"}] * 2,
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    model_field.run_validators(value)
                with self.assertRaises(ValidationError):
                    form_field.clean(json.dumps(value))
                with self.assertRaises(APIValidationError):
                    api_field.run_validation(value)
        self.assertIsNone(form_field.clean("null"))
        self.assertEqual(form_field.clean("[]"), [])

    def test_partial_api_updates_preserve_null_empty_and_explicit_policy(self):
        row = ProxboxPluginSettings.get_solo()
        client = APIClient()
        client.force_authenticate(
            user=make_user("retirement-operator", is_superuser=True)
        )
        url = f"/api/plugins/proxbox/settings/{row.pk}/"
        for value in (None, [], [{"site_id": 901, "status": "offline", "tag_id": 902}]):
            response = client.patch(
                url, {"orphan_retirement_rules": value}, format="json"
            )
            self.assertEqual(response.status_code, 200, response.data)
            row.refresh_from_db()
            self.assertEqual(row.orphan_retirement_rules, value)
            self.assertEqual(client.get(url).data["orphan_retirement_rules"], value)
        response = client.patch(
            url, {"orphan_retirement_rules": [{"site_id": 901}]}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        row.refresh_from_db()
        self.assertEqual(
            row.orphan_retirement_rules,
            [{"site_id": 901, "status": "offline", "tag_id": 902}],
        )
