"""Add optional site-scoped retirement rules without changing existing policy."""

from django.db import migrations, models

import netbox_proxbox.validators
from ._idempotent_ops import add_field_idempotent


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_proxbox", "0106_device_sync_scope_and_netbox_token_approval"),
    ]

    operations = [
        add_field_idempotent(
            "proxboxpluginsettings",
            "orphan_retirement_rules",
            models.JSONField(
                blank=True,
                default=None,
                null=True,
                validators=[netbox_proxbox.validators.validate_orphan_retirement_rules],
                verbose_name="Orphan retirement rules",
                help_text=(
                    "Null preserves legacy soft-decommissioning. A list allows only the "
                    "listed site IDs; other sites are report-only. Each rule has site_id, "
                    "status (report_only, offline or decommissioning), and an optional "
                    "existing tag_id. An empty list is report-only everywhere. "
                    "Requires a backend supporting site-scoped retirement rules."
                ),
            ),
        ),
    ]
