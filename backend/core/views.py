from django.db.models import Count, Prefetch
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from .models import ClothRoll, DipRun, Loft, RollSignOff
from .serializers import (
    ClothRollSerializer,
    DipRunSerializer,
    LoftSerializer,
    SignOffSerializer,
)


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = (
            ClothRoll.objects.select_related("loft")
            .prefetch_related(
                Prefetch(
                    "signoffs",
                    queryset=RollSignOff.objects.filter(voided_at__isnull=True),
                    to_attr="active_signoffs",
                )
            )
            .all()
        )
        loft_id = self.request.query_params.get("loftId")
        status = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class DipRunViewSet(viewsets.ModelViewSet):
    serializer_class = DipRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = DipRun.objects.select_related("roll", "roll__loft").all()
        roll_id = self.request.query_params.get("rollId")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs


class SignOffViewSet(viewsets.ModelViewSet):
    """客户画押编号：操作工可落编号；作废仅管理员。"""

    serializer_class = SignOffSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = RollSignOff.objects.select_related("roll", "roll__loft", "signed_by").all()
        state = self.request.query_params.get("state")
        roll_id = self.request.query_params.get("rollId")
        if state == "active":
            qs = qs.filter(voided_at__isnull=True)
        elif state == "voided":
            qs = qs.filter(voided_at__isnull=False)
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        return qs

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        if request.user.role != User.ROLE_ADMIN:
            raise PermissionDenied("仅管理员可作废画押编号")
        signoff = self.get_object()
        if signoff.voided_at is not None:
            return Response({"detail": "该画押编号已作废"}, status=400)
        signoff.voided_at = timezone.now()
        signoff.save(update_fields=["voided_at"])
        return Response(self.get_serializer(signoff).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    data = {
        "loftCount": Loft.objects.count(),
        "rawRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_RAW).count(),
        "dippingRollCount": ClothRoll.objects.filter(
            status=ClothRoll.STATUS_DIPPING
        ).count(),
        "curedRollCount": ClothRoll.objects.filter(status=ClothRoll.STATUS_CURED).count(),
        "dipRunCount": DipRun.objects.count(),
    }
    return Response(data)
