---
name: rbac-permission-architecture
description: Design or update RBAC, permission-driven UI, and authorization flows with a permission-first model instead of role-only checks. Use this whenever work involves permission naming, route guards, backend/frontend auth alignment, field-level authorization, menu/page/action visibility, role-to-permission mapping, or tricky partial-access cases such as users who can update one field but cannot view the full detail screen.
---

# RBAC Permission Architecture

Use this skill to keep RBAC and permission-driven UI work consistent across frontend and backend.

## Follow This Workflow

1. Identify the resource and list the real business actions.
2. Model permissions in a permission-first format such as `resource.action.scope`.
3. Separate navigation access, route access, and in-page action access.
4. Design backend endpoints and authorization checks before trusting UI visibility.
5. Enforce field-level authorization for every partial update path.
6. When a user can mutate a narrow field without broad read access, design a minimum-action UI instead of rendering a full detail page.

## Apply These Defaults

- Treat roles as permission bundles, not as the primary authorization primitive.
- Split `read` permissions by data sensitivity when the screen exposes materially different data classes.
- Split `update` permissions by field group or business capability; do not hide business actions inside a generic update permission.
- Prefer explicit permission assignment over hidden permission dependencies.
- Reject unauthorized fields in update payloads by default.

## Guardrails

- Do not implement authorization with `if (user.role === "admin")`.
- Do not assume route access implies action access.
- Do not rely on hidden buttons as a security boundary.
- Do not expose full-detail screens for `update-without-read` scenarios.
- Do not collapse sensitive data into a broad `read` permission.

## Read The References When Needed

- Read [references/rbac-rules.md](./references/rbac-rules.md) for the canonical rules, naming conventions, backend authority, field-level authorization, and acceptance checklist.
- Read [references/patterns.md](./references/patterns.md) for route/action mapping patterns, minimum-action UI patterns, and concrete allowed vs forbidden examples.

## Output Expectations

When using this skill, produce authorization decisions that:

- name permissions explicitly and consistently
- separate route access from action access
- keep backend as the final authority
- handle partial access without leaking full UI or sensitive data
- remain easy to audit and extend as roles evolve
