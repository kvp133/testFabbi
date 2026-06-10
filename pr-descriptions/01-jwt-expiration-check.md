# PR #1 — `bugfix/jwt-expiration-check`

**Branch:** `bugfix/jwt-expiration-check` (off `main`)
**Layer:** Auth · **Severity:** 🔴 Critical · **Issue id:** S1

---

## Issue 1.1 — JWT expiration check disabled

- **Location**
  `backend/app/core/security.py:49-60`, function `verify_token()`.
  The offending call is on line 56: `options={"verify_exp": False}`.

- **Reason**
  Passing `verify_exp: False` to `python-jose` silently disables the entire
  expiration check. The settings `ACCESS_TOKEN_EXPIRE_MINUTES=30` and
  `REFRESH_TOKEN_EXPIRE_DAYS=7` therefore have no runtime effect — any
  issued token remains valid until the JWT secret is rotated. This defeats
  the whole purpose of short-lived tokens: a leaked or stolen token cannot
  be aged out, only forcibly invalidated by a global secret change (which
  would log out every legitimate user simultaneously).

- **Fix proposal**
  Remove the `options` argument so python-jose applies its default
  (verify `exp`, raise `ExpiredSignatureError` → caught as `JWTError` →
  returns `None`, which the dependency layer maps to HTTP 401).

  ```python
  # backend/app/core/security.py
  def verify_token(token: str) -> dict[str, Any] | None:
      """Verify and decode a JWT token. Returns None if invalid or expired."""
      try:
          payload = jwt.decode(
              token,
              settings.JWT_SECRET,
              algorithms=[settings.JWT_ALGORITHM],
          )
          return payload
      except JWTError:
          return None
  ```

---

## Tests

- `tests/test_auth.py::test_expired_access_token_is_rejected`
  Forges an access token with `expires_delta=timedelta(seconds=-60)` (i.e.
  already expired) and asserts `/auth/me` returns 401.

## Verification

```bash
docker compose exec backend pytest tests/test_auth.py -v
```

All five tests pass on this branch (4 existing + 1 new regression).

## Risk and rollout note

Active sessions older than `ACCESS_TOKEN_EXPIRE_MINUTES` will start failing
immediately after deploy. This is the intended behaviour — they should
never have worked in the first place — but it is worth surfacing in the
release notes so users understand a forced re-login.
