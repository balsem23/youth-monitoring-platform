from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError


class Profile(models.Model):
    ROLE_CHOICES = [
        #onetoone field
        ('ADMIN', 'Admin'),
        ('TEACHER', 'Teacher'),
        ('COUNSELOR', 'Counselor'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class RiskThreshold(models.Model):
    high_risk_threshold = models.FloatField(default=50)
    medium_risk_threshold = models.FloatField(default=75)

    def __str__(self):
        return "Risk Threshold Settings"

    @classmethod
    def get_settings(cls):
        settings, created = cls.objects.get_or_create(id=1)
        return settings


class Student(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    attendance_rate = models.FloatField(default=100)
    average_grade = models.FloatField(default=0)

    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low'),
            ('MEDIUM', 'Medium'),
            ('HIGH', 'High'),
        ],
        default='LOW'
    )

    # Sensitive field — should only be visible to COUNSELOR and ADMIN
    counselor_notes = models.TextField(
        blank=True,
        default="",
        help_text="Confidential notes, visible only to counselors and admins."
    )

    @property
    def risk_explanation(self):
        thresholds = RiskThreshold.get_settings()

        if self.attendance_rate < thresholds.high_risk_threshold:
            return (
                f"High risk because attendance is below "
                f"{thresholds.high_risk_threshold}%."
            )

        elif self.attendance_rate < thresholds.medium_risk_threshold:
            return (
                f"Medium risk because attendance is between "
                f"{thresholds.high_risk_threshold}% and "
                f"{thresholds.medium_risk_threshold}%."
            )

        return (
            f"Low risk because attendance is "
            f"{thresholds.medium_risk_threshold}% or higher."
        )

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Case(models.Model):
    """
    Represents a tracked case for a student, following an explicit
    state machine: NEW -> IN_REVIEW -> INTERVENTION_PLANNED -> FOLLOW_UP -> CLOSED.
    Each transition is validated and audited.
    """
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('IN_REVIEW', 'In Review'),
        ('INTERVENTION_PLANNED', 'Intervention Planned'),
        ('FOLLOW_UP', 'Follow-up'),
        ('CLOSED', 'Closed'),
    ]

    # Valid transitions: from_state -> [allowed_to_states]
    VALID_TRANSITIONS = {
        'NEW': ['IN_REVIEW'],
        'IN_REVIEW': ['INTERVENTION_PLANNED'],
        'INTERVENTION_PLANNED': ['FOLLOW_UP'],
        'FOLLOW_UP': ['CLOSED'],
        'CLOSED': [],
    }

    # Roles allowed to perform each transition
    TRANSITION_ROLES = {
        ('NEW', 'IN_REVIEW'): ['TEACHER', 'COUNSELOR', 'ADMIN'],
        ('IN_REVIEW', 'INTERVENTION_PLANNED'): ['COUNSELOR', 'ADMIN'],
        ('INTERVENTION_PLANNED', 'FOLLOW_UP'): ['COUNSELOR', 'ADMIN'],
        ('FOLLOW_UP', 'CLOSED'): ['COUNSELOR', 'ADMIN'],
    }

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='cases'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='NEW'
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cases'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_cases'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def can_transition_to(self, new_status, user_role):
        """Check if the transition is valid for the given role."""
        allowed_statuses = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed_statuses:
            return False, f"Cannot move from '{self.get_status_display()}' to '{new_status}'. Allowed: {allowed_statuses}"

        allowed_roles = self.TRANSITION_ROLES.get(
            (self.status, new_status), []
        )
        if user_role not in allowed_roles:
            return False, f"Role '{user_role}' is not allowed to perform this transition. Allowed roles: {allowed_roles}"

        return True, "Transition allowed."

    def transition_to(self, new_status, user, user_role):
        """
        Attempt to transition the case to a new status.
        Raises ValidationError if the transition is invalid.
        """
        can, reason = self.can_transition_to(new_status, user_role)
        if not can:
            # Log the blocked transition
            AuditLog.objects.create(
                user=user,
                user_role=user_role,
                action_type='SECURITY',
                case=self,
                affected_object_id=self.id,
                action_result='FAILURE',
                description=(
                    f"BLOCKED case transition for case #{self.id} "
                    f"({self.student}). "
                    f"Attempted: {self.status} -> {new_status}. "
                    f"Reason: {reason}"
                )
            )
            raise ValidationError(reason)

        old_status = self.status
        self.status = new_status
        self.save()

        # Log the successful transition
        AuditLog.objects.create(
            user=user,
            user_role=user_role,
            action_type='UPDATE',
            case=self,
            affected_object_id=self.id,
            action_result='SUCCESS',
            description=(
                f"Case #{self.id} ({self.student}) transitioned "
                f"from {old_status} to {new_status}."
            )
        )

    def __str__(self):
        return f"Case #{self.id} - {self.student} ({self.status})"


class Attendance(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    date = models.DateField()
    present = models.BooleanField(default=True)

    class Meta:
        unique_together = ['student', 'date']

    def __str__(self):
        return f"{self.student} - {self.date}"


class Alert(models.Model):
    ALERT_TYPES = [
        ('EDUCATION', 'Education Risk'),
        ('HEALTH', 'Health Follow-up'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.alert_type}"


class Intervention(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('CLOSED', 'Closed'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='interventions'
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    recommendation_reason = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OPEN'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.title}"


class Appointment(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    counselor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='counselor_appointments'
    )
    date = models.DateField()
    attended = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.student} - {self.date}"


class AuditLog(models.Model):
    ACTION_TYPES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('ALERT', 'Alert'),
        ('SECURITY', 'Security'),
        ('INGESTION', 'Data Ingestion'),
    ]

    RESULT_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILURE', 'Failure'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    user_role = models.CharField(max_length=20, blank=True, default="")
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField()
    action_result = models.CharField(
        max_length=10,
        choices=RESULT_CHOICES,
        default='SUCCESS'
    )
    case = models.ForeignKey(
        'Case',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    affected_object_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} [{self.action_result}] - {self.created_at}"


class DataIngestionLog(models.Model):
    """Tracks CSV/data file uploads and their validation results."""
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    file_name = models.CharField(max_length=255)
    total_rows = models.IntegerField(default=0)
    accepted_rows = models.IntegerField(default=0)
    rejected_rows = models.IntegerField(default=0)
    errors = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def pass_rate(self):
        if self.total_rows == 0:
            return 0
        return round((self.accepted_rows / self.total_rows) * 100, 1)

    def __str__(self):
        return (
            f"{self.file_name} — "
            f"{self.accepted_rows}/{self.total_rows} accepted"
        )


# ---- Signals ----

@receiver(post_save, sender=Attendance)
def check_attendance_risk(sender, instance, created, **kwargs):
    if not created:
        return

    student = instance.student
    thresholds = RiskThreshold.get_settings()

    total_records = Attendance.objects.filter(
        student=student
    ).count()

    absent_records = Attendance.objects.filter(
        student=student,
        present=False
    ).count()

    if total_records == 0:
        return

    attendance_rate = (
        (total_records - absent_records) / total_records
    ) * 100

    student.attendance_rate = attendance_rate

    if attendance_rate < thresholds.high_risk_threshold:
        student.risk_level = "HIGH"

        existing_alert = Alert.objects.filter(
            student=student,
            alert_type="EDUCATION",
            is_resolved=False
        ).first()

        if existing_alert:
            existing_alert.message = (
                f"High dropout risk detected. Attendance rate: {attendance_rate:.2f}%"
            )
            existing_alert.save()
        else:
            Alert.objects.create(
                student=student,
                alert_type="EDUCATION",
                message=f"High dropout risk detected. Attendance rate: {attendance_rate:.2f}%"
            )

            AuditLog.objects.create(
                action_type="ALERT",
                action_result="SUCCESS",
                affected_object_id=student.id,
                description=f"Education alert created for {student}. Attendance rate: {attendance_rate:.2f}%"
            )

    elif attendance_rate < thresholds.medium_risk_threshold:
        student.risk_level = "MEDIUM"

    else:
        student.risk_level = "LOW"

    student.save()


@receiver(post_save, sender=Appointment)
def check_missed_appointments(sender, instance, created, **kwargs):
    if not created:
        return

    student = instance.student

    if not instance.attended:
        AuditLog.objects.create(
            action_type="CREATE",
            action_result="SUCCESS",
            affected_object_id=student.id,
            description=f"Missed appointment recorded for {student} on {instance.date}."
        )

    missed_count = Appointment.objects.filter(
        student=student,
        attended=False
    ).count()

    if missed_count >= 3:
        existing_alert = Alert.objects.filter(
            student=student,
            alert_type="HEALTH",
            is_resolved=False
        ).exists()

        if not existing_alert:
            Alert.objects.create(
                student=student,
                alert_type="HEALTH",
                message=f"Student missed {missed_count} appointments. Referral/reminder required."
            )

            AuditLog.objects.create(
                action_type="ALERT",
                action_result="SUCCESS",
                affected_object_id=student.id,
                description=f"Health alert created for {student}. Missed appointments: {missed_count}"
            )