from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class Loft(models.Model):
    name = models.CharField(max_length=120)
    location = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class ClothRoll(models.Model):
    STATUS_RAW = "raw"
    STATUS_DIPPING = "dipping"
    STATUS_CURED = "cured"
    STATUS_CHOICES = [
        (STATUS_RAW, "原布"),
        (STATUS_DIPPING, "浸渍中"),
        (STATUS_CURED, "已固化"),
    ]

    loft = models.ForeignKey(Loft, on_delete=models.CASCADE, related_name="rolls")
    roll_code = models.CharField(max_length=40)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RAW)
    fabric_weight_gsm = models.PositiveIntegerField(default=380)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["loft_id", "roll_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["loft", "roll_code"],
                name="uniq_roll_code_per_loft",
            )
        ]

    def __str__(self):
        return f"{self.loft.name}/{self.roll_code}"


class DipRun(models.Model):
    roll = models.ForeignKey(ClothRoll, on_delete=models.CASCADE, related_name="dip_runs")
    started_at = models.DateTimeField()
    resin_pct = models.DecimalField(max_digits=5, decimal_places=2)
    cure_hours = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Dip@{self.roll_id} {self.started_at}"


class CustomerMark(models.Model):
    """客户在专页落下的六位数字画押编号；固化卷拨回原布的放行凭据。"""

    CODE_RE = r"^\d{6}$"

    roll = models.ForeignKey(
        ClothRoll, on_delete=models.CASCADE, related_name="customer_marks"
    )
    code = models.CharField(
        max_length=6,
        validators=[RegexValidator(CODE_RE, "画押编号必须正好为 6 位数字")],
    )
    signed_at = models.DateTimeField(auto_now_add=True)
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_marks_signed",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_marks_revoked",
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-signed_at", "-id"]
        constraints = [
            # 同一卷未作废（有效）画押最多一条；作废记录 revoked_at 非空，不受约束。
            models.UniqueConstraint(
                fields=["roll"],
                condition=models.Q(revoked_at__isnull=True),
                name="uniq_one_active_mark_per_roll",
            )
        ]

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def __str__(self):
        state = "有效" if self.is_active else "已作废"
        return f"Mark {self.code}@{self.roll_id}（{state}）"


def active_customer_mark(roll: ClothRoll) -> CustomerMark | None:
    """取该卷当前唯一的未作废画押；没有返回 None。"""
    return roll.customer_marks.filter(revoked_at__isnull=True).first()
