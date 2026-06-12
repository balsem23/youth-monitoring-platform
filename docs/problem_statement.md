# Problem Statement

## Population

Tunisian students and young people aged **10–18 years** in secondary school settings. The platform is designed for schools, youth centers, and counseling units that monitor student wellbeing.

## Problem

Two interrelated behavioral risks:

1. **Education disengagement**: declining attendance rates and academic performance that signal dropout risk.
2. **Missed health/mental-health follow-up**: untreated or unsupported health needs indicated by missed appointments with counselors or health staff.

## Decision Makers

| Role | Responsibility |
|---|---|
| **Teacher** | Records daily attendance, observes student behavior, initiates cases |
| **Counselor** | Validates alerts, creates intervention plans, schedules follow-up appointments, transitions case workflows |
| **Admin/Manager** | Configures risk thresholds, uploads student datasets, monitors platform metrics, manages users |

## Operational Workflow

1. **Intake & Validation**: Admin uploads student records via CSV (validated for schema, ranges, and formats). Teachers record daily attendance through forms.
2. **Risk Assessment**: The platform calculates attendance rates from recorded data and applies rule-based threshold scoring. When attendance drops below the configurable HIGH-risk threshold, an EDUCATION alert is automatically generated.
3. **Alert & Intervention**: Counselors review alerts, create intervention plans with recommendation explanations, and schedule follow-up appointments. After 3 missed appointments, a HEALTH alert triggers a referral workflow.
4. **Case Management**: Teachers or admins open a workflow case. Cases follow a strict state machine: NEW → IN_REVIEW → INTERVENTION_PLANNED → FOLLOW_UP → CLOSED. Each transition is validated by role permissions and logged to an audit trail.
5. **Monitoring & Decision Support**: The dashboard displays KPIs (workflow completion %, data validation pass %, alert resolution %, security incident count). Operators can export filtered reports.

## Expected Value

- **Faster detection**: Automated risk alerts reduce the time between observation and intervention.
- **Better follow-up**: Missed-appointment tracking ensures counselors follow up with at-risk students.
- **Safer intervention tracking**: Role-based permissions, audit logging, and state-machine validation prevent unauthorized or incorrect actions.
- **Measurable impact**: Dashboard metrics allow stakeholders to track system performance.

## Validation Rules

- **CSV ingestion**: A row is accepted only if all required columns are present with valid types (YYYY-MM-DD date, 0–100 attendance/grade, non-empty names). Rows with errors are rejected with specific messages. Missing required columns raises a failure.
- **Attendance risk**: HIGH risk when attendance_rate < high_risk_threshold (default 50%). MEDIUM when < medium_risk_threshold (default 75%). LOW otherwise.
- **Health alert**: A HEALTH alert triggers after 3 or more missed appointments for the same student (unresolved).
- **Case transitions**: Only the allowed next state per `VALID_TRANSITIONS` is permitted. Only roles listed in `TRANSITION_ROLES` may perform the step. Any violation is blocked and logged as a SECURITY failure.
- **Role-based access**: Unauthorized page access is redirected, the attempt is logged to AuditLog with action_type=SECURITY and action_result=FAILURE.

## Data & Ethics Boundary

- All data is **synthetic** — no real personal, medical, or confidential records are stored.
- `counselor_notes` is a sensitive field: visible only to ADMIN and COUNSELOR roles; redacted for TEACHER.
- The platform provides **decision support only** — it does not replace human judgment. Teachers, counselors, and administrators remain responsible for all final decisions.
- Risk scores are **indicators only** and may contain false positives or false negatives.
- Access follows the **principle of least privilege**: each role can only access actions related to its responsibility.
- Unauthorized actions are **blocked and recorded** in the audit trail.
