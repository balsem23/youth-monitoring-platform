import os # for file handling in tests
import io # for in-memory file handling in CSV tests
from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError

from .models import (
    Profile,
    Student,
    Attendance,
    Appointment,
    Alert,
    Intervention,
    AuditLog,
    Case,
    DataIngestionLog,
    RiskThreshold
)
from .data_ingestion import ingest_students_csv


class CoreSystemTests(TestCase):

    def setUp(self):
        # Create user accounts for testing
        self.admin = User.objects.create_user(username="admin_test", password="TestPassword123")
        Profile.objects.create(user=self.admin, role="ADMIN")

        self.teacher = User.objects.create_user(username="teacher_test", password="TestPassword123")
        Profile.objects.create(user=self.teacher, role="TEACHER")

        self.counselor = User.objects.create_user(username="counselor_test", password="TestPassword123")
        Profile.objects.create(user=self.counselor, role="COUNSELOR")

        # Create a basic student
        self.student = Student.objects.create(
            first_name="Hedi",
            
            
            last_name="Jaziri",
            date_of_birth=date(2011, 4, 10),
            counselor_notes="Needs guidance."
        )

    # 1. Automated Alert & Signal Tests
    def test_attendance_triggers_high_risk_and_alert(self):
        # High risk threshold default is 50%
        # Let's add 3 absent and 1 present (25% attendance rate)
        #error insert in the real db 
        for i in range(3):
            Attendance.objects.create(student=self.student, date=date(2026, 6, 1) + timedelta(days=i), present=False)
        Attendance.objects.create(student=self.student, date=date(2026, 6, 4), present=True)

        self.student.refresh_from_db()
        self.assertEqual(self.student.risk_level, "HIGH")

        # Verify education alert exists
        alert = Alert.objects.filter(student=self.student, alert_type="EDUCATION", is_resolved=False).first()
        self.assertIsNotNone(alert)
        self.assertIn("High dropout risk detected", alert.message)

        # Verify Audit Log entry created for the alert
        log = AuditLog.objects.filter(action_type="ALERT", affected_object_id=self.student.id).first()
        self.assertIsNotNone(log)

    def test_three_missed_appointments_triggers_health_alert(self):
        # 3 missed appointments should trigger health alert
        for i in range(3):
            Appointment.objects.create(
                student=self.student,
                counselor=self.counselor,
                date=date(2026, 6, 10) + timedelta(days=i),
                attended=False,
                notes="Missed"
            )

        alert = Alert.objects.filter(student=self.student, alert_type="HEALTH", is_resolved=False).first()
        self.assertIsNotNone(alert)
        self.assertIn("missed 3 appointments", alert.message.lower())

        log = AuditLog.objects.filter(action_type="ALERT", affected_object_id=self.student.id, description__icontains="health").first()
        self.assertIsNotNone(log)

    # 2. Case State Machine Transition Tests
    def test_valid_state_machine_transition_sequence(self):
        case = Case.objects.create(
            student=self.student,
            title="Support workflow",
            description="Intake case",
            status="NEW",
            created_by=self.teacher,
            assigned_to=self.counselor
        )

        # NEW -> IN_REVIEW (Teacher, Counselor, Admin allowed)
        case.transition_to("IN_REVIEW", self.teacher, "TEACHER")
        self.assertEqual(case.status, "IN_REVIEW")

        # IN_REVIEW -> INTERVENTION_PLANNED (Counselor, Admin allowed)
        case.transition_to("INTERVENTION_PLANNED", self.counselor, "COUNSELOR")
        self.assertEqual(case.status, "INTERVENTION_PLANNED")

        # INTERVENTION_PLANNED -> FOLLOW_UP (Counselor, Admin allowed)
        case.transition_to("FOLLOW_UP", self.counselor, "COUNSELOR")
        self.assertEqual(case.status, "FOLLOW_UP")

        # FOLLOW_UP -> CLOSED (Counselor, Admin allowed)
        case.transition_to("CLOSED", self.counselor, "COUNSELOR")
        self.assertEqual(case.status, "CLOSED")

    def test_invalid_state_transition_raises_validation_error(self):
        case = Case.objects.create(
            student=self.student,
            title="Support workflow",
            description="Intake case",
            status="NEW",
            created_by=self.teacher,
            assigned_to=self.counselor
        )

        # Illegal skip: NEW -> CLOSED directly
        with self.assertRaises(ValidationError):
            case.transition_to("CLOSED", self.counselor, "COUNSELOR")

        # Verify a FAILURE log was created in AuditLog for security tracking
        log = AuditLog.objects.filter(
            action_type="SECURITY",
            action_result="FAILURE",
            case=case
        ).first()
        self.assertIsNotNone(log)
        self.assertIn("BLOCKED case transition", log.description)

    def test_role_boundary_enforcement_on_transitions(self):
        case = Case.objects.create(
            student=self.student,
            title="Support workflow",
            description="Intake case",
            status="IN_REVIEW",
            created_by=self.teacher,
            assigned_to=self.counselor
        )

        # Teacher tries to transition IN_REVIEW -> INTERVENTION_PLANNED (not allowed for TEACHER)
        with self.assertRaises(ValidationError):
            case.transition_to("INTERVENTION_PLANNED", self.teacher, "TEACHER")

        # Verify blocked action logged
        log = AuditLog.objects.filter(
            action_type="SECURITY",
            action_result="FAILURE",
            user=self.teacher,
            case=case
        ).first()
        self.assertIsNotNone(log)

    # 3. CSV Ingestion Validation (Success & Failure Injections)
    def test_valid_csv_ingestion(self):
        csv_data = (
            "first_name,last_name,date_of_birth,attendance_rate,average_grade\n"
            "Anis,Trabelsi,2010-05-15,85.5,12.4\n"
            "Farah,Abid,2011-09-20,99.0,15.8\n"
        )
        file_obj = io.StringIO(csv_data)
        
        result = ingest_students_csv(file_obj, "test_valid.csv", self.admin)
        self.assertEqual(result['accepted'], 2)
        self.assertEqual(result['rejected'], 0)
        
        # Verify student records created in DB
        s1 = Student.objects.filter(first_name="Anis", last_name="Trabelsi").first()
        self.assertIsNotNone(s1)
        self.assertEqual(s1.attendance_rate, 85.5)
        self.assertEqual(s1.average_grade, 12.4)

        # IngestionLog check
        ing_log = DataIngestionLog.objects.filter(file_name="test_valid.csv").first()
        self.assertIsNotNone(ing_log)
        self.assertEqual(ing_log.accepted_rows, 2)
        self.assertEqual(ing_log.rejected_rows, 0)

    def test_malformed_csv_failure_injection(self):
        csv_data = (
            "first_name,last_name,date_of_birth,attendance_rate,average_grade\n"
            ",Trabelsi,2010-05-15,85.5,12.4\n"           # empty first name
            "Anis,Trabelsi,2010/05/15,85.5,12.4\n"         # wrong date format
            "Farah,Abid,2011-09-20,120.0,15.8\n"           # attendance rate > 100
            "Karim,Saidi,2011-09-20,95.0,-2.0\n"            # grade < 0
        )
        file_obj = io.StringIO(csv_data)
        
        result = ingest_students_csv(file_obj, "test_malformed.csv", self.admin)
        self.assertEqual(result['accepted'], 0)
        self.assertEqual(result['rejected'], 4)
        self.assertEqual(len(result['errors']), 4)

        # IngestionLog check
        ing_log = DataIngestionLog.objects.filter(file_name="test_malformed.csv").first()
        self.assertEqual(ing_log.rejected_rows, 4)
        self.assertIn("Row 2: First name is empty", ing_log.errors)
        self.assertIn("Row 3: Invalid date format", ing_log.errors)
        self.assertIn("Row 4: Attendance rate 120.0 must be between 0 and 100", ing_log.errors)
        self.assertIn("Row 5: Average grade -2.0 must be between 0 and 100", ing_log.errors)

    def test_csv_missing_header_rejection(self):
        csv_data = (
            "first_name,last_name,attendance_rate,average_grade\n" # missing date_of_birth
            "Anis,Trabelsi,85.5,12.4\n"
        )
        file_obj = io.StringIO(csv_data)
        
        with self.assertRaises(ValidationError):
            ingest_students_csv(file_obj, "test_missing_header.csv", self.admin)
            
        # Verify Audit Log entry logged the ingestion failure
        log = AuditLog.objects.filter(action_type="INGESTION", action_result="FAILURE").first()
        self.assertIsNotNone(log)
        self.assertIn("Missing required columns", log.description)

    # 4. Privacy by Design & Redaction Tests
    def test_teacher_sees_redacted_counselor_notes(self):
        client = Client()
        client.login(username="teacher_test", password="TestPassword123")
        
        response = client.get(reverse("student_detail", args=[self.student.id]))
        self.assertEqual(response.status_code, 200)
        # Verify notes are redacted in context
        student_in_context = response.context['student']
        self.assertEqual(student_in_context.counselor_notes, "[REDACTED — UNAUTHORIZED ROLE]")
        self.assertTrue(response.context['is_notes_redacted'])

    def test_counselor_sees_full_counselor_notes(self):
        client = Client()
        client.login(username="counselor_test", password="TestPassword123")
        
        response = client.get(reverse("student_detail", args=[self.student.id]))
        self.assertEqual(response.status_code, 200)
        # Verify notes are fully visible
        student_in_context = response.context['student']
        self.assertEqual(student_in_context.counselor_notes, "Needs guidance.")
        self.assertFalse(response.context['is_notes_redacted'])

    # 5. Access Control Permissions Matrix Tests
    def test_teacher_views_are_restricted(self):
        client = Client()
        client.login(username="teacher_test", password="TestPassword123")
        
        # Teacher cannot access settings
        response = client.get(reverse("admin_settings"))
        self.assertEqual(response.status_code, 302) # Redirected
        
        # Teacher cannot access CSV upload
        response = client.get(reverse("upload_csv"))
        self.assertEqual(response.status_code, 302) # Redirected

        # Teacher cannot add intervention
        response = client.get(reverse("add_intervention", args=[self.student.id]))
        self.assertEqual(response.status_code, 302) # Redirected

        # Teacher cannot add appointment
        response = client.get(reverse("add_appointment", args=[self.student.id]))
        self.assertEqual(response.status_code, 302) # Redirected

        # Verify a SECURITY AuditLog entry exists for unauthorized attempt
        log = AuditLog.objects.filter(user=self.teacher, action_type="SECURITY", description__icontains="BLOCKED").first()
        self.assertIsNotNone(log)

    def test_counselor_views_are_restricted(self):
        client = Client()
        client.login(username="counselor_test", password="TestPassword123")

        # Counselor cannot access admin settings
        response = client.get(reverse("admin_settings"))
        self.assertEqual(response.status_code, 302) # Redirected

        # Counselor cannot upload CSV
        response = client.get(reverse("upload_csv"))
        self.assertEqual(response.status_code, 302) # Redirected

        # Counselor CAN add intervention
        response = client.get(reverse("add_intervention", args=[self.student.id]))
        self.assertEqual(response.status_code, 200)

        # Counselor CAN view audit logs
        response = client.get(reverse("audit_log_list"))
        self.assertEqual(response.status_code, 200)

    # 6. Observability Health Check Endpoint Test
    def test_health_check_endpoint(self):
        client = Client()
        response = client.get(reverse("health_check"))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "connected")
        self.assertIn("counts", data)
        self.assertEqual(data["counts"]["students"], 1)