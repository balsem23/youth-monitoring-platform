# Youth Monitoring Platform

Django project for the exam theme: **Tunisian Hope and Future for Children and Youth**.

A decision-support platform for tracking student wellbeing, risk alerts, workflow cases, and audit history. Targets early detection of education disengagement and missed health follow-up for Tunisian youth.

---

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Then open http://127.0.0.1:8000/

---

## Sample Accounts (created by `seed_data`)

| Username       | Password    | Role        |
|----------------|-------------|-------------|
| `admin_user`   | `Test1234!` | Admin       |
| `teacher_user` | `Test1234!` | Teacher     |
| `counselor_user`| `Test1234!`| Counselor   |

---

## Running Tests

```bash
python manage.py test
# or
pytest
```

---

## Datasets

| File | Description |
|------|-------------|
| `datasets/students_sample.csv` | 20 valid student records for CSV upload ingestion |
| `datasets/students_malformed.csv` | 10 rows with injection errors (empty names, wrong date format, out-of-range values) for failure-injection testing |

---

## Scenario Walkthroughs

### Scenario 1 — Education Early Warning

1. Log in as **admin_user**
2. Go to **Upload CSV** → upload `datasets/students_sample.csv`
3. Go to **Students** → verify student records appear
4. Go to **Admin Settings** → adjust risk thresholds (configurable by supervisor)
5. Log in as **teacher_user** → open a student → **Add Attendance** → mark 3 absences out of 4
6. The system auto-generates a HIGH-risk EDUCATION alert
7. Go to **Dashboard** → see updated KPIs (high-risk count, active alerts)
8. Click **Export Report** → download filtered CSV of all students
9. **Failure injection**: Upload `datasets/students_malformed.csv` → observe rejected rows with validation error messages → check Audit Logs for INGESTION failure log

### Scenario 2 — Health/Mental-Health Follow-up

1. Log in as **counselor_user**
2. Open a student → **Schedule Appointment** → mark as not attended, repeat 3 times
3. The system auto-creates a HEALTH alert after 3 missed appointments
4. **Create Intervention** with a recommendation reason
5. **Start Tracking Case** → transition through states: NEW → IN_REVIEW → INTERVENTION_PLANNED → FOLLOW_UP → CLOSED
6. View case timeline showing who acted, when, and what changed
7. **Failure injection**: Try skipping a state (e.g., NEW → CLOSED) → observe Blocked transition with SECURITY audit log
8. Log in as **teacher_user** → try accessing Admin Settings → observe redirect with BLOCKED security log entry

---

## Evidence

Screenshots of the running application are in the `screenshots/` directory (see `screenshots/README.md` for the full list).

---

## Project Structure

```
config/           — Django project configuration (settings, urls, wsgi)
core/             — Main application (models, views, templates, tests)
datasets/         — Sample CSV data files
docs/             — Documentation (problem statement, roles, state machine, risk register, ethics, advanced tracks)
screenshots/      — Evidence screenshots
```
