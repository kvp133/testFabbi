# PR #3 — `bugfix/todo-ownership-idor`

**Branch:** `bugfix/todo-ownership-idor` (off `main`)
**Layer:** Authorization · **Severity:** 🔴 Critical · **Issue ids:** A1, A2, A3

Three closely related IDOR (Insecure Direct Object Reference) bugs that
share a single root cause and a single fix.

---

## Issue 3.1 — IDOR on `GET /todos/{id}`

- **Location**
  `backend/app/api/v1/todos.py:88-102`, function `get_todo()`.
  It calls `get_todo_by_id(db, todo_id)` and returns the row without
  checking `todo.user_id == current_user.id`.

- **Reason**
  Any authenticated user who learns another user's todo UUID can read it.
  UUIDs are not secrets and routinely leak via URLs, logs, browser history,
  error messages, or simple enumeration of public APIs (every list endpoint
  that returns todo ids becomes an oracle). This is the textbook IDOR
  pattern.

---

## Issue 3.2 — IDOR on `PUT /todos/{id}`

- **Location**
  `backend/app/api/v1/todos.py:105-134`, function `update_existing_todo()`.
  Same root cause as 3.1: `get_todo_by_id(db, todo_id)` returns any user's
  row, and the handler mutates `todo.title`, `todo.description`, and
  `todo.completed` without ownership verification.

- **Reason**
  An attacker can rewrite arbitrary users' todos. Possible abuse:
  defacement, phishing payloads in titles/descriptions visible in the
  owner's UI, or simply data corruption that the owner cannot trace.

---

## Issue 3.3 — IDOR on `DELETE /todos/{id}`

- **Location**
  `backend/app/api/v1/todos.py:137-154`, function `delete_existing_todo()`.
  Same pattern: ownership is never checked before `db.delete(todo)`.

- **Reason**
  An attacker can wipe any user's todos. Combined with 3.2, the attacker
  can both corrupt and destroy data they don't own.

---

## Fix proposal (shared)

Treat ownership as a property of the helper, not a per-handler
responsibility. This way the type system enforces correctness — a caller
that forgets the user no longer compiles.

1. Change the helper signature so `user_id` is required:

   ```python
   # backend/app/services/todo_service.py
   async def get_todo_by_id(
       db: AsyncSession, todo_id: uuid.UUID, user_id: uuid.UUID
   ) -> Todo | None:
       result = await db.execute(
           select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id)
       )
       return result.scalar_one_or_none()
   ```

2. Update all three call sites to pass `current_user.id`:

   ```python
   # backend/app/api/v1/todos.py — GET / PUT / DELETE
   todo = await get_todo_by_id(db, todo_id, current_user.id)
   ```

3. Return `None` for both "doesn't exist" and "exists but not yours" so the
   existing 404 path collapses both cases. Returning 403 instead would
   create an existence oracle — an attacker could enumerate todo UUIDs by
   distinguishing 403 from 404. 404 for everything you can't see is the
   standard safe answer.

---

## Tests

Three regression tests in `tests/test_todos.py` using two distinct users
(owner + attacker):

- `test_cannot_read_other_users_todo` — attacker GET → 404.
- `test_cannot_update_other_users_todo` — attacker PUT → 404, then verify
  the owner still sees the original title (proves no partial write).
- `test_cannot_delete_other_users_todo` — attacker DELETE → 404, then
  verify the owner can still GET the todo (proves no partial delete).

## Verification

```bash
docker compose exec backend pytest tests/test_todos.py -v
```

All eight tests pass on this branch (5 existing + 3 new IDOR coverage).
