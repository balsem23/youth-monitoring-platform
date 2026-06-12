# Threat Model — YouthCare platform

This document describes the threat modeling, assets, abuse cases, and security controls for the YouthCare student monitoring platform.

## 1. System Assets

| Asset Name | Classification | Description |
|---|---|---|
| Student Directory | Internal | General academic and demographic records (first name, last name, DOB, attendance, grades). |
| Counselor Notes | Confidential | Highly sensitive intake and clinical follow-up notes written by counseling staff. |
| Workflow Cases | Internal | Tracked cases representing active student risk interventions and state changes. |
| Audit Trail Logs | Sensitive | System-wide audit logs detailing user logins, database actions, state transitions, and security blocks. |
| System Configuration | Administrative | Risk thresholds (high, medium) governing automatic alert spawns. |

---

## 2. Abuse Cases & Threat Analysis

### Threat 1: Unauthorized access to student clinical records
* **Objective:** An unauthorized user (e.g. a teacher or external actor) attempts to view sensitive counselor notes.
* **Impact:** Violation of student privacy regulations (GDPR/Tunisian local privacy laws) and breach of trust.
* **Mitigation:**
  * Strict decorator-based path checks (`@role_required`).
  * Field-level redaction at the controller/view layer. If a user's role is not `COUNSELOR` or `ADMIN`, the `counselor_notes` attribute is overwritten in memory with `[REDACTED]` before template rendering.

### Threat 2: Illegal state machine workflow bypassing
* **Objective:** A malicious user bypasses standard workflow progression (e.g. transitions a case from `NEW` to `CLOSED` without review, or a teacher attempts counselor-only transitions).
* **Impact:** Silent workflow failures, failure of care pathway continuity, and untracked child-safety issues.
* **Mitigation:**
  * Transition logic is encapsulated inside the `Case.transition_to()` model method.
  * Explicit role checks and transition-step validity checks are performed using the `Case.VALID_TRANSITIONS` and `Case.TRANSITION_ROLES` matrices.
  * Blocked attempts raise a `ValidationError` and automatically spawn a `SECURITY` action type `FAILURE` result entry in the `AuditLog`.

### Threat 3: Manipulation of system risk thresholds
* **Objective:** An unauthorized user (e.g. teacher or counselor) modifies risk thresholds to disable alerts.
* **Impact:** System fails to flag at-risk students, leading to delayed or absent interventions.
* **Mitigation:**
  * The `admin_settings` view is guarded strictly by `@role_required(["ADMIN"])`.
  * Modification attempts by other roles are blocked and log a high-priority security audit alert.

### Threat 4: CSRF & Session Hijacking
* **Objective:** An attacker tricks a logged-in user into performing actions (e.g. deleting records or updating states) or hijacks their session.
* **Impact:** Unauthorized operations performed on behalf of legitimate staff.
* **Mitigation:**
  * Standard Django middlewares: `SessionMiddleware`, `AuthenticationMiddleware`, and `CsrfViewMiddleware`.
  * All POST forms require the `{% csrf_token %}` template tags.

---

## 3. Security posture summary
The YouthCare application adopts the **Principle of Least Privilege** (least privilege model) across three distinct user roles:
1. **Teacher:** Can view student registry, add daily attendance, and open cases. Restricted from clinical logs, CSV ingestion, settings, and interventions.
2. **Counselor:** Can view student registry, view counselor notes, schedule appointments, create/edit interventions, and advance cases from `IN_REVIEW` onwards. Restricted from CSV ingestion and settings.
3. **Admin:** Full privileges, including CSV ingestion, changing system risk thresholds, and managing database structures.
