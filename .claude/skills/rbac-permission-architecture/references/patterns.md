# RBAC Patterns Reference

Use this file for concrete modeling patterns and implementation shapes.

## Route Permission vs Action Permission

Use separate checks for page entry and in-page controls.

Example mapping:

```txt
Route:
/admin/users      -> users.list
/admin/users/[id] -> users.read.basic

Actions inside `/admin/users`:
Create user       -> users.create
Update status     -> users.update.status
Delete user       -> users.delete

Actions inside `/admin/users/[id]`:
Read sensitive    -> users.read.sensitive
Edit profile      -> users.update.profile
Assign role       -> users.update.role
```

Interpretation:

- a user may reach `/admin/users` and still lack `users.create`
- a user may reach `/admin/users/[id]` and still lack `users.read.sensitive`

## Permission-Driven UI Layers

Apply three distinct checks.

```ts
const canSeeUsersMenu = hasPermission("users.list");
const canAccessUsersPage = hasPermission("users.list");
const canCreateUser = hasPermission("users.create");
const canChangeStatus = hasPermission("users.update.status");
const canDeleteUser = hasPermission("users.delete");
```

Pattern:

- menu visibility controls discovery
- route guards control page entry
- component guards control each action

## `Update Without Read` Minimum-Action UI

Use a narrow interaction when the caller can mutate one field but cannot open the full record.

Allowed pattern:

```txt
Permissions:
users.list
users.update.status

UI:
- render user list
- deny detail page
- show row-level "Update Status" button
- open modal with only `status`
```

Allowed implementation shapes:

- row action + modal
- row action + drawer
- inline editor in table
- dedicated action endpoint for one business action

Forbidden pattern:

```txt
Permissions:
users.list
users.update.status

UI:
- render full user detail page
- show all profile fields in read-only mode
- allow status edit in the same screen
```

This leaks detail context that the permission model did not grant.

## Read-Split Pattern

Use data classes to decide whether to split reads.

Example:

```txt
users.read.basic
users.read.detail
users.read.sensitive
```

Typical screen design:

- list page requires `users.list`
- summary card requires `users.read.basic`
- audit tab requires `users.read.detail`
- compensation or identity tab requires `users.read.sensitive`

## Update-Split Pattern

Use field groups or business capability, not raw CRUD vocabulary.

Preferred:

```txt
users.update.profile
users.update.status
users.update.role
users.update.permissions
users.reset_password
```

Avoid:

```txt
users.update
```

Use a dedicated business action when the workflow is not a generic edit:

```txt
orders.approve
orders.reject
payments.refund
tickets.assign
```

## Endpoint Mapping Pattern

Match endpoint shape to permission shape.

Preferred:

```txt
GET    /users              -> users.list
GET    /users/:id          -> users.read.basic
PATCH  /users/:id/profile  -> users.update.profile
PATCH  /users/:id/status   -> users.update.status
PATCH  /users/:id/role     -> users.update.role
POST   /users/:id/reset-password -> users.reset_password
```

Avoid:

```txt
PATCH /users/:id
```

Why:

- field-level checks are harder
- permission boundaries become opaque
- auditing and tests become less precise

## Field Authorization Pattern

Express allowed fields in one central policy map.

```ts
const allowedFieldsByPermission = {
  "users.update.profile": ["firstName", "lastName", "phone"],
  "users.update.status": ["status"],
  "users.update.role": ["roleId"],
};
```

Preferred backend behavior:

1. compute caller permissions
2. derive allowed field set
3. reject payloads containing disallowed fields
4. update only through a permission-specific service or handler

## Role-As-Bundle Pattern

Keep business policy in permissions, not in role names.

Example:

```txt
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

The role label explains the audience; the permission list explains authority.

## Allowed vs Forbidden Summary

Allowed:

- `hasPermission("users.update.status")`
- page guard for `/admin/users`
- backend `403` for forbidden endpoint access
- modal-only status editing without detail-page access
- explicit `users.read.sensitive`

Forbidden:

- `if (user.role === "admin")`
- assuming page access implies create or delete access
- generic `users.update` for unrelated mutations
- generic `PATCH /users/:id` for all field updates
- exposing sensitive tabs under broad detail access
