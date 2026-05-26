from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from ingestion.models import EmissionRecord
import json


@api_view(['POST'])
def review_record(request, record_id):
    """
    Analyst reviews a single record.
    Body: { "action": "approved"|"flagged"|"rejected", "note": "...", "analyst": "..." }
    """
    try:
        record = EmissionRecord.objects.get(id=record_id)
    except EmissionRecord.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if record.is_locked:
        return Response({'error': 'Record is locked for audit'}, status=400)

    action = request.data.get('action')
    if action not in ('approved', 'flagged', 'rejected'):
        return Response({'error': 'action must be approved, flagged, or rejected'}, status=400)

    analyst = request.data.get('analyst', 'analyst@demo.com')
    note = request.data.get('note', '')

    record.review_status = action
    record.reviewed_by = analyst
    record.reviewed_at = timezone.now()
    record.review_note = note
    record.save()

    return Response({'id': str(record.id), 'review_status': record.review_status})


@api_view(['POST'])
def bulk_review(request):
    """
    Bulk approve/flag records.
    Body: { "ids": ["uuid", ...], "action": "approved", "analyst": "..." }
    """
    ids = request.data.get('ids', [])
    action = request.data.get('action')
    analyst = request.data.get('analyst', 'analyst@demo.com')

    if action not in ('approved', 'flagged', 'rejected'):
        return Response({'error': 'Invalid action'}, status=400)

    updated = EmissionRecord.objects.filter(
        id__in=ids, is_locked=False
    ).update(
        review_status=action,
        reviewed_by=analyst,
        reviewed_at=timezone.now(),
    )
    return Response({'updated': updated})


@api_view(['POST'])
def lock_approved(request):
    """Lock all approved records for audit."""
    analyst = request.data.get('analyst', 'analyst@demo.com')
    updated = EmissionRecord.objects.filter(
        review_status='approved', is_locked=False
    ).update(is_locked=True, locked_at=timezone.now())
    return Response({'locked': updated})
