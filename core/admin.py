from django.contrib import admin
from .models import Profile, Student, Attendance, Alert, Intervention, Appointment, AuditLog

admin.site.register(Profile)
admin.site.register(Student)
admin.site.register(Attendance)
admin.site.register(Alert)
admin.site.register(Intervention)
admin.site.register(Appointment)
admin.site.register(AuditLog)