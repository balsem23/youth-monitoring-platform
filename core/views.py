import csv
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db import connection

from .models import (
    Student,
    Alert,
    Intervention,
    Appointment,
    AuditLog,
    RiskThreshold,
    Case,
    DataIngestionLog
)

from .forms import (
    AttendanceForm,
    InterventionForm,
    AppointmentForm,
    RiskThresholdForm,
    CaseForm,
    CSVUploadForm
)

from .permissions import role_required, get_user_role
from .data_ingestion import ingest_students_csv


@login_required
def dashboard(request):
    total_students = Student.objects.count()
    high_risk_students = Student.objects.filter(risk_level="HIGH").count()
    active_alerts = Alert.objects.filter(is_resolved=False).count()
    open_interventions = Intervention.objects.exclude(status="CLOSED").count()
    missed_appointments = Appointment.objects.filter(attended=False).count()

    # Computed evaluation metrics
    total_cases = Case.objects.count()
    closed_cases = Case.objects.filter(status='CLOSED').count()
    workflow_completion_rate = round((closed_cases / total_cases * 100), 1) if total_cases > 0 else 0.0

    ingestion_stats = DataIngestionLog.objects.aggregate(total=Sum('total_rows'), accepted=Sum('accepted_rows'))
    total_ingested = ingestion_stats['total'] or 0
    accepted_ingested = ingestion_stats['accepted'] or 0
    data_validation_pass_rate = round((accepted_ingested / total_ingested * 100), 1) if total_ingested > 0 else 0.0

    total_alerts = Alert.objects.count()
    resolved_alerts = Alert.objects.filter(is_resolved=True).count()
    alert_resolution_rate = round((resolved_alerts / total_alerts * 100), 1) if total_alerts > 0 else 0.0

    # Alert precision proxy: ratio of alerts that led to an intervention/action
    alerts_with_action = Alert.objects.filter(
        student__interventions__isnull=False,
        is_resolved=True
    ).values('student').distinct().count()
    alerted_students = Alert.objects.values('student').distinct().count()
    alert_precision_proxy = round(
        (alerts_with_action / alerted_students * 100), 1
    ) if alerted_students > 0 else 0.0

    security_checks_count = AuditLog.objects.filter(action_type='SECURITY').count()

    recent_alerts = Alert.objects.order_by('-created_at')[:5]
    recent_audit_logs = AuditLog.objects.order_by('-created_at')[:10]

    context = {
        "total_students": total_students,
        "high_risk_students": high_risk_students,
        "active_alerts": active_alerts,
        "open_interventions": open_interventions,
        "missed_appointments": missed_appointments,
        # Metrics
        "workflow_completion_rate": workflow_completion_rate,
        "data_validation_pass_rate": data_validation_pass_rate,
        "alert_resolution_rate": alert_resolution_rate,
        "alert_precision_proxy": alert_precision_proxy,
        "security_checks_count": security_checks_count,
        # Tables
        "recent_alerts": recent_alerts,
        "recent_audit_logs": recent_audit_logs,
    }

    return render(request, "core/dashboard.html", context)


@login_required
def student_list(request):
    students = Student.objects.all()
    risk_level = request.GET.get("risk_level", "")
    search = request.GET.get("search", "")

    if risk_level:
        students = students.filter(risk_level=risk_level)

    if search and search != "None":
        students = students.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    context = {
        "students": students,
        "selected_risk_level": risk_level,
        "search": "" if search == "None" else search,
    }

    return render(request, "core/student_list.html", context)


@login_required
def student_detail(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    role = get_user_role(request.user)

    # Privacy by design: Redact counselor notes for unauthorized roles (e.g. Teacher)
    if role not in ["ADMIN", "COUNSELOR"]:
        student.counselor_notes = "[REDACTED — UNAUTHORIZED ROLE]"
        is_notes_redacted = True
    else:
        is_notes_redacted = False

    alerts = student.alerts.all().order_by("-created_at")
    interventions = student.interventions.all().order_by("-created_at")
    appointments = student.appointments.all().order_by("-date")
    cases = student.cases.all().order_by("-created_at")
    logs = AuditLog.objects.filter(affected_object_id=student.id).order_by("-created_at")[:20]

    context = {
        "student": student,
        "is_notes_redacted": is_notes_redacted,
        "alerts": alerts,
        "interventions": interventions,
        "appointments": appointments,
        "cases": cases,
        "logs": logs,
    }

    return render(request, "core/student_detail.html", context)


@login_required
def export_students_csv(request):
    risk_filter = request.GET.get("risk_level", "")
    students = Student.objects.all()
    if risk_filter:
        students = students.filter(risk_level=risk_filter)

    response = HttpResponse(content_type="text/csv")
    filename = f"students_report_{'all' if not risk_filter else risk_filter}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "First Name",
        "Last Name",
        "Date of Birth",
        "Attendance Rate",
        "Average Grade",
        "Risk Level",
        "Risk Explanation",
    ])

    for student in students:
        writer.writerow([
            student.first_name,
            student.last_name,
            student.date_of_birth,
            student.attendance_rate,
            student.average_grade,
            student.risk_level,
            student.risk_explanation,
        ])

    return response


@login_required
@role_required(["ADMIN"])
def admin_settings(request):
    thresholds = RiskThreshold.get_settings()

    if request.method == "POST":
        form = RiskThresholdForm(request.POST, instance=thresholds)

        if form.is_valid():
            form.save()

            AuditLog.objects.create(
                user=request.user,
                user_role=get_user_role(request.user),
                action_type="UPDATE",
                action_result="SUCCESS",
                description="Risk thresholds updated by admin."
            )

            messages.success(request, "Risk thresholds updated successfully.")
            return redirect("admin_settings")

        messages.error(request, "Invalid threshold values. Please check the form.")
    else:
        form = RiskThresholdForm(instance=thresholds)

    return render(
        request,
        "core/admin_settings.html",
        {
            "form": form,
            "thresholds": thresholds,
        }
    )


@login_required
@role_required(["TEACHER", "ADMIN"])
def add_attendance(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        form = AttendanceForm(request.POST)

        if form.is_valid():
            attendance = form.save(commit=False)
            attendance.student = student
            try:
                attendance.save()

                AuditLog.objects.create(
                    user=request.user,
                    user_role=get_user_role(request.user),
                    action_type="CREATE",
                    action_result="SUCCESS",
                    affected_object_id=student.id,
                    description=f"Attendance added for {student} on {attendance.date}"
                )

                messages.success(request, "Attendance added successfully.")
                return redirect("student_detail", student_id=student.id)
            except Exception as e:
                messages.error(request, f"Error saving attendance: {str(e)}")
        else:
            messages.error(request, "Invalid attendance input. Please check the form.")
    else:
        form = AttendanceForm()

    return render(
        request,
        "core/add_attendance.html",
        {
            "form": form,
            "student": student,
        }
    )


@login_required
@role_required(["COUNSELOR", "ADMIN"])
def add_intervention(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        form = InterventionForm(request.POST)

        if form.is_valid():
            intervention = form.save(commit=False)
            intervention.student = student
            intervention.save()

            AuditLog.objects.create(
                user=request.user,
                user_role=get_user_role(request.user),
                action_type="CREATE",
                action_result="SUCCESS",
                affected_object_id=student.id,
                description=f"Intervention created for {student}"
            )

            messages.success(request, "Intervention created successfully.")
            return redirect("student_detail", student_id=student.id)

        messages.error(request, "Invalid intervention input. Please check the form.")
    else:
        form = InterventionForm()

    return render(
        request,
        "core/add_intervention.html",
        {
            "form": form,
            "student": student,
        }
    )


@login_required
@role_required(["COUNSELOR", "ADMIN"])
def edit_intervention(request, intervention_id):
    intervention = get_object_or_404(Intervention, id=intervention_id)
    student = intervention.student
    old_status = intervention.status

    if request.method == "POST":
        form = InterventionForm(request.POST, instance=intervention)

        if form.is_valid():
            updated_intervention = form.save()
            new_status = updated_intervention.status

            AuditLog.objects.create(
                user=request.user,
                user_role=get_user_role(request.user),
                action_type="UPDATE",
                action_result="SUCCESS",
                affected_object_id=student.id,
                description=f"Intervention updated for {student}. Status changed from {old_status} to {new_status}."
            )

            messages.success(request, "Intervention updated successfully.")
            return redirect("student_detail", student_id=student.id)

        messages.error(request, "Invalid intervention update. Please check the form.")
    else:
        form = InterventionForm(instance=intervention)

    return render(
        request,
        "core/edit_intervention.html",
        {
            "form": form,
            "student": student,
            "intervention": intervention,
        }
    )


@login_required
@role_required(["COUNSELOR", "ADMIN"])
def add_appointment(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        form = AppointmentForm(request.POST)

        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.student = student
            appointment.counselor = request.user
            appointment.save()

            AuditLog.objects.create(
                user=request.user,
                user_role=get_user_role(request.user),
                action_type="CREATE",
                action_result="SUCCESS",
                affected_object_id=student.id,
                description=f"Appointment created for {student}"
            )

            messages.success(request, "Appointment created successfully.")
            return redirect("student_detail", student_id=student.id)

        messages.error(request, "Invalid appointment input. Please check the form.")
    else:
        form = AppointmentForm()

    return render(
        request,
        "core/add_appointment.html",
        {
            "form": form,
            "student": student,
        }
    )


# ---- New Views to complete the Exam Requirements ----

@login_required
@role_required(["ADMIN"])
def upload_csv(request):
    """Handles CSV ingestion with schema validation and logs error details."""
    if request.method == "POST":
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            try:
                result = ingest_students_csv(csv_file, csv_file.name, request.user)
                msg = f"Ingestion complete: {result['accepted']} accepted, {result['rejected']} rejected."
                if result['rejected'] > 0:
                    messages.warning(request, f"{msg} Click audit logs to see validation errors.")
                else:
                    messages.success(request, msg)
                return redirect("dashboard")
            except ValidationError as ve:
                messages.error(request, str(ve))
            except Exception as e:
                messages.error(request, f"Failed to parse CSV: {str(e)}")
    else:
        form = CSVUploadForm()

    return render(request, "core/upload_csv.html", {"form": form})


@login_required
@role_required(["ADMIN", "COUNSELOR"])
def audit_log_list(request):
    """Lists audit log entries with action type filters and pagination."""
    action_type = request.GET.get("action_type", "")
    logs = AuditLog.objects.all().order_by("-created_at")

    if action_type:
        logs = logs.filter(action_type=action_type)

    paginator = Paginator(logs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    action_choices = AuditLog.ACTION_TYPES

    return render(
        request,
        "core/audit_log_list.html",
        {
            "page_obj": page_obj,
            "action_choices": action_choices,
            "selected_action_type": action_type
        }
    )


@login_required
def case_list(request):
    """View to list all student cases with status and assignee filters."""
    status = request.GET.get("status", "")
    assigned_to = request.GET.get("assigned_to", "")
    
    cases = Case.objects.all().order_by("-created_at")

    if status:
        cases = cases.filter(status=status)
    if assigned_to:
        cases = cases.filter(assigned_to_id=assigned_to)

    status_choices = Case.STATUS_CHOICES
    
    # Get all users who have cases assigned
    assignees_ids = Case.objects.values_list('assigned_to', flat=True).distinct()
    from django.contrib.auth.models import User
    assignees = User.objects.filter(id__in=assignees_ids)

    return render(
        request,
        "core/case_list.html",
        {
            "cases": cases,
            "status_choices": status_choices,
            "selected_status": status,
            "assignees": assignees,
            "selected_assigned_to": assigned_to,
        }
    )


@login_required
def case_detail(request, case_id):
    """View to display details about a specific Case, including its progress bar."""
    case = get_object_or_404(Case, id=case_id)
    role = get_user_role(request.user)

    # Determine which transitions are valid for the user's role
    allowed_transitions = []
    for option in ['NEW', 'IN_REVIEW', 'INTERVENTION_PLANNED', 'FOLLOW_UP', 'CLOSED']:
        can, _ = case.can_transition_to(option, role)
        if can:
            allowed_transitions.append(option)

    logs = AuditLog.objects.filter(case=case).order_by("-created_at")

    # Define steps for the progress bar
    progress_steps = [
        ('NEW', 'New'),
        ('IN_REVIEW', 'In Review'),
        ('INTERVENTION_PLANNED', 'Intervention Planned'),
        ('FOLLOW_UP', 'Follow-up'),
        ('CLOSED', 'Closed'),
    ]

    return render(
        request,
        "core/case_detail.html",
        {
            "case": case,
            "allowed_transitions": allowed_transitions,
            "logs": logs,
            "progress_steps": progress_steps,
        }
    )


@login_required
def case_transition(request, case_id):
    """Handles POST request to transition a case to a new status."""
    if request.method != "POST":
        return redirect("case_detail", case_id=case_id)

    case = get_object_or_404(Case, id=case_id)
    new_status = request.POST.get("status")
    role = get_user_role(request.user)

    try:
        case.transition_to(new_status, request.user, role)
        messages.success(request, f"Case status updated to '{new_status}' successfully.")
    except ValidationError as ve:
        messages.error(request, str(ve))

    return redirect("case_detail", case_id=case.id)


@login_required
@role_required(["ADMIN", "TEACHER"])
def add_case(request, student_id):
    """Allows creating a new Case for a student. Only accessible by ADMIN or TEACHER."""
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        form = CaseForm(request.POST)
        if form.is_valid():
            case = form.save(commit=False)
            case.student = student
            case.created_by = request.user
            case.save()

            AuditLog.objects.create(
                user=request.user,
                user_role=get_user_role(request.user),
                action_type="CREATE",
                action_result="SUCCESS",
                case=case,
                affected_object_id=case.id,
                description=f"Case #{case.id} created for {student} by {request.user.username}."
            )

            messages.success(request, "Case created successfully.")
            return redirect("student_detail", student_id=student.id)
        else:
            messages.error(request, "Invalid case input. Please check the form.")
    else:
        # Prepopulate student field and filter it to only this student
        form = CaseForm(initial={"student": student})
        form.fields['student'].queryset = Student.objects.filter(id=student.id)

    return render(
        request,
        "core/add_case.html",
        {
            "form": form,
            "student": student,
        }
    )


def health_check(request):
    """
    Public/unauthenticated endpoint returning database connectivity,
    record counts, and system status.
    """
    db_ok = True
    error_message = None

    try:
        # Check database connectivity
        connection.cursor()
    except Exception as e:
        db_ok = False
        error_message = str(e)

    status_code = 200 if db_ok else 500
    
    data = {
        "status": "healthy" if db_ok else "unhealthy",
        "database": "connected" if db_ok else "disconnected",
        "counts": {
            "students": Student.objects.count() if db_ok else 0,
            "alerts": Alert.objects.count() if db_ok else 0,
            "cases": Case.objects.count() if db_ok else 0,
            "interventions": Intervention.objects.count() if db_ok else 0,
            "audit_logs": AuditLog.objects.count() if db_ok else 0,
        }
    }
    if error_message:
        data["error"] = error_message

    return JsonResponse(data, status=status_code)