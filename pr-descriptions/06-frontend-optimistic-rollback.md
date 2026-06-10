# PR #6 — `bugfix/frontend-optimistic-rollback`

**Branch:** `bugfix/frontend-optimistic-rollback` (off `main`)
**Layer:** Frontend · **Severity:** 🟠 High · **Issue ids:** F3, F4

Two unrelated client bugs bundled because they live in the same file
(`features/todos/api/todos.ts`) and ship together cleanly.

---

## Issue 6.1 — Default page size is 10 000

- **Location**
  `frontend/src/features/todos/api/todos.ts:35`, hook
  `useTodos(page = 1, size = 10000)`.

- **Reason**
  The dashboard requests up to 10 000 todos on every load. With the demo
  seed of 1 000 rows it is already a ~1 MB JSON payload; the `GUIDE.md`
  documents an optional 1 000 000-row seed, where this default would
  hang the browser. The backend already supports pagination — the client
  simply never asks for it.

---

## Issue 6.2 — Optimistic update never rolls back on error

- **Location**
  `frontend/src/features/todos/api/todos.ts:64-101`, hook
  `useUpdateTodo()`. `onMutate` writes optimistically and returns
  `{ previousTodos }` in context, but `onError` only calls `toast.error`
  and discards the snapshot.

- **Reason**
  A failed PUT leaves the wrong title / `completed` flag visible in the
  UI until the next refetch. Because the global `staleTime` is 5
  minutes, the user keeps seeing the stale optimistic write and
  reasonably concludes the operation succeeded. They may even act on
  that false state (e.g., archiving a todo they think is already
  completed, or repeating the action and silently corrupting more data).

---

## Fix proposal

1. Export a constant and use it as the default page size; include the
   pagination params in the query key so pages cache independently:

   ```ts
   export const DEFAULT_TODOS_PAGE_SIZE = 20;

   export function useTodos(
     page: number = 1,
     size: number = DEFAULT_TODOS_PAGE_SIZE,
   ) {
     return useQuery({
       queryKey: ["todos", { page, size }],
       queryFn: async () => (await api.get("/todos", { params: { page, size } })).data,
     });
   }
   ```

2. Snapshot all paginated list pages, return them in `context`, and
   restore them in `onError`:

   ```ts
   onMutate: async ({ id, data }) => {
     await queryClient.cancelQueries({ queryKey: ["todos"] });
     const previousLists = queryClient.getQueriesData<TodoListResponse>({
       queryKey: ["todos"],
     });
     previousLists.forEach(([key, list]) => {
       if (!list) return;
       queryClient.setQueryData<TodoListResponse>(key, {
         ...list,
         items: list.items.map((t) => (t.id === id ? { ...t, ...data } : t)),
       });
     });
     return { previousLists };
   },
   onError: (_err, _vars, context) => {
     context?.previousLists.forEach(([key, list]) => {
       if (list) queryClient.setQueryData(key, list);
     });
     toast.error("Failed to update todo");
   },
   ```

3. `TodoPage` now owns `page` state and renders Prev/Next buttons with a
   `Page X / Y` indicator. Total pages are `Math.ceil(total / size)`; the
   buttons disable at the boundaries.

---

## Tests

No frontend test runner; verified with `npx tsc -b` (no type errors).

### Manual repro of the rollback bug

Temporarily make the backend return 500 on PUT (e.g., `raise` inside the
handler), toggle a todo's checkbox in the UI. With the fix, the checkbox
reverts to its previous state after the error toast. Without the fix, the
checkbox stays toggled until the user navigates away or 5 minutes pass.

## Verification

```bash
cd frontend && npx tsc -b
```

No type errors.
