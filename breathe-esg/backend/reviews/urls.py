from django.urls import path
from . import views

urlpatterns = [
    path('records/<uuid:record_id>/review/', views.review_record, name='review-record'),
    path('records/bulk-review/', views.bulk_review, name='bulk-review'),
    path('records/lock/', views.lock_approved, name='lock-approved'),
]
