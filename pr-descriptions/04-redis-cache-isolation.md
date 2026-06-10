# PR #4 — `bugfix/redis-cache-isolation`

**Branch:** `bugfix/redis-cache-isolation` (off `main`)
**Layer:** Cache · **Severity:** 🔴 Critical / 🟠 High · **Issue ids:** C1, C2, C3

Three closely related caching bugs that share one root cause (badly chosen
cache key + missing invalidation) and one fix.

---

## Issue 4.1 — Global cache key leaks data across users

- **Location**
  `backend/app/api/v1/todos.py:37`, function `list_todos()`.
  The cache key is the constant string `"todos:list"`.

- **Reason**
  This single key is shared by every user. The first request to populate
  the cache will have its response served to every subsequent caller for
  the next 5 minutes (`CACHE_TTL = 300`), regardless of which user is
  logged in. The cache short-circuits the DB query, so the per-user
  `user_id` filter in `get_todos()` and the JWT / ownership middleware do
  not protect against it. This is a critical data-isolation breach: a
  user can be served someone else's todos verbatim.

---

## Issue 4.2 — Cache key ignores `page` and `size`

- **Location**
  Same line. The key does not include the pagination parameters.

- **Reason**
  Page 2 and page 1 share the same key, so `?page=2` returns page 1 data.
  Same problem for any different `size` value. Pagination is silently
  broken once anything is cached.

---

## Issue 4.3 — Cache never invalidated on writes

- **Location**
  `backend/app/api/v1/todos.py`:
  `create_new_todo` (line 77), `update_existing_todo` (line 105),
  `delete_existing_todo` (line 137). None of them touch Redis.

- **Reason**
  After creating a todo, the list query continues to return the stale
  cached page for up to 5 minutes. After deleting, the deleted todo
  continues to appear. After updating, the old title/`completed` flag
  still shows. Users perceive the app as broken — they take an action,
  refresh, and see no effect.

---

## Fix proposal (shared)

1. Replace the constant key with a per-user, per-page key:

   ```python
   def todos_list_cache_key(user_id: uuid.UUID, page: int, size: int) -> str:
       return f"user:{user_id}:todos:list:p{page}:s{size}"

   def todos_user_cache_pattern(user_id: uuid.UUID) -> str:
       return f"user:{user_id}:todos:list:*"
   ```

2. Add `RedisClient.delete_pattern(pattern)` that uses `SCAN` (not `KEYS`)
   so invalidation does not block Redis on large keysets:

   ```python
   # backend/app/core/redis.py
   async def delete_pattern(self, pattern: str) -> int:
       deleted = 0
       async for key in self._redis.scan_iter(match=pattern):
           await self._redis.delete(key)
           deleted += 1
       return deleted
   ```

3. Call `invalidate_user_todos_cache(redis, current_user.id)` on every
   write path (`POST /todos`, `PUT /todos/{id}`, `DELETE /todos/{id}`).

4. Add a `delete_pattern` `AsyncMock` to the test conftest so the new
   write paths don't fail under unit test (the mock returns `0`).

---

## Tests

`tests/test_cache.py` adds three unit tests on the cache-key helpers
(no live Redis required):

- `test_cache_key_is_scoped_per_user` — different users → different keys.
- `test_cache_key_is_scoped_per_page` — different pages/sizes → different keys.
- `test_invalidation_pattern_matches_only_owners_keys` — the glob
  contains the owner's id and excludes other users.

Integration tests (cache hit / invalidation against a real Redis) would
require either a fakeredis dep or running the suite with the real Redis
container, both of which are out of scope here.

## Verification

```bash
docker compose exec backend pytest tests/ -v
```

All 14 tests pass on this branch.
