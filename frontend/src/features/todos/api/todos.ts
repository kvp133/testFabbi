import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";

export interface Todo {
  id: string;
  title: string;
  description: string | null;
  completed: boolean;
  user_id: string;
  created_at: string;
  updated_at: string;
}

interface TodoListResponse {
  items: Todo[];
  total: number;
  page: number;
  size: number;
}

interface CreateTodoRequest {
  title: string;
  description?: string;
}

interface UpdateTodoRequest {
  title?: string;
  description?: string;
  completed?: boolean;
}


export const todoKeys = {
  all: ["todos"] as const,
  lists: () => [...todoKeys.all, "list"] as const,
  list: (params: { page: number; size: number }) =>
    [...todoKeys.lists(), params] as const,
};

export function useTodos(page: number = 1, size: number = 10000) {
  return useQuery({
    queryKey: todoKeys.list({ page, size }),
    queryFn: async (): Promise<TodoListResponse> => {
      const response = await api.get("/todos", {
        params: { page, size },
      });
      return response.data;
    },
  });
}

export function useCreateTodo() {
  return useMutation({
    mutationFn: async (data: CreateTodoRequest): Promise<Todo> => {
      const response = await api.post("/todos", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: todoKeys.all });
      toast.success("Todo created successfully!");
    },
    onError: () => {
      toast.error("Failed to create todo");
    },
  });
}


export function useUpdateTodo() {
  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: UpdateTodoRequest;
    }): Promise<Todo> => {
      const response = await api.put(`/todos/${id}`, data);
      return response.data;
    },
    onMutate: async ({ id, data }) => {
      // Cancel any outgoing list queries so they don't overwrite our optimistic write
      await queryClient.cancelQueries({ queryKey: todoKeys.lists() });

      // Snapshot every cached list page so we can restore on error
      const previousLists = queryClient.getQueriesData<TodoListResponse>({
        queryKey: todoKeys.lists(),
      });

      // Apply the optimistic update to every cached list page
      previousLists.forEach(([key, list]) => {
        if (!list) return;
        queryClient.setQueryData<TodoListResponse>(key, {
          ...list,
          items: list.items.map((todo) =>
            todo.id === id ? { ...todo, ...data } : todo
          ),
        });
      });

      return { previousLists };
    },
    onError: () => {
      toast.error("Failed to update todo");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: todoKeys.all });
    },
  });
}

export function useDeleteTodo() {
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/todos/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: todoKeys.all });
      toast.success("Todo deleted successfully!");
    },
    onError: () => {
      toast.error("Failed to delete todo");
    },
  });
}

export function useToggleTodo() {
  const updateTodo = useUpdateTodo();

  return {
    ...updateTodo,
    mutate: (todo: Todo) => {
      updateTodo.mutate({
        id: todo.id,
        data: { completed: !todo.completed },
      });
    },
  };
}
