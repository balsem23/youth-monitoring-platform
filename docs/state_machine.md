# Workflow State Machine

## Case States

1. New
2. In Review
3. Intervention Planned
4. Follow-up
5. Closed

## Transitions

| From | To | Allowed Role | Condition |
|---|---|---|---|
| New | In Review | Teacher, Counselor, Admin | Case data is valid |
| In Review | Intervention Planned | Counselor, Admin | Risk alert exists |
| Intervention Planned | Follow-up | Counselor, Admin | Plan is created |
| Follow-up | Closed | Counselor, Admin | Follow-up is completed |

## Blocked Transitions

- Teacher cannot close a case.
- Teacher cannot create intervention plans.
- Counselor cannot manage system settings.
- Invalid case data must stay blocked until corrected.