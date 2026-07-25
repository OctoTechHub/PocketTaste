"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuthContext } from "@/components/providers/auth-provider";
import { authApi } from "@/lib/api/endpoints";
import type { LoginRequest, RegisterRequest } from "@/lib/api/types";

/** Read-only auth state: `account`, `isAuthenticated`, `logout`. */
export function useAuth() {
  const { account, isAuthenticated, logout } = useAuthContext();
  return { account, isAuthenticated, logout };
}

/** POST /auth/login — persists the session and clears cached queries. */
export function useLogin() {
  const { setSession } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginRequest) => authApi.login(body),
    onSuccess: (token) => {
      setSession(token);
      qc.invalidateQueries();
    },
  });
}

/** POST /auth/register — creates the account, then signs in. */
export function useRegister() {
  const { setSession } = useAuthContext();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterRequest) => authApi.register(body),
    onSuccess: (token) => {
      setSession(token);
      qc.invalidateQueries();
    },
  });
}
