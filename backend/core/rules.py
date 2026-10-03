"""帆布浸渍防水台业务规则。"""

from __future__ import annotations

from decimal import Decimal

from .models import ClothRoll, DipRun, RollSignOff

MIN_CURE_HOURS_FOR_CURED = Decimal("12")


def latest_dip_run(roll: ClothRoll) -> DipRun | None:
    return roll.dip_runs.order_by("-started_at", "-id").first()


def active_signoff(roll: ClothRoll) -> RollSignOff | None:
    """该卷当前未作废的画押编号（最多一条，由数据库唯一约束兜底）。"""
    return roll.signoffs.filter(voided_at__isnull=True).first()


def can_mark_roll_cured(roll: ClothRoll) -> tuple[bool, str]:
    """
    布卷转为「已固化」(cured) 的前提：
    最近一条浸渍记录的固化时长已记录，且 >= 12 小时。
    画押不参与固化判断。
    """
    latest = latest_dip_run(roll)
    if latest is None:
        return False, "该布卷尚无浸渍记录，不能标记为已固化"
    if latest.cure_hours is None:
        return False, "最近浸渍记录尚未填写固化时长，不能标记为已固化"
    if latest.cure_hours < MIN_CURE_HOURS_FOR_CURED:
        return (
            False,
            f"最近浸渍固化时长 {latest.cure_hours} 小时低于 {MIN_CURE_HOURS_FOR_CURED} 小时，不能标记为已固化",
        )
    return True, ""


def can_restore_roll_to_raw(roll: ClothRoll) -> tuple[bool, str]:
    """
    已固化卷拨回「原布」(raw) 的前提：
    该卷存在未作废的客户画押编号。非已固化卷不校验。
    """
    if roll.status != ClothRoll.STATUS_CURED:
        return True, ""
    if active_signoff(roll) is None:
        return (
            False,
            "该卷已固化，拨回原布前须由客户在「客户画押」专页落下有效的 6 位画押编号（未作废）",
        )
    return True, ""
