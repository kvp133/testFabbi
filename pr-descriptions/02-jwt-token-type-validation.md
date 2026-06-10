# PR #2 — `bugfix/jwt-token-type-validation`

**Branch:** `bugfix/jwt-token-type-validation` (off `main`)
**Layer:** Auth · **Severity:** 🔴 Critical · **Issue id:** S2

---

## Issue 2.1 — Refresh tokens accepted at protected endpoints

- **Location**
  `backend/app/api/deps.py:16-51`, function `get_current_user()`.
  Between lines 23-29 the payload is validated for signature and the
  presence of the `sub` claim; the `type` claim is never inspected.

- **Reason**
  `create_refresh_token()` and `create_access_token()` both embed a `type`
  claim (`"refresh"` vs `"access"`) and use different lifetimes (7 days vs
  30 minutes). Because `get_current_user` only checks the signature, a
  refresh token is accepted by every endpoint that depends on
  `get_current_user` — i.e. every protected endpoint.

  Refresh tokens are designed to be long-lived and sent only to
  `/auth/refresh`. Treating them as access tokens collapses the two-token
  model into a single one with the worst properties of both: a stolen
  refresh token now grants 14× the impersonation window of a stolen
  access token, and it is also the token that survives longer in storage
  (frontend stores it in `localStorage` next to the access token).

- **Fix proposal**
  After validating the payload, reject anything where
  `payload.get("type") != "access"` with HTTP 401. `/auth/refresh` already
  performs the inverse check (`!= "refresh"`), so the asymmetry is
  preserved at both edges.

  ```python
  # backend/app/api/deps.py
  if payload.get("type") != "access":
      raise HTTPException(
          status_code=status.HTTP_401_UNAUTHORIZED,
          detail="Invalid token type",
      )
  ```

---

## Tests

- `tests/test_auth.py::test_refresh_token_rejected_at_protected_endpoint`
  Registers a user, then calls `/auth/me` with the `refresh_token` returned
  from the registration response. Must return 401.

- `tests/test_auth.py::test_forged_refresh_token_rejected`
  Builds a fresh refresh token using `create_refresh_token()` (so the
  signature is valid) and calls `/auth/me`. Must return 401. This covers
  the case where signature verification succeeds but the type is wrong.

## Verification

```bash
docker compose exec backend pytest tests/test_auth.py -v
```

All six tests pass on this branch (4 existing + 2 new regression).
