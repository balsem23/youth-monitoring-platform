# Data Dictionary — YouthCare database schema

This document describes the database tables, fields, constraints, and design details for all models in the YouthCare application.

---

## 1. Profile
* **Purpose:** Extends the standard Django `User` model to associate roles (ADMIN, TEACHER, COUNSELOR) to accounts.
* **Database Table:** `core_profile`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `user` | OneToOneField (User) | Foreign Key, CASCADE | Reference to the built-in Django User auth record. |
| `role` | CharField(20) | Choices: `ADMIN`, `TEACHER`, `COUNSELOR` | The role assigned to the user, governing RBAC views and transitions. |

---

## 2. Student
* **Purpose:** Core table representing monitored students in Tunisian schools.
* **Database Table:** `core_student`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `first_name` | CharField(100) | Non-empty | First name of the student. |
| `last_name` | CharField(100) | Non-empty | Last name of the student. |
| `date_of_birth` | DateField | YYYY-MM-DD | Date of birth. |
| `attendance_rate` | FloatField | Default: 100.0, Range: 0 to 100 | The calculated attendance rate (%). Updated by signal check. |
| `average_grade` | FloatField | Default: 0.0, Range: 0 to 100 | Cumulative average academic grade. |
| `risk_level` | CharField(20) | Choices: `LOW`, `MEDIUM`, `HIGH`, Default: `LOW` | Automatically calculated risk level based on settings thresholds. |
| `counselor_notes` | TextField | Blank allowed, Default: "" | Sensitive counselor intake comments. Redacted for teachers. |

---

## 3. Case
* **Purpose:** Workflows for tracking support interventions on at-risk students, subject to state machine validation.
* **Database Table:** `core_case`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `student` | ForeignKey (Student) | CASCADE | Reference to the student this workflow tracks. |
| `title` | CharField(200) | Non-empty | Title of the case. |
| `description` | TextField | Blank allowed | Description of the case and intake symptoms. |
| `status` | CharField(30) | Choices: `NEW`, `IN_REVIEW`, `INTERVENTION_PLANNED`, `FOLLOW_UP`, `CLOSED` | The current state in the state-machine. |
| `assigned_to` | ForeignKey (User) | SET_NULL, Null allowed | Reference to the staff member tracking the timeline. |
| `created_by` | ForeignKey (User) | SET_NULL, Null allowed | Reference to the staff member who opened the case. |
| `created_at` | DateTimeField | Auto-add now | Timestamp of case initialization. |
| `updated_at` | DateTimeField | Auto-update now | Timestamp of last modification. |

---

## 4. Attendance
* **Purpose:** Daily attendance records for students.
* **Database Table:** `core_attendance`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `student` | ForeignKey (Student) | CASCADE | Reference to the student. |
| `date` | DateField | YYYY-MM-DD | Attendance date. |
| `present` | BooleanField | Default: True | Flag showing if student was present (True) or absent (False). |

* **Index / Unique Constraints:** `unique_together = ['student', 'date']` (ensures a student has only one attendance status per day).

---

## 5. Alert
* **Purpose:** System-generated risk flags to notify decision-makers.
* **Database Table:** `core_alert`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `student` | ForeignKey (Student) | CASCADE | Reference to the flagged student. |
| `alert_type` | CharField(20) | Choices: `EDUCATION`, `HEALTH` | Flag type (Education dropout risk or health missed-referrals). |
| `message` | TextField | Non-empty | Automated warning details. |
| `is_resolved` | BooleanField | Default: False | Flag showing if the alert has been closed by staff. |
| `created_at` | DateTimeField | Auto-add now | Alert creation timestamp. |

---

## 6. Intervention
* **Purpose:** Documented intervention action plans created for students by counselors.
* **Database Table:** `core_intervention`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `student` | ForeignKey (Student) | CASCADE | Reference to the student. |
| `title` | CharField(200) | Non-empty | Summary of the plan. |
| `description` | TextField | Non-empty | Specific actions to be taken (outreach, study hours). |
| `recommendation_reason` | TextField | Blank allowed | Rationale supporting the intervention. |
| `status` | CharField(20) | Choices: `OPEN`, `IN_PROGRESS`, `CLOSED` | The current operational state of the intervention. |
| `created_at` | DateTimeField | Auto-add now | Intervention creation timestamp. |

---

## 7. Appointment
* **Purpose:** Structured clinical or guidance appointments between counselors and students.
* **Database Table:** `core_appointment`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `student` | ForeignKey (Student) | CASCADE | Reference to the student. |
| `counselor` | ForeignKey (User) | CASCADE | Reference to the counselor hosting the session. |
| `date` | DateField | YYYY-MM-DD | Date of the session. |
| `attended` | BooleanField | Default: True | Flag showing if student attended (True) or missed (False). |
| `notes` | TextField | Blank allowed | Clinical counseling summary. |

---

## 8. AuditLog
* **Purpose:** System-wide secure audit trail tracking events, transitions, and security checks.
* **Database Table:** `core_auditlog`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `user` | ForeignKey (User) | SET_NULL, Null allowed | User who performed the action. |
| `user_role` | CharField(20) | Blank allowed | Role of the user at the time of the action (ADMIN, etc.). |
| `action_type` | CharField(20) | Choices: `CREATE`, `UPDATE`, `ALERT`, `SECURITY`, `INGESTION` | General category of the action. |
| `description` | TextField | Non-empty | Detailed multiline log statement. |
| `action_result` | CharField(10) | Choices: `SUCCESS`, `FAILURE`, Default: `SUCCESS` | Result status (used to track blocked access). |
| `case` | ForeignKey (Case) | SET_NULL, Null allowed | Related case ID if applicable. |
| `affected_object_id` | IntegerField | Null allowed | ID of the affected student, user, or threshold record. |
| `created_at` | DateTimeField | Auto-add now | Log timestamp. |

---

## 9. DataIngestionLog
* **Purpose:** Tracking CSV batch uploads and validation stats.
* **Database Table:** `core_dataingestionlog`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `user` | ForeignKey (User) | SET_NULL, Null allowed | Admin user who performed the upload. |
| `file_name` | CharField(255) | Non-empty | Original uploaded filename. |
| `total_rows` | IntegerField | Default: 0 | Total parsed records. |
| `accepted_rows` | IntegerField | Default: 0 | Number of rows that passed validation and were stored. |
| `rejected_rows` | IntegerField | Default: 0 | Number of invalid rows rejected. |
| `errors` | TextField | Blank allowed | Detailed multiline validation errors per row. |
| `created_at` | DateTimeField | Auto-add now | Upload timestamp. |

---

## 10. RiskThreshold
* **Purpose:** Global configuration governing automated risk calculations.
* **Database Table:** `core_riskthreshold`

| Field Name | Data Type | Constraints | Description |
|---|---|---|---|
| `id` | BigAutoField | Primary Key, Auto-increment | Internal unique record identifier. |
| `high_risk_threshold` | FloatField | Default: 50.0 | Attendance rate percentage under which high risk triggers (<50%). |
| `medium_risk_threshold` | FloatField | Default: 75.0 | Attendance rate percentage under which medium risk triggers (<75%). |
