from django.db import models
import uuid


class Client(models.Model):
    """Multi-tenant: every row belongs to a client."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class IngestionJob(models.Model):
    """Represents one upload/ingest event. Source of truth for provenance."""
    SOURCE_SAP = 'sap'
    SOURCE_UTILITY = 'utility'
    SOURCE_TRAVEL = 'travel'
    SOURCE_CHOICES = [
        (SOURCE_SAP, 'SAP Flat File'),
        (SOURCE_UTILITY, 'Utility CSV'),
        (SOURCE_TRAVEL, 'Travel JSON'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='jobs')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    file_name = models.CharField(max_length=500, blank=True)
    file_path = models.FileField(upload_to='uploads/', blank=True, null=True)
    raw_payload = models.JSONField(null=True, blank=True)  # for travel JSON paste
    rows_total = models.IntegerField(default=0)
    rows_ok = models.IntegerField(default=0)
    rows_failed = models.IntegerField(default=0)
    error_log = models.JSONField(default=list)
    ingested_at = models.DateTimeField(auto_now_add=True)
    ingested_by = models.CharField(max_length=255, default='system')

    class Meta:
        ordering = ['-ingested_at']

    def __str__(self):
        return f"{self.client} / {self.source_type} / {self.ingested_at:%Y-%m-%d %H:%M}"


class EmissionRecord(models.Model):
    """
    Normalized emission activity row. Every source funnels into this.
    Scope 1 = direct (fuel combustion)
    Scope 2 = indirect (purchased electricity)
    Scope 3 = value chain (business travel)
    """
    SCOPE_1 = 1
    SCOPE_2 = 2
    SCOPE_3 = 3
    SCOPE_CHOICES = [(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')]

    CATEGORY_FUEL = 'fuel'
    CATEGORY_ELECTRICITY = 'electricity'
    CATEGORY_FLIGHT = 'flight'
    CATEGORY_HOTEL = 'hotel'
    CATEGORY_GROUND = 'ground_transport'
    CATEGORY_CHOICES = [
        (CATEGORY_FUEL, 'Fuel Combustion'),
        (CATEGORY_ELECTRICITY, 'Electricity'),
        (CATEGORY_FLIGHT, 'Flight'),
        (CATEGORY_HOTEL, 'Hotel Stay'),
        (CATEGORY_GROUND, 'Ground Transport'),
    ]

    REVIEW_PENDING = 'pending'
    REVIEW_APPROVED = 'approved'
    REVIEW_FLAGGED = 'flagged'
    REVIEW_REJECTED = 'rejected'
    REVIEW_CHOICES = [
        (REVIEW_PENDING, 'Pending Review'),
        (REVIEW_APPROVED, 'Approved'),
        (REVIEW_FLAGGED, 'Flagged'),
        (REVIEW_REJECTED, 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Multi-tenancy ──────────────────────────────────────────────
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='records')

    # ── Provenance (source-of-truth tracking) ─────────────────────
    job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='records')
    source_row_id = models.CharField(max_length=255, blank=True)  # original PK/row number from source
    source_raw = models.JSONField()  # verbatim row as ingested, never mutated

    # ── Classification ─────────────────────────────────────────────
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)

    # ── Activity data (normalized) ─────────────────────────────────
    activity_date = models.DateField()
    period_start = models.DateField(null=True, blank=True)   # for utility billing periods
    period_end = models.DateField(null=True, blank=True)

    description = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)  # plant code, meter ID, office

    # ── Quantity (always stored in SI base unit) ───────────────────
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    unit = models.CharField(max_length=30)          # normalized unit: L, kWh, km, night
    quantity_original = models.DecimalField(max_digits=20, decimal_places=6)
    unit_original = models.CharField(max_length=30)  # raw unit from source

    # ── Emission factor applied ────────────────────────────────────
    emission_factor = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    emission_factor_source = models.CharField(max_length=255, blank=True)  # e.g. "DEFRA 2023"
    co2e_kg = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)

    # ── Data quality flags ─────────────────────────────────────────
    is_estimated = models.BooleanField(default=False)    # imputed/interpolated value
    is_suspicious = models.BooleanField(default=False)   # statistical outlier or validation fail
    suspicion_reason = models.CharField(max_length=500, blank=True)

    # ── Review & audit lifecycle ───────────────────────────────────
    review_status = models.CharField(max_length=20, choices=REVIEW_CHOICES, default=REVIEW_PENDING)
    reviewed_by = models.CharField(max_length=255, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    # ── Edit tracking (was this row touched post-ingestion?) ───────
    is_edited = models.BooleanField(default=False)
    edit_history = models.JSONField(default=list)  # [{field, old, new, by, at}]

    # ── Audit lock ────────────────────────────────────────────────
    is_locked = models.BooleanField(default=False)   # locked = sent to auditor
    locked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['client', 'scope', 'activity_date']),
            models.Index(fields=['client', 'review_status']),
            models.Index(fields=['job']),
        ]

    def __str__(self):
        return f"{self.client} | {self.category} | {self.activity_date} | {self.quantity} {self.unit}"
