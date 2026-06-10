import { useState } from "react";
import { Plus, LogOut, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { DEFAULT_TODOS_PAGE_SIZE, useTodos } from "../api/todos";
import { TodoList } from "./TodoList";
import { TodoForm } from "./TodoForm";
import { useAuth } from "@/features/auth/hooks/useAuth";

export function TodoPage() {
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = DEFAULT_TODOS_PAGE_SIZE;
  const { data, isLoading, error } = useTodos(page, pageSize);
  const { user, logout } = useAuth();

  const totalPages = data ? Math.max(1, Math.ceil(data.total / pageSize)) : 1;
  const canPrev = page > 1;
  const canNext = page < totalPages;

  return (
    <div className="min-h-screen bg-muted/40">
      {/* Header */}
      <header className="bg-card border-b">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Todo App</h1>
            {user && (
              <p className="text-sm text-muted-foreground">{user.email}</p>
            )}
          </div>
          <Button variant="ghost" size="sm" onClick={logout}>
            <LogOut className="h-4 w-4 mr-2" />
            Logout
          </Button>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-3xl mx-auto px-4 py-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">My Todos</CardTitle>
            <Button size="sm" onClick={() => setShowCreateForm(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Add Todo
            </Button>
          </CardHeader>
          <Separator />
          <CardContent className="pt-4">
            {isLoading && (
              <div className="text-center py-12 text-muted-foreground">
                Loading todos...
              </div>
            )}

            {error && (
              <div className="text-center py-12 text-destructive">
                Failed to load todos. Please try again.
              </div>
            )}

            {data && <TodoList todos={data.items} />}

            {data && data.total > 0 && (
              <div className="mt-4 flex items-center justify-between text-sm text-muted-foreground">
                <span>
                  Showing {data.items.length} of {data.total} todos
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={!canPrev}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Prev
                  </Button>
                  <span>
                    Page {page} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => p + 1)}
                    disabled={!canNext}
                  >
                    Next
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      {/* Create Todo Dialog */}
      <TodoForm
        mode="create"
        open={showCreateForm}
        onClose={() => setShowCreateForm(false)}
      />
    </div>
  );
}
