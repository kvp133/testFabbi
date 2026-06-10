# PR #5 — `bugfix/frontend-cache-isolation`

**Branch:** `bugfix/frontend-cache-isolation` (off `main`)
**Layer:** Frontend · **Severity:** 🔴 Critical · **Issue ids:** F1, F2

Two closely related client-side cache leaks.

---

## Issue 5.1 — React Query key not parameterised by page / size / user

- **Location**
  `frontend/src/features/todos/api/todos.ts:35-45`, hook `useTodos()`.
  The key is the constant array `["todos"]`.

- **Reason**
  React Query keys identity-match by deep equality. Using a constant key
  means every paginated request is treated as the same cache entry:
  - Page 2 displays page 1 data.
  - Every mutation invalidates every page indiscriminately.
  - The same cache entry survives across login sessions on the same tab,
    so user A's list briefly renders for user B after re-login.

---

## Issue 5.2 — React Query cache not cleared on logout

- **Location**
  - `frontend/src/features/auth/api/auth.ts:46-56` — `useLogout()`.
  - `frontend/src/features/auth/hooks/useAuth.ts:23-35` — `logout()`.

  Both touch only `localStorage`. The React Query cache is left intact.

- **Reason**
  After logout, the cached entries under `["currentUser"]` and `["todos"]`
  persist. If a different user logs in on the same tab, the dashboard
  initially renders from the cached state of the previous user — their
  email in the header, their todos in the list — until the new fetches
  resolve. Worst case: the new user briefly believes the app is showing
  them someone else's data, even though the backend is doing the right
  thing.

---

## Fix proposal (shared)

1. Introduce a `todoKeys` factory so the parameter set is the cache key:

   ```ts
   // frontend/src/features/todos/api/todos.ts
   export const todoKeys = {
     all: ["todos"] as const,
     lists: () => [...todoKeys.all, "list"] as const,
     list: (params: { page: number; size: number }) =>
       [...todoKeys.lists(), params] as const,
   };
   ```

   `useTodos` uses the parameterised key; mutations invalidate via
   `todoKeys.all` so the whole todos subtree is refreshed.

2. `useUpdateTodo.onMutate` snapshots *every* cached list page via
   `getQueriesData({ queryKey: todoKeys.lists() })`, then patches each one
   in place. The previous code patched only the constant key.

3. Centralise client-side session cleanup:

   ```ts
   // frontend/src/features/auth/api/auth.ts
   function clearUserSession() {
     localStorage.removeItem("access_token");
     localStorage.removeItem("refresh_token");
     queryClient.clear();
   }

   export function useLogout() {
     return useMutation({
       mutationFn: async () => { await api.post("/auth/logout"); },
       onSettled: () => { clearUserSession(); },
     });
   }
   ```

   `onSettled` runs whether the API call succeeds or fails — the
   server-side `/auth/logout` is best-effort (the JWT remains valid until
   expiry anyway), but the client-side session must be wiped either way.

4. `useAuth.logout` now only navigates after the mutation settles, since
   the session cleanup is handled by the mutation hook itself.

---

## Tests

The project ships no frontend test runner. The change was verified with
`npx tsc -b` (no type errors).

### Manual repro of the original bug

1. With the old code: log in as user A, navigate the dashboard so todos
   are fetched into the cache, log out.
2. Log in as user B in the same tab. User A's email shows in the header
   for ~200 ms while React Query refetches; user A's todos may briefly
   render in the list.
3. With the fix: the page renders from an empty cache, only user B's
   data is ever displayed.

## Verification

```bash
cd frontend && npx tsc -b
```

No type errors.
