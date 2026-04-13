# RBAC Rules Reference

Use this file when the task needs the full policy set behind the RBAC skill.

## Core Model

- Model permissions as the unit of authorization.
- Model roles as named bundles of permissions.
- Keep UI visibility, page access, and backend authorization as separate decisions.
- Treat the frontend as UX control, not as the security authority.
- Enforce the final authorization decision in backend code and endpoint handlers.

## Permission Naming

Use lowercase, dot-separated names.

Preferred shape:

```txt
resource.action.scope
```

The scope segment is optional when the action is already precise enough.

Good examples:

```txt
users.list
users.read.basic
users.read.detail
users.read.sensitive
users.create
users.update.profile
users.update.status
users.update.role
users.delete
users.reset_password
orders.approve
payments.refund
```

Avoid:

```txt
userAccess
canEditUser
manageUsers
users.update
allAccess
```

Naming rules:

- Use names that describe one clear business capability.
- Avoid vague buckets such as `manage`, `full`, or `allAccess`.
- Do not let one permission stand in for multiple unrelated actions.

## Split Read Access By Data Class

Do not model all reads with one broad permission if the data has different sensitivity levels.

Recommended baseline:

```txt
users.read.basic
users.read.detail
users.read.sensitive
```

Typical meaning:

- `users.read.basic`: name, email, status, created-at style fields
- `users.read.detail`: team, notes, audit context, last-login style fields
- `users.read.sensitive`: salary, identity data, financial data, private contact data

Rule:

- Never merge sensitive fields into `basic` or `detail`.

## Split Update Access By Field Group Or Capability

Do not keep a generic update permission when the business risk differs by field.

Preferred examples:

```txt
users.update.profile
users.update.status
users.update.role
users.update.permissions
```

Keep business actions separate from generic update actions:

```txt
users.reset_password
orders.approve
orders.reject
payments.refund
tickets.assign
invoices.cancel
```

Rule:

- If the action has its own business meaning, model it as its own permission.

## Separate Route Access From Action Access

Do not grant every in-page action just because the user can open the page.

Examples:

```txt
/admin/users      -> users.list
/admin/users/[id] -> users.read.basic
/admin/roles      -> roles.list
/admin/settings   -> settings.read
```

In-page actions still need their own checks:

```txt
Create user           -> users.create
Open detail drawer    -> users.read.basic
Open sensitive tab    -> users.read.sensitive
Edit profile          -> users.update.profile
Change status         -> users.update.status
Assign role           -> users.update.role
Delete user           -> users.delete
```

## Handle `Update Without Read` Safely

Default rule:

- Do not render a full detail page when the user lacks the read permission required for that page.

Preferred handling:

1. Identify the minimum context required for the mutation.
2. Add the smallest read permission that genuinely supports that mutation, if needed.
3. Otherwise keep the user on a list or summary screen.
4. Expose a narrow modal, drawer, inline editor, or business-action control containing only the editable field set.

Example:

```txt
users.list
users.update.status
```

Without `users.read.detail`, the correct behavior is:

- allow the list page
- deny the detail page
- show a row-level "Update Status" action
- open a modal that only edits `status`

If the action is really a business action, rename it accordingly:

```txt
users.activate
orders.approve
orders.reject
tickets.assign
```

## UI Control Layers

Apply permission checks at three layers:

### Navigation

Control whether the module appears in menus.

```ts
const canSeeUsersMenu = hasPermission("users.list");
```

### Route

Prevent route rendering when the user lacks page access.

```ts
const canAccessUsersPage = hasPermission("users.list");
```

Return a `403` or an equivalent access-denied screen when blocked.

### Component / Action

Gate each action independently even after the page has loaded.

```ts
const canCreateUser = hasPermission("users.create");
const canReadSensitive = hasPermission("users.read.sensitive");
const canChangeStatus = hasPermission("users.update.status");
const canDeleteUser = hasPermission("users.delete");
```

## Backend Authority

Backend code remains the single source of truth.

Rules:

- Check permissions on every endpoint.
- Apply field-level authorization on every partial update path.
- Reject unauthorized payload fields by default.
- Return `403 Forbidden` for unauthorized requests.

Prefer endpoint design that matches permission granularity:

```txt
GET    /users              -> users.list
GET    /users/:id          -> users.read.basic
POST   /users              -> users.create
PATCH  /users/:id/profile  -> users.update.profile
PATCH  /users/:id/status   -> users.update.status
PATCH  /users/:id/role     -> users.update.role
DELETE /users/:id          -> users.delete
```

Avoid broad endpoints such as:

```txt
PATCH /users/:id
```

That pattern makes permission checks and field-level authorization harder to audit.

## Field-Level Authorization

Map allowed fields to explicit permissions.

Example:

```ts
const allowedFieldsByPermission = {
  "users.update.profile": ["firstName", "lastName", "phone"],
  "users.update.status": ["status"],
  "users.update.role": ["roleId"],
};
```

Default policy:

- reject the request if it contains fields outside the caller's allowed set

## Permission Dependencies

Prefer explicit assignment over hidden dependency logic.

Example:

```txt
users.update.profile
users.read.basic
```

This is easier to debug than an implicit rule that silently grants one from the other.

If the system does support dependencies:

- document them centrally
- keep them explicit and discoverable

## Recommended Baseline Layers

For CRUD-heavy admin systems, start with:

```txt
users.list
orders.list
reports.list
users.read.basic
users.read.detail
users.read.sensitive
users.create
orders.create
roles.create
users.update.profile
users.update.status
users.update.role
users.update.permissions
orders.approve
orders.cancel
payments.refund
users.reset_password
users.delete
users.archive
orders.delete
```

Rule:

- do not merge `delete` and `archive`

## Frontend Implementation Standard

Prefer centralized helpers such as:

- `hasPermission(permission)`
- `hasAllPermissions([...])`
- `hasAnyPermission([...])`
- `Can`
- route or page guards

Avoid scattered role checks:

```ts
if (user.role === "admin") {
  // forbidden pattern
}
```

Prefer:

```ts
if (hasPermission("users.update.status")) {
  // allowed pattern
}
```

## Role Design

Design roles as permission sets.

Example:

```txt
Admin:
users.list
users.read.basic
users.read.detail
users.read.sensitive
users.create
users.update.profile
users.update.status
users.update.role
users.delete

Support:
users.list
users.read.basic
users.update.status
users.reset_password

Auditor:
users.list
users.read.basic
users.read.detail
```

## Anti-Patterns

Do not:

- collapse everything into `users.read`, `users.update`, or `users.manage`
- treat hidden buttons as authorization
- use route access as a substitute for action access
- expose sensitive fields on a broad detail screen
- hide business actions inside a generic CRUD permission
- scatter authorization rules across ad hoc component logic

## Acceptance Checklist

The design is aligned with this skill when all of these are true:

- permission names follow a resource/action/scope convention
- route access and action access are separated
- read permissions are split where data sensitivity differs
- update permissions are split where business risk differs
- business actions have their own permission names
- frontend performs UX gating only
- backend performs the final authorization check
- field-level authorization exists for partial updates
- `update-without-read` cases use minimum-action UI
- sensitive data is guarded by distinct permissions
