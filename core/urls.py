from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    
    path("students/", views.student_list, name="student_list"),
    path("students/<int:student_id>/", views.student_detail, name="student_detail"),
    path("students/<int:student_id>/attendance/add/", views.add_attendance, name="add_attendance"),
    path("students/<int:student_id>/intervention/add/", views.add_intervention, name="add_intervention"),
    path("students/<int:student_id>/appointment/add/", views.add_appointment, name="add_appointment"),
    path("students/<int:student_id>/cases/add/", views.add_case, name="add_case"),
    path("students/export/csv/", views.export_students_csv, name="export_students_csv"),
    
    path("interventions/<int:intervention_id>/edit/", views.edit_intervention, name="edit_intervention"),
    
    path("admin-settings/", views.admin_settings, name="admin_settings"),
    path("upload/csv/", views.upload_csv, name="upload_csv"),
    path("audit-logs/", views.audit_log_list, name="audit_log_list"),
    
    path("cases/", views.case_list, name="case_list"),
    path("cases/<int:case_id>/", views.case_detail, name="case_detail"),
    path("cases/<int:case_id>/transition/", views.case_transition, name="case_transition"),
    
    path("health/", views.health_check, name="health_check"),
]