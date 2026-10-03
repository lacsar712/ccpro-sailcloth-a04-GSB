from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ClothRoll, CustomerMark, DipRun, Loft
from .serializers import (
    ClothRollSerializer,
    CustomerMarkSerializer,
    DipRunSerializer,
    LoftSerializer,
)


class LoftViewSet(viewsets.ModelViewSet):
    queryset = Loft.objects.annotate(roll_count=Count("rolls")).all()
    serializer_class = LoftSerializer


class ClothRollViewSet(viewsets.ModelViewSet):
    serializer_class = ClothRollSerializer

    def get_queryset(self):
        qs = ClothRoll.objects.select_related("loft").prefetch_related(
            "customer_marks"
        )
        loft_id = self.request.query_params.get("loftId")
        status_param = self.request.query_params.get("status")
        if loft_id:
            qs = qs.filter(loft_id=loft_id)
        if status_param:
            qs = qs.filter(status=status_param)
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


class CustomerMarkViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerMarkSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = CustomerMark.objects.select_related(
            "roll", "roll__loft", "signed_by", "revoked_by"
        )
        roll_id = self.request.query_params.get("rollId")
        state = self.request.query_params.get("state")
        if roll_id:
            qs = qs.filter(roll_id=roll_id)
        if state == "valid":
            qs = qs.filter(revoked_at__isnull=True)
        elif state == "void":
            qs = qs.filter(revoked_at__isnull=False)
        return qs

    @action(
        detail=True,
        methods=["post"],
        url_path="revoke",
        permission_classes=[IsAuthenticated],
    )
    def revoke(self, request, pk=None):
        """作废画押：仅管理员。作废后该编号不能再用于放行。"""
        if request.user.role != "admin":
            return Response(
                {"detail": "只有管理员可以作废画押编号"},
                status=status.HTTP_403_FORBIDDEN,
            )
        mark = self.get_object()
        if mark.revoked_at is not None:
            return Response(
                {"detail": "该画押编号已经作废，无需重复操作"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        mark.revoked_at = timezone.now()
        mark.revoked_by = request.user
        mark.save(update_fields=["revoked_at", "revoked_by"])
        return Response(self.get_serializer(mark).data)


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
