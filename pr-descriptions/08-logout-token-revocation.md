# PR #8 — `bugfix/logout-token-revocation`

**Branch:** `bugfix/logout-token-revocation` (off `main`)
**Layer:** Auth · **Severity:** 🔴 Critical · **Issue id:** S3

---

## Issue 8.1 — Logout does not actually log the user out

- **Location**
  `backend/app/api/v1/auth.py:102-107`, function `logout()`.
  ```python
  @router.post("/logout")
  async def logout(current_user: User = Depends(get_current_user)):
      return {"message": "Successfully logged out"}
  ```

- **Reason**
  The endpoint returns 200 with a friendly message but performs no
  side effect. The access and refresh tokens issued at login remain
  valid until their natural expiry (30 minutes and 7 days
  respectively). For a user clicking "Log out" on a shared device, the
  session was not in fact terminated — anyone with access to the same
  `localStorage` can resume the session, and the long refresh-token
  lifetime makes the problem worse.

  This breaks the contract every authenticated UI implicitly makes
  with the user: that "log out" means "this credential is now dead."

- **Fix proposal — JTI blocklist in Redis**

  1. Embed a `jti` (JWT ID) claim in every access token. Refresh
     tokens already had one. Both are now individually addressable.

     ```python
     # backend/app/core/security.py
     to_encode.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
     ```

  2. Define the blocklist key shape:

     ```python
     def revoked_token_key(jti: str) -> str:
         return f"revoked:jti:{jti}"
     ```

  3. `get_current_user` consults the blocklist after signature
     verification, before the DB lookup:

     ```python
     jti = payload.get("jti")
     if jti and await redis.exists(revoked_token_key(jti)):
         raise HTTPException(401, detail="Token has been revoked")
     ```

  4. `/auth/logout` accepts the access token in the `Authorization`
     header (so it is also revoked) and an optional `refresh_token` in
     the body. Each token is added to the blocklist with TTL equal to
     its remaining lifetime — so entries self-clean and Redis does
     not grow unbounded:

     ```python
     async def _revoke_token(redis: RedisClient, token: str) -> None:
         payload = verify_token(token)
         if payload is None:
             return
         jti = payload.get("jti")
         exp = payload.get("exp")
         if not jti or not exp:
             return
         remaining = int(exp - time.time())
         if remaining > 0:
             await redis.set(revoked_token_key(jti), "1", ex=remaining)
     ```

  5. `/auth/refresh` also consults the blocklist so a refresh token
     revoked by an earlier logout cannot be used to mint fresh credentials.

  Old tokens issued before this lands carry no `jti` and remain valid
  for backward compatibility — they simply cannot be revoked. New
  tokens issued after deploy inherit the new behaviour.

---

## Tests

- `test_access_token_revoked_after_logout` — `/auth/me` returns 200
  before logout and 401 ("revoked") with the same token after logout.
- `test_refresh_token_revoked_after_logout` — `/auth/logout` with a
  `refresh_token` body, then `/auth/refresh` with that token, returns
  401 ("revoked").

The mocked Redis in `conftest.py` is replaced with an in-memory
`_FakeRedis` that preserves state across requests, so the revocation
flow is exercised end-to-end. The store is cleared between tests by
the existing `setup_db` autouse fixture.

## Verification

```bash
docker compose exec backend pytest tests/test_auth.py -v
```

All six auth tests pass on this branch (4 existing + 2 new). The full
test suite (11 tests across `test_auth.py` and `test_todos.py`) also
passes.

## Dependency on other fixes

This fix is technically independent and ships off `main`. Pairing it
with [PR #2](./01-jwt-expiration-check.md) (`verify_exp`) and
[PR #3](./02-jwt-token-type-validation.md) (token type) gives a full
session-hygiene story; without those, expired tokens are still
honoured and refresh tokens still work everywhere, so revoking one
specific token only closes one hole at a time.
