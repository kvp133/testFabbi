# PR #7 — `bugfix/users-email-uniqueness`

**Branch:** `bugfix/users-email-uniqueness` (off `main`)
**Layer:** Database · **Severity:** 🔴 Critical / 🟡 Medium · **Issue ids:** D1, D6

Two related identity bugs shipped together because shipping one without
the other immediately undoes it (a case-sensitive UNIQUE constraint
still allows `demo@x` and `DEMO@x` to coexist).

---

## Issue 7.1 — `users.email` has no uniqueness constraint

- **Location**
  - Model: `backend/app/models/user.py:21-24`
    `email = mapped_column(String(255), nullable=False)` — no `unique=True`,
    no `index=True`.
  - Initial migration: `backend/alembic/versions/001_initial.py:26`
    `sa.Column("email", sa.String(255), nullable=False)` — no constraint
    emitted.

- **Reason**
  Two users can register with the same email. `get_user_by_email` calls
  `scalar_one_or_none()` on what may be an ambiguous result set; depending
  on row order Postgres returns whichever it finds first, so login becomes
  non-deterministic. Even without an attacker this corrupts the "email
  identifies a user" invariant that the rest of the auth flow depends on.

---

## Issue 7.2 — Email comparison is case-sensitive

- **Location**
  `backend/app/services/auth_service.py:11-13` (`get_user_by_email`)
  and `:21-30` (`create_user`). Both pass `user_data.email` through
  unchanged.

- **Reason**
  `demo@test.com` and `DEMO@test.com` are treated as distinct accounts at
  every layer. The local-part of an email is by SMTP convention
  case-insensitive in practice; users typing their email with the Shift
  key held will create accidental duplicate accounts and lose their data.

---

## Fix proposal — defence in depth at three layers

### 1. Model

```python
# backend/app/models/user.py
email: Mapped[str] = mapped_column(
    String(255),
    nullable=False,
    unique=True,
    index=True,
)
```

### 2. Service — normalize at every entry point

```python
# backend/app/services/auth_service.py
def _normalize_email(email: str) -> str:
    return email.strip().lower()

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == _normalize_email(email))
    )
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
    user = User(
        email=_normalize_email(user_data.email),
        hashed_password=get_password_hash(user_data.password),
    )
    db.add(user)
    ...
```

### 3. Migration `b1a2c3d4e5f6`

The migration must run on existing data, so it has three phases:

```python
def upgrade() -> None:
    bind = op.get_bind()

    # Phase 1: lowercase existing rows so the UNIQUE index is reachable
    op.execute("UPDATE users SET email = LOWER(email) WHERE email <> LOWER(email)")

    # Phase 2: refuse to proceed if normalisation surfaced duplicates —
    # admin must merge manually. Silently dropping rows is worse than
    # failing loudly.
    duplicate = bind.execute(sa.text(
        "SELECT email, COUNT(*) AS c FROM users "
        "GROUP BY email HAVING COUNT(*) > 1 LIMIT 1"
    )).fetchone()
    if duplicate is not None:
        raise RuntimeError(
            f"Cannot add UNIQUE constraint on users.email: duplicate "
            f"{duplicate[0]!r} ({duplicate[1]} rows). Resolve manually."
        )

    # Phase 3: add the constraint
    op.create_index("ix_users_email", "users", ["email"], unique=True)
```

### 4. Endpoint — race condition

The register endpoint additionally wraps `create_user` in
`try/except IntegrityError` to translate the race-condition path (two
parallel inserts of the same email between SELECT and INSERT) into a
clean 400 instead of a 500:

```python
try:
    user = await create_user(db, user_data)
except IntegrityError:
    await db.rollback()
    raise HTTPException(status_code=400, detail="Email already registered")
```

---

## Tests

`tests/test_auth.py` gains three regression tests:

- `test_duplicate_email_register_rejected` — second register with the
  same email → 400.
- `test_duplicate_email_case_insensitive` — `demo@x` then `DEMO@X` → 400.
- `test_login_normalizes_email_case` — register lowercase, login
  mixed-case → 200.

## Verification

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend pytest tests/test_auth.py -v
```

Confirmed on the live Postgres instance after migration:

```
\d users
Indexes:
  "users_pkey" PRIMARY KEY, btree (id)
  "ix_users_email" UNIQUE, btree (email)
```

All 7 tests pass on this branch.
