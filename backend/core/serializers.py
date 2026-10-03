import re

from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import ClothRoll, DipRun, Loft, RollSignOff
from .rules import can_mark_roll_cured, can_restore_roll_to_raw


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
    activeSignOffCode = serializers.SerializerMethodField()

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
            "activeSignOffCode",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "loftName", "activeSignOffCode", "created_at", "updated_at")

    def get_activeSignOffCode(self, obj):
        active = getattr(obj, "active_signoffs", None)
        if active is not None:
            return active[0].code if active else None
        so = obj.signoffs.filter(voided_at__isnull=True).first()
        return so.code if so else None

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
        if new_status == ClothRoll.STATUS_CURED:
            roll = self.instance
            if roll is None:
                raise serializers.ValidationError(
                    {"status": "新建布卷不能直接设为已固化"}
                )
            # 合并未提交字段到临时视角：用当前实例校验
            ok, msg = can_mark_roll_cured(roll)
            if not ok:
                raise serializers.ValidationError({"status": msg})
        if new_status == ClothRoll.STATUS_RAW and self.instance is not None:
            # 已固化卷拨回原布：须存在未作废画押编号
            ok, msg = can_restore_roll_to_raw(self.instance)
            if not ok:
                raise serializers.ValidationError({"status": msg})
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


class SignOffSerializer(serializers.ModelSerializer):
    rollId = serializers.PrimaryKeyRelatedField(
        source="roll", queryset=ClothRoll.objects.all()
    )
    rollCode = serializers.CharField(source="roll.roll_code", read_only=True)
    loftName = serializers.CharField(source="roll.loft.name", read_only=True)
    code = serializers.CharField(max_length=6)
    signedAt = serializers.DateTimeField(source="signed_at", read_only=True)
    signedBy = serializers.CharField(source="signed_by.username", read_only=True)
    voidedAt = serializers.DateTimeField(source="voided_at", read_only=True)
    active = serializers.SerializerMethodField()

    class Meta:
        model = RollSignOff
        fields = (
            "id",
            "rollId",
            "rollCode",
            "loftName",
            "code",
            "signedAt",
            "signedBy",
            "voidedAt",
            "active",
            "created_at",
        )
        read_only_fields = (
            "id",
            "rollCode",
            "loftName",
            "signedAt",
            "signedBy",
            "voidedAt",
            "active",
            "created_at",
        )

    def get_active(self, obj):
        return obj.voided_at is None

    def validate_code(self, value):
        if not re.fullmatch(r"[0-9]{6}", value or ""):
            raise serializers.ValidationError("画押编号必须正好 6 位数字")
        return value

    def create(self, validated_data):
        validated_data["signed_by"] = self.context["request"].user
        try:
            # 唯一约束（未作废每卷一条）兜底并发双落：后提交者在此报 IntegrityError
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                {"rollId": "该布卷已存在未作废的画押编号，不能重复落下"}
            )
