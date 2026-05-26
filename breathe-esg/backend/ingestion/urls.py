from django.urls import path
from . import views

urlpatterns = [
    path('ingest/sap/', views.SAPIngestView.as_view(), name='ingest-sap'),
    path('ingest/utility/', views.UtilityIngestView.as_view(), name='ingest-utility'),
    path('ingest/travel/', views.TravelIngestView.as_view(), name='ingest-travel'),
    path('jobs/', views.job_list, name='job-list'),
    path('records/', views.record_list, name='record-list'),
    path('stats/', views.dashboard_stats, name='dashboard-stats'),
]
