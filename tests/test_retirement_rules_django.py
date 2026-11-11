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

from django.core.exceptions import ValidationError  # noqa: E402
from django.test import TestCase  # noqa: E402
from rest_framework.exceptions import ValidationError as APIValidationError  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from netbox_proxbox.api.serializers.settings import ProxboxPluginSettingsSerializer  # noqa: E402
from netbox_proxbox.forms.settings import ProxboxPluginSettingsForm  # noqa: E402
from netbox_proxbox.models import ProxboxPluginSettings  # noqa: E402
from tests.django_support import make_user  # noqa: E402


class RetirementRulesTest(TestCase):
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
