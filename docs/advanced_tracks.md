# Advanced Tracks — Evidence Summary

The project implements **at least two advanced tracks** as required by the exam specification (Section 14):

---

## Track B — Security and Privacy by Design

| Requirement | Evidence |
|---|---|
| Threat model summary | `docs/risk_register.md` — covers data, security, operational, and decision risks with impacts and mitigations |
| Strong authentication/session practices | Django built-in auth with password validators, session middleware, login/logout redirects |
| Role/permission policy checks | `core/permissions.py` — `role_required` decorator enforces access per view; blocked attempts logged with SECURITY action_type |
| Sensitive-field handling | `counselor_notes` redacted for unauthorized roles (Teacher sees `[REDACTED — UNAUTHORIZED ROLE]`); tested in `test_teacher_sees_redacted_counselor_notes` |
| Auditability | `AuditLog` model records user, role, action_type, action_result, case, affected_object_id, description, and timestamp for every key action |
| Unauthorized action blocking | Tested in `test_teacher_views_are_restricted`, `test_counselor_views_are_restricted`, `test_role_boundary_enforcement_on_transitions` |

---

## Track D — Observability and Reliability

| Requirement | Evidence |
|---|---|
| Structured logs | `core/middleware.py` — `RequestLoggingMiddleware` logs method, path, status code, user, role, and duration with correlation IDs for every request |
| Health and error indicators | `/health/` endpoint returns JSON with status (`healthy`/`unhealthy`), database connectivity, and record counts |
| Dashboard metrics | 4 system evaluation KPIs: workflow completion rate, data validation pass rate, alert resolution rate, security incident count |
| Failure injection evidence | `test_malformed_csv_failure_injection` — 4 rows with validation errors, all correctly rejected; `test_csv_missing_header_rejection` — missing columns raise error |
| Safe recovery behavior | Invalid state transitions raise `ValidationError` and log to AuditLog; CSV errors return user-facing messages without crashing |
| Correlation IDs | All log entries include a request correlation ID for traceability across requests |

---

## Track A — Architecture and Performance (Bonus)

| Requirement | Evidence |
|---|---|
| Modular design | Service-layer pattern in `core/data_ingestion.py`, separated from views; middleware in `core/middleware.py`; permissions in `core/permissions.py` |
| ORM optimization | `select_related` / `prefetch_related` available for query optimization; unique_together constraint on Attendance prevents duplicates |
