import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Profile, Student, Attendance, Alert, Intervention, Appointment, Case, AuditLog

class Command(BaseCommand):
    help = "Seeds the database with role-based users, students, attendances, appointments, alerts, interventions, and audit logs."

    def handle(self, *args, **options):
        self.stdout.write("Clearing existing dev data...")
        
        # Clear dev data (keep superusers)
        User.objects.filter(is_superuser=False).delete()
        Student.objects.all().delete()
        Attendance.objects.all().delete()
        Alert.objects.all().delete()
        Intervention.objects.all().delete()
        Appointment.objects.all().delete()
        Case.objects.all().delete()
        AuditLog.objects.all().delete()

        self.stdout.write("Creating role-based users...")
        
        # Create standard accounts
        admin_user = User.objects.create_user(username="admin_user", password="Test1234!")
        Profile.objects.create(user=admin_user, role="ADMIN")

        teacher_user = User.objects.create_user(username="teacher_user", password="Test1234!")
        Profile.objects.create(user=teacher_user, role="TEACHER")

        counselor_user = User.objects.create_user(username="counselor_user", password="Test1234!")
        Profile.objects.create(user=counselor_user, role="COUNSELOR")

        self.stdout.write("Creating synthetic students (Tunisian names)...")
        
        first_names = ["Youssef", "Amine", "Nour", "Fatma", "Mariem", "Ahmed", "Selim", "Omar", "Syrine", "Farah", "Chaouki", "Karim", "Yasmin", "Hedi", "Rania"]
        last_names = ["Ben Salem", "Trabelsi", "Ghrab", "Bayoudhi", "Jaziri", "Ellouze", "Bouaziz", "Rekik", "Masmoudi", "Kallel", "Abid", "Saidi", "Gharbi", "Ayadi"]

        students = []
        for i in range(15):
            fn = first_names[i % len(first_names)]
            ln = last_names[i % len(last_names)]
            dob = date(2010 + (i % 5), random.randint(1, 12), random.randint(1, 28))
            
            # Sensitive notes: only counselors/admins can see
            notes = f"Counselor Intake Notes for {fn}: Student expresses feelings of isolation and wants academic help."
            
            student = Student.objects.create(
                first_name=fn,
                last_name=ln,
                date_of_birth=dob,
                counselor_notes=notes,
                attendance_rate=100.0,
                average_grade=round(random.uniform(8.0, 18.0), 2)
            )
            students.append(student)

        self.stdout.write("Creating attendances (triggering high risk for some)...")
        
        # Student 0 (Youssef Ben Salem): make High Risk (3 absences out of 4 days)
        # Threshold: high risk is under 50% attendance rate
        for day in range(4):
            Attendance.objects.create(
                student=students[0],
                date=date(2026, 5, 1) + timedelta(days=day),
                present=(day == 0) # 25% attendance
            )

        # Student 1 (Amine Trabelsi): make Medium Risk (3 present, 1 absent = 75% attendance)
        for day in range(4):
            Attendance.objects.create(
                student=students[1],
                date=date(2026, 5, 1) + timedelta(days=day),
                present=(day != 0) # 75% attendance
            )

        # Other students: 100% attendance
        for student in students[2:]:
            for day in range(3):
                Attendance.objects.create(
                    student=student,
                    date=date(2026, 5, 1) + timedelta(days=day),
                    present=True
                )

        self.stdout.write("Creating appointments (triggering missed appointment alerts)...")
        
        # Student 2 (Nour Ghrab): Counselor schedules 3 appointments, Nour misses all 3, which triggers a HEALTH alert
        for i in range(3):
            Appointment.objects.create(
                student=students[2],
                counselor=counselor_user,
                date=date(2026, 5, 10) + timedelta(days=i),
                attended=False,
                notes=f"Missed follow-up #{i+1} without warning."
            )

        # Student 3 (Fatma Bayoudhi): Schedules 2 appointments, attends both
        for i in range(2):
            Appointment.objects.create(
                student=students[3],
                counselor=counselor_user,
                date=date(2026, 5, 12) + timedelta(days=i),
                attended=True,
                notes=f"Discussed career options. Fatma is doing well."
            )

        self.stdout.write("Creating workflow cases & transition timelines...")
        
        # Case 1: Student 0 (Youssef Ben Salem) - IN_REVIEW state
        case1 = Case.objects.create(
            student=students[0],
            title="Academic Support Plan for Youssef",
            description="Attendance has dropped significantly. Teacher flagged this case.",
            status="NEW",
            created_by=teacher_user,
            assigned_to=counselor_user
        )
        # Transition to IN_REVIEW
        case1.transition_to("IN_REVIEW", counselor_user, "COUNSELOR")

        # Case 2: Student 2 (Nour Ghrab) - INTERVENTION_PLANNED state
        case2 = Case.objects.create(
            student=students[2],
            title="Mental Health Follow-up for Nour",
            description="Missed 3 appointments consecutively. Needs home visitation plan.",
            status="NEW",
            created_by=counselor_user,
            assigned_to=counselor_user
        )
        case2.transition_to("IN_REVIEW", counselor_user, "COUNSELOR")
        case2.transition_to("INTERVENTION_PLANNED", counselor_user, "COUNSELOR")

        # Case 3: Student 3 (Fatma Bayoudhi) - CLOSED state
        case3 = Case.objects.create(
            student=students[3],
            title="Intake Review for Fatma",
            description="Intake assessment closed out as student is fully adjusted.",
            status="NEW",
            created_by=counselor_user,
            assigned_to=counselor_user
        )
        case3.transition_to("IN_REVIEW", counselor_user, "COUNSELOR")
        case3.transition_to("INTERVENTION_PLANNED", counselor_user, "COUNSELOR")
        case3.transition_to("FOLLOW_UP", counselor_user, "COUNSELOR")
        case3.transition_to("CLOSED", counselor_user, "COUNSELOR")

        self.stdout.write("Creating interventions...")
        
        # Active intervention for Nour (Case 2)
        Intervention.objects.create(
            student=students[2],
            title="Home visit and parent outreach",
            description="Counselor will reach out to Nour's family regarding missed follow-ups.",
            recommendation_reason="Nour missed 3 clinical appointments.",
            status="IN_PROGRESS"
        )

        self.stdout.write(self.style.SUCCESS("Database seeded successfully!"))
        self.stdout.write(f"Users created: admin_user, teacher_user, counselor_user (Password: Test1234!)")
