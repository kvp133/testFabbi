# Assessment Bug Report — Overview

Full-stack code review of the Fabbi Todo App. This document is the canonical
overview: it lists every issue identified across the backend, frontend,
database, caching, and infrastructure layers; ranks them by severity; and
points to the individual PR description for each fix that was actually
implemented.

The codebase was audited end-to-end. Out of **43 identified issues**,
**7 fixes were implemented** on dedicated branches per the assessment
requirement of "≥ 5 meaningful issues, ≥ 2 backend, ≥ 1 frontend." The
selection prioritises **correctness, security, and data isolation** over
cosmetic cleanup, as the assessment brief instructs.

> AI assistance disclosure: Claude Code (Opus 4.7) was used for codebase
> exploration, bug triage, and draft generation of fixes, tests, and PR
> descriptions. All findings and the final implementation choices were
> reviewed before commit. Full disclosure of what was used and how lives
> in [`CLAUDE.md`](../CLAUDE.md) at the repo root.

---

## Severity scale

| Marker         | Meaning                                                                       |
| -------------- | ----------------------------------------------------------------------------- |
| 🔴 **Critical** | Breaks security or data isolation; leaks or corrupts data across users        |
| 🟠 **High**     | Logic bug that produces wrong data, regression risk, or production-scale perf |
| 🟡 **Medium**   | Quality, UX, performance, or robustness issue                                 |
| 🟢 **Low**      | Convention or cosmetic                                                        |

---

## Bug catalogue

### 🔐 Security / Authentication (backend)

| ID  | Severity    | Issue                                                            | Location                                                                |
| --- | ----------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------- |
| S1  | 🔴 Critical | `verify_token` disables `verify_exp`; all JWTs effectively infinite | `app/core/security.py:56`                                              |
| S2  | 🔴 Critical | `get_current_user` does not check token `type` — refresh tokens accepted as access tokens | `app/api/deps.py:21-34`                                |
| S3  | 🔴 Critical | `/auth/logout` is a no-op — tokens remain valid until expiry, no JTI blocklist | `app/api/v1/auth.py:102-107`                                    |
| S4  | 🟠 High     | Email enumeration on `/login`: 404 vs 401 leaks whether the email exists | `app/api/v1/auth.py:54-66`                                          |
| S5  | 🟠 High     | Default `JWT_SECRET` hardcoded in source and `.env` committed to repo | `app/core/config.py:15`, `.env`, `.gitignore:9`                     |
| S6  | 🟠 High     | `CORS allow_origins=["*"]` combined with `allow_credentials=True` — invalid per spec, opens cross-origin attacks | `app/main.py:31`                  |
| S7  | 🟡 Medium   | No rate limit on `/login` or `/register` — brute force / abuse vector | `app/api/v1/auth.py`                                                |
| S8  | 🟡 Medium   | Refresh tokens are not rotated and have no blocklist — replayable | `app/api/v1/auth.py:77-99`                                            |
| S9  | 🟡 Medium   | `UserCreate` schema has no password complexity rules; FE enforces min 6 but BE accepts anything | `app/schemas/user.py:7-9`                          |
| S10 | 🟢 Low      | `authenticate_user` defined but unused; `/login` reimplements the same logic | `app/services/auth_service.py:33`, `app/api/v1/auth.py:60`     |

### 🔓 Authorization / Data isolation (backend)

| ID | Severity    | Issue                                                                      | Location                            |
| -- | ----------- | -------------------------------------------------------------------------- | ----------------------------------- |
| A1 | 🔴 Critical | `GET /todos/{id}` does not verify `todo.user_id == current_user.id` — IDOR | `app/api/v1/todos.py:88-102`        |
| A2 | 🔴 Critical | `PUT /todos/{id}` — same IDOR pattern, attacker can rewrite any todo       | `app/api/v1/todos.py:105-134`       |
| A3 | 🔴 Critical | `DELETE /todos/{id}` — same IDOR pattern, attacker can delete any todo     | `app/api/v1/todos.py:137-154`       |

### 🗄️ Database (schema / migrations / queries)

| ID | Severity    | Issue                                                                          | Location                                                                                       |
| -- | ----------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| D1 | 🔴 Critical | `users.email` lacks UNIQUE constraint and index — duplicate accounts possible  | `app/models/user.py:21-24`, `alembic/versions/001_initial.py:26`                               |
| D2 | 🟠 High     | `todos.user_id` has no index — every list query full-scans                     | `app/models/todo.py:35-38`                                                                     |
| D3 | 🟠 High     | FK `todos.user_id` lacks `ON DELETE CASCADE` — orphans or delete failures      | `app/models/todo.py:36`                                                                        |
| D4 | 🟠 High     | `get_todos` has no `ORDER BY` — OFFSET/LIMIT produces non-deterministic pages  | `app/services/todo_service.py:31`                                                              |
| D5 | 🟠 High     | N+1 query in `list_todos` — per-todo `SELECT users` lookup                     | `app/api/v1/todos.py:48-50`                                                                    |
| D6 | 🟡 Medium   | Email stored case-sensitively; `DEMO@test.com` ≠ `demo@test.com`               | `app/services/auth_service.py:11-12,21-30`                                                     |
| D7 | 🟡 Medium   | `DB_ECHO=True` is the default; production logs flooded with SQL                | `app/core/config.py:9`                                                                         |
| D8 | 🟡 Medium   | No upper bound on `?size=` — `?size=10000000` is accepted, DoS surface         | `app/api/v1/todos.py:29`                                                                       |

### ⚡ Caching (Redis)

| ID | Severity    | Issue                                                                                          | Location                              |
| -- | ----------- | ---------------------------------------------------------------------------------------------- | ------------------------------------- |
| C1 | 🔴 Critical | Cache key `"todos:list"` is global — one user's response is served to every other user         | `app/api/v1/todos.py:37`              |
| C2 | 🔴 Critical | Cache key ignores `page`/`size` — `?page=2` returns page 1                                     | `app/api/v1/todos.py:37`              |
| C3 | 🟠 High     | Cache never invalidated on create/update/delete — stale data for up to 5 minutes               | `app/api/v1/todos.py` (mutation paths) |

### 🧩 Backend API correctness

| ID | Severity   | Issue                                                                                                      | Location                              |
| -- | ---------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| B1 | 🟠 High    | `PUT /todos/{id}` uses `if todo_data.completed:` — only truthy values are applied, so `completed=False` is silently ignored | `app/api/v1/todos.py:123-124` |
| B2 | 🟠 High    | `TodoUpdate` apply logic is inconsistent (`is not None` vs `in update_data`) and calls `update_todo(db, todo, {})` with an empty dict | `app/api/v1/todos.py:121-132` |
| B3 | 🟡 Medium  | `/auth/register` returns tokens directly; no audit log; deviates from typical "register then login" UX     | `app/api/v1/auth.py:23-43`            |
| B4 | 🟡 Medium  | `PUT /todos/{id}` is treated as a partial update — should be `PATCH`                                       | `app/api/v1/todos.py:105`             |

### ⚛️ Frontend

| ID | Severity    | Issue                                                                                                                                | Location                                                                              |
| -- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| F1 | 🔴 Critical | React Query key `["todos"]` is not scoped by page/size/user — pagination collides, and after logout the cache leaks to the next user | `frontend/src/features/todos/api/todos.ts:37`                                         |
| F2 | 🔴 Critical | Logout does not clear the React Query cache — `["currentUser"]` and `["todos"]` survive across sessions                              | `frontend/src/features/auth/hooks/useAuth.ts:23-35`, `features/auth/api/auth.ts:46-56` |
| F3 | 🟠 High     | `useTodos(page=1, size=10000)` — default fetches up to 10 000 rows                                                                   | `frontend/src/features/todos/api/todos.ts:35`                                         |
| F4 | 🟠 High     | Optimistic update never rolls back — `onError` only toasts, the snapshot in `context` is discarded                                   | `frontend/src/features/todos/api/todos.ts:95-101`                                     |
| F5 | 🟠 High     | Refresh-token flow is not wired up — 401 jumps straight to `/login`, losing state                                                    | `frontend/src/lib/api.ts:27-37`                                                       |
| F6 | 🟡 Medium   | `TodoList` uses `key={index}` — checkbox toggle can "jump" when the list reorders                                                    | `frontend/src/features/todos/components/TodoList.tsx:42`                              |
| F7 | 🟡 Medium   | No confirmation before delete — single misclick destroys data                                                                        | `frontend/src/features/todos/components/TodoList.tsx:24-26`                           |
| F8 | 🟡 Medium   | `ProtectedRoute` only checks token presence in `localStorage` — expired tokens still admit, the 401 only fires after navigation      | `frontend/src/router/ProtectedRoute.tsx:9`                                            |
| F9 | 🟢 Low      | Register form sends `confirmPassword` to the backend (silently ignored by Pydantic)                                                  | `frontend/src/features/auth/schemas/auth.ts:11`                                       |

### 🏗️ Infrastructure / Test reliability

| ID | Severity  | Issue                                                                                                              | Location                                                  |
| -- | --------- | ------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| I1 | 🟠 High   | `depends_on` lacks `condition: service_healthy` — backend crashes on first boot if Postgres is slow to accept conn | `docker-compose.yml:31-33,43-44`                          |
| I2 | 🟠 High   | Tests run on SQLite while production uses Postgres — masks UUID, RETURNING, and isolation-level differences        | `tests/conftest.py:11-12`                                 |
| I3 | 🟠 High   | `conftest.py::auth_headers` issues a token for a UUID that does not exist in the DB — fixture unusable             | `tests/conftest.py:81-85`                                 |
| I4 | 🟠 High   | Test suite has zero cross-user authorization coverage                                                              | `tests/test_todos.py`                                     |
| I5 | 🟡 Medium | `.env` with `JWT_SECRET` committed to the repo; `.gitignore` deliberately comments out the `.env` line             | `.gitignore:9`, `.env`                                    |
| I6 | 🟡 Medium | Frontend image bakes `VITE_API_URL=http://localhost:8000` at build time — wrong for any non-localhost deploy       | `frontend/Dockerfile`, `docker-compose.yml:42`            |
| I7 | 🟡 Medium | Backend `CMD` runs `alembic upgrade head` inline — race condition across replicas                                  | `backend/Dockerfile:18`                                   |
| I8 | 🟢 Low    | Both `PyJWT` and `python-jose` are installed; code only uses jose — unused dependency surface                      | `backend/requirements.txt:43,47`                          |

### Severity totals

| Severity    | Count  |
| ----------- | ------ |
| 🔴 Critical | **10** |
| 🟠 High     | **17** |
| 🟡 Medium   | **13** |
| 🟢 Low      | **3**  |
| **Total**   | **43** |

---

## Fixes implemented

Eight fixes were shipped on dedicated branches. Each one is described in its
own file in this directory and lives on a branch named per the assessment
rule (`bugfix/...`). The selection covers three auth fixes, one authorization
fix, one cache fix, two frontend fixes, and one DB fix — closing every
🔴 Critical issue identified during the audit.

| #   | Branch                                | Layer         | Issues addressed | PR description                                        |
| --- | ------------------------------------- | ------------- | ---------------- | ----------------------------------------------------- |
| 1   | `bugfix/jwt-expiration-check`         | Auth          | S1               | [`01-jwt-expiration-check.md`](./01-jwt-expiration-check.md) |
| 2   | `bugfix/jwt-token-type-validation`    | Auth          | S2               | [`02-jwt-token-type-validation.md`](./02-jwt-token-type-validation.md) |
| 3   | `bugfix/todo-ownership-idor`          | Authorization | A1, A2, A3       | [`03-todo-ownership-idor.md`](./03-todo-ownership-idor.md) |
| 4   | `bugfix/redis-cache-isolation`        | Cache         | C1, C2, C3       | [`04-redis-cache-isolation.md`](./04-redis-cache-isolation.md) |
| 5   | `bugfix/frontend-cache-isolation`     | Frontend      | F1, F2           | [`05-frontend-cache-isolation.md`](./05-frontend-cache-isolation.md) |
| 6   | `bugfix/frontend-optimistic-rollback` | Frontend      | F3, F4           | [`06-frontend-optimistic-rollback.md`](./06-frontend-optimistic-rollback.md) |
| 7   | `bugfix/users-email-uniqueness`       | DB            | D1, D6           | [`07-users-email-uniqueness.md`](./07-users-email-uniqueness.md) |
| 8   | `bugfix/logout-token-revocation`      | Auth          | S3               | [`08-logout-token-revocation.md`](./08-logout-token-revocation.md) |

### Selection rationale

- **Auth (S1, S2, S3)** all ship. S1 (expiration) and S2 (token type) had
  to land first because without them even a properly revoked token would
  be ineffective — tokens never expire, and the access/refresh distinction
  is meaningless. S3 (logout revocation, shipped in PR #8) sits on top
  of that foundation and adds an explicit blocklist via Redis.
- **Authorization (A1+A2+A3)** are shipped as a single fix because they
  share one root cause — `get_todo_by_id` filters only by id. Splitting them
  would have produced three near-identical PRs.
- **Cache (C1+C2+C3)** are also shipped together: the global key and the
  missing invalidation are two sides of the same caching mistake, and
  fixing one without the other still leaves the door open.
- **Frontend (F1+F2, F3+F4)** are paired into two PRs by theme: one for
  cache scoping/clearing (cross-user data leak), one for write-path UX
  (optimistic rollback + page size).
- **DB (D1+D6)** are combined because they both concern email identity —
  the uniqueness constraint and the case-insensitive comparison have to
  ship in the same migration or one immediately undoes the other (a
  case-sensitive UNIQUE constraint would still allow `demo@x` and
  `DEMO@x` to coexist).

### Why other criticals were not shipped

| Skipped         | Why                                                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------------------------------------- |
| S5 (env secret) | Operational fix, not a code fix; better handled in a deploy checklist than a code PR.                                     |
| S6 (CORS)       | One-line config change; trivial to add in a follow-up.                                                                    |
| D3, D4, D5, D8  | Performance / schema hygiene; significant but lower priority than data isolation and authentication for an MVP review.    |

---

## Verification

Every fix branches off `main` independently (no chained branches), so any
subset can be merged in any order. To verify a fix in isolation:

```bash
git checkout bugfix/<name>
docker compose up --build -d backend          # rebuild so app code matches
docker compose exec backend pytest tests/ -v  # backend tests
# For frontend branches:
cd frontend && npx tsc -b
```

The DB fix branch (`bugfix/users-email-uniqueness`) also runs a new
Alembic migration: `docker compose exec backend alembic upgrade head`.

### Test results summary (per branch)

| Branch                                | Tests | Notes                                                       |
| ------------------------------------- | ----- | ----------------------------------------------------------- |
| `bugfix/jwt-expiration-check`         | 5 ✅  | +1 regression test for expired token                        |
| `bugfix/jwt-token-type-validation`    | 6 ✅  | +2 regression tests for refresh-token rejection             |
| `bugfix/todo-ownership-idor`          | 8 ✅  | +3 cross-user IDOR tests                                    |
| `bugfix/redis-cache-isolation`        | 14 ✅ | +3 cache-key unit tests; conftest gains `delete_pattern` mock |
| `bugfix/frontend-cache-isolation`     | tsc ✅ | No frontend test runner in the project                      |
| `bugfix/frontend-optimistic-rollback` | tsc ✅ | No frontend test runner in the project                      |
| `bugfix/users-email-uniqueness`       | 7 ✅  | +3 tests covering duplicate / case-insensitive / mixed-case login; new Alembic migration applied successfully to live Postgres |
| `bugfix/logout-token-revocation`      | 11 ✅ | +2 tests for access / refresh revocation; conftest gains an in-memory FakeRedis preserving state across requests |

---

## Known limitations

- The frontend has no test runner (no Vitest/Jest), so frontend changes are
  validated only by `tsc -b` and manual repro. Adding a runner would have
  expanded the change beyond bug fixing.
- The bcrypt/passlib stack emits a `error reading bcrypt version` warning
  on startup. This is a known passlib 1.7.4 + bcrypt 4.x compatibility
  issue and does not affect hashing or verification. Out of scope here.
- The running Docker stack must be rebuilt (`docker compose up --build -d
  backend`) for any backend code change to take effect — `depends_on` does
  not bind-mount source.
