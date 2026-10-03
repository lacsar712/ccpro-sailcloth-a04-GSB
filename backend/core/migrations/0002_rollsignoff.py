import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RollSignOff",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "code",
                    models.CharField(
                        max_length=6,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^[0-9]{6}$", "画押编号必须正好 6 位数字"
                            )
                        ],
                    ),
                ),
                ("signed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("voided_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "roll",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signoffs",
                        to="core.clothroll",
                    ),
                ),
                (
                    "signed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="signoffs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-signed_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="rollsignoff",
            constraint=models.UniqueConstraint(
                condition=models.Q(voided_at__isnull=True),
                fields=("roll",),
                name="uniq_active_signoff_per_roll",
            ),
        ),
        migrations.AddConstraint(
            model_name="rollsignoff",
            constraint=models.CheckConstraint(
                check=models.Q(code__regex="^[0-9]{6}$"),
                name="signoff_code_six_digits",
            ),
        ),
    ]
