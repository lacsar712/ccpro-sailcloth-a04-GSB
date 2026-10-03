from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import ClothRoll, CustomerMark, DipRun, Loft
from .rules import can_mark_roll_cured, can_revert_to_raw


class LoftSerializer(serializers.ModelSerializer):
    rollCount = serializers.SerializerMethodField()

    class Meta:
        model = Loft
        fields = ("id", "name", "location", "notes", "rollCount", "created_at")
        read_only_fields = ("id", "rollCount", "created_at")

    def get_rollCount(self, obj):
        if hasattr(obj, "roll_count"):
            return obj.roll_count
        return obj.rolls.count()


class ClothRollSerializer(serializers.ModelSerializer):
    loftId = serializers.PrimaryKeyRelatedField(source="loft", queryset=Loft.objects.all())
    rollCode = serializers.CharField(source="roll_code")
    fabricWeightGsm = serializers.IntegerField(source="fabric_weight_gsm", required=False)
    loftName = serializers.CharField(source="loft.name", read_only=True)
    activeMarkCode = serializers.SerializerMethodField()

    class Meta:
        model = ClothRoll
        fields = (
            "id",
            "loftId",
            "loftName",
            "rollCode",
            "status",
            "fabricWeightGsm",
            "notes",
            "activeMarkCode",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "activeMarkCode", "created_at", "updated_at")

    def get_activeMarkCode(self, obj):
        # 视图已 prefetch_related("customer_marks")，用 .all() 命中预取缓存，避免 N+1。
        mark = next(
            (m for m in obj.customer_marks.all() if m.revoked_at is None), None
        )
        return mark.code if mark else None

    def validate(self, attrs):
        loft = attrs.get("loft") or getattr(self.instance, "loft", None)
        roll_code = attrs.get("roll_code") or getattr(self.instance, "roll_code", None)
        if loft and roll_code:
            qs = ClothRoll.objects.filter(loft=loft, roll_code=roll_code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"rollCode": "同一帆布间卷号必须唯一"})

        new_status = attrs.get("status")
        if new_status is not None and self.instance is not None:
            if new_status == ClothRoll.STATUS_CURED:
                # 固化只看时长满十二小时，画押不参与固化判断。
                ok, msg = can_mark_roll_cured(self.instance)
                if not ok:
                    raise serializers.ValidationError({"status": msg})
            elif new_status == ClothRoll.STATUS_RAW:
                # 已固化卷拨回原布必须持有未作废的客户画押编号。
                if self.instance.status == ClothRoll.STATUS_CURED:
                    ok, msg = can_revert_to_raw(self.instance)
                    if not ok:
                        raise serializers.ValidationError({"status": msg})
        elif new_status == ClothRoll.STATUS_CURED and self.instance is None:
            raise serializers.ValidationError(
                {"status": "新建布卷不能直接设为已固化"}
            )
        return attrs


class DipRunSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    startedAt = serializers.DateTimeField(source="started_at")
    resinPct = serializers.DecimalField(source="resin_pct", max_digits=5, decimal_places=2)
    cureHours = serializers.DecimalField(
        source="cure_hours",
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)

    class Meta:
        model = DipRun
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "startedAt",
            "resinPct",
            "cureHours",
            "notes",
            "created_at",
        )
        read_only_fields = ("id", "rollCode", "loftName", "created_at")


class CustomerMarkSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)
    code = serializers.CharField(max_length=6, min_length=6)
    signedBy = serializers.CharField(source="signed_by.username", read_only=True)
    revokedBy = serializers.CharField(source="revoked_by.username", read_only=True)
    revokedAt = serializers.DateTimeField(source="revoked_at", read_only=True)
    signedAt = serializers.DateTimeField(source="signed_at", read_only=True)

    class Meta:
        model = CustomerMark
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "code",
            "signedAt",
            "signedBy",
            "revokedAt",
            "revokedBy",
            "notes",
        )
        read_only_fields = (
            "id",
            "rollCode",
            "loftName",
            "signedAt",
            "signedBy",
            "revokedAt",
            "revokedBy",
        )

    def validate_code(self, value: str) -> str:
        if not (value.isdigit() and len(value) == 6):
            raise serializers.ValidationError("画押编号必须正好为 6 位数字")
        return value

    def validate(self, attrs):
        roll = attrs.get("roll")
        if roll is not None and CustomerMark.objects.filter(
            roll=roll, revoked_at__isnull=True
        ).exists():
            raise serializers.ValidationError(
                {"rollId": "该卷已有未作废画押编号，不能重复落下"}
            )
        return attrs

    def create(self, validated_data):
        validated_data["signed_by"] = self.context["request"].user
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError:
            # 两名仓管交叉并发落下时，数据库部分唯一约束兜底：只许一条留下。
            raise serializers.ValidationError(
                {"rollId": "该卷已有未作废画押编号，不能重复落下"}
            )
