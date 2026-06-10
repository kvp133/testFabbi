import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useLogout, fetchCurrentUser } from "../api/auth";

export function useAuth() {
  const navigate = useNavigate();
  const logoutMutation = useLogout();

  const token = localStorage.getItem("access_token");
  const isAuthenticated = !!token;

  const {
    data: user,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["currentUser"],
    queryFn: fetchCurrentUser,
    enabled: isAuthenticated,
    retry: false,
  });

  const logout = () => {
    // Session cleanup (tokens + react-query cache) happens in the
    // mutation's onSettled, so we only need to navigate here.
    logoutMutation.mutate(undefined, {
      onSettled: () => {
        navigate("/login");
      },
    });
  };

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    logout,
  };
}
