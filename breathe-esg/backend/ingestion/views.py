from django.utils import timezone
from rest_framework import serializers, viewsets, status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Client, IngestionJob, EmissionRecord
from .parsers import parse_sap_csv, parse_utility_csv, parse_travel_json


# ── Serializers ───────────────────────────────────────────────────────────────

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'


class IngestionJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionJob
        fields = '__all__'


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    review_status_display = serializers.CharField(source='get_review_status_display', read_only=True)
    job_source_type = serializers.CharField(source='job.source_type', read_only=True)

    class Meta:
        model = EmissionRecord
        fields = '__all__'


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_or_create_demo_client():
    client, _ = Client.objects.get_or_create(
        slug='acme-corp',
        defaults={'name': 'ACME Corp (Demo)'}
    )
    return client


def _save_records(records, errors, job):
    saved = 0
    for rec in records:
        EmissionRecord.objects.create(
            client=job.client,
            job=job,
            scope=rec['scope'],
            category=rec['category'],
            activity_date=rec['activity_date'],
            period_start=rec.get('period_start'),
            period_end=rec.get('period_end'),
            description=rec.get('description', ''),
            location=rec.get('location', ''),
            quantity=rec['quantity'],
            unit=rec['unit'],
            quantity_original=rec['quantity_original'],
            unit_original=rec['unit_original'],
            emission_factor=rec.get('emission_factor'),
            emission_factor_source=rec.get('emission_factor_source', ''),
            co2e_kg=rec.get('co2e_kg'),
            source_raw=rec['source_raw'],
            source_row_id=rec.get('source_row_id', ''),
            is_estimated=rec.get('is_estimated', False),
            is_suspicious=rec.get('is_suspicious', False),
            suspicion_reason=rec.get('suspicion_reason', ''),
        )
        saved += 1
    job.rows_ok = saved
    job.rows_failed = len(errors)
    job.rows_total = saved + len(errors)
    job.error_log = errors
    job.status = IngestionJob.STATUS_DONE
    job.save()


# ── Upload Views ──────────────────────────────────────────────────────────────

class SAPIngestView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        client = _get_or_create_demo_client()
        job = IngestionJob.objects.create(
            client=client,
            source_type=IngestionJob.SOURCE_SAP,
            status=IngestionJob.STATUS_PROCESSING,
            file_name=file_obj.name,
            ingested_by=request.data.get('analyst', 'analyst@demo.com'),
        )

        content = file_obj.read().decode('utf-8', errors='replace')
        records, errors = parse_sap_csv(content)
        _save_records(records, errors, job)

        return Response(IngestionJobSerializer(job).data, status=201)


class UtilityIngestView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        client = _get_or_create_demo_client()
        job = IngestionJob.objects.create(
            client=client,
            source_type=IngestionJob.SOURCE_UTILITY,
            status=IngestionJob.STATUS_PROCESSING,
            file_name=file_obj.name,
            ingested_by=request.data.get('analyst', 'analyst@demo.com'),
        )

        content = file_obj.read().decode('utf-8', errors='replace')
        records, errors = parse_utility_csv(content)
        _save_records(records, errors, job)

        return Response(IngestionJobSerializer(job).data, status=201)


class TravelIngestView(APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request):
        # Accept either JSON body or file upload
        if request.FILES.get('file'):
            content = request.FILES['file'].read().decode('utf-8')
            payload = __import__('json').loads(content)
            file_name = request.FILES['file'].name
        else:
            payload = request.data if isinstance(request.data, (list, dict)) else request.data.get('data', [])
            file_name = 'api-payload.json'

        client = _get_or_create_demo_client()
        job = IngestionJob.objects.create(
            client=client,
            source_type=IngestionJob.SOURCE_TRAVEL,
            status=IngestionJob.STATUS_PROCESSING,
            file_name=file_name,
            raw_payload=payload if isinstance(payload, (list, dict)) else None,
            ingested_by=request.data.get('analyst', 'analyst@demo.com') if isinstance(request.data, dict) else 'analyst@demo.com',
        )

        records, errors = parse_travel_json(payload)
        _save_records(records, errors, job)

        return Response(IngestionJobSerializer(job).data, status=201)


# ── List / Query Views ────────────────────────────────────────────────────────

@api_view(['GET'])
def job_list(request):
    jobs = IngestionJob.objects.select_related('client').all()[:100]
    return Response(IngestionJobSerializer(jobs, many=True).data)


@api_view(['GET'])
def record_list(request):
    qs = EmissionRecord.objects.select_related('client', 'job').all()

    # Filters
    scope = request.query_params.get('scope')
    category = request.query_params.get('category')
    review_status = request.query_params.get('review_status')
    suspicious = request.query_params.get('suspicious')
    source_type = request.query_params.get('source_type')

    if scope:
        qs = qs.filter(scope=scope)
    if category:
        qs = qs.filter(category=category)
    if review_status:
        qs = qs.filter(review_status=review_status)
    if suspicious == 'true':
        qs = qs.filter(is_suspicious=True)
    if source_type:
        qs = qs.filter(job__source_type=source_type)

    total = qs.count()
    page = int(request.query_params.get('page', 1))
    page_size = 50
    start = (page - 1) * page_size
    items = qs[start:start + page_size]

    return Response({
        'count': total,
        'page': page,
        'pages': (total + page_size - 1) // page_size,
        'results': EmissionRecordSerializer(items, many=True).data,
    })


@api_view(['GET'])
def dashboard_stats(request):
    from django.db.models import Sum, Count, Q
    qs = EmissionRecord.objects.all()

    stats = {
        'total_records': qs.count(),
        'pending': qs.filter(review_status='pending').count(),
        'approved': qs.filter(review_status='approved').count(),
        'flagged': qs.filter(review_status='flagged').count(),
        'rejected': qs.filter(review_status='rejected').count(),
        'suspicious': qs.filter(is_suspicious=True).count(),
        'total_co2e_kg': float(qs.aggregate(s=Sum('co2e_kg'))['s'] or 0),
        'scope1_co2e': float(qs.filter(scope=1).aggregate(s=Sum('co2e_kg'))['s'] or 0),
        'scope2_co2e': float(qs.filter(scope=2).aggregate(s=Sum('co2e_kg'))['s'] or 0),
        'scope3_co2e': float(qs.filter(scope=3).aggregate(s=Sum('co2e_kg'))['s'] or 0),
        'jobs': IngestionJob.objects.count(),
    }
    return Response(stats)
