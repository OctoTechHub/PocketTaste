"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/apiClient";
import type { HealthInfo, UserSummary } from "@/lib/types";

interface UserContextValue {
  users: UserSummary[];
  currentUserId: string | null;
  currentUser: UserSummary | null;
  setCurrentUserId: (id: string) => void;
  health: HealthInfo | null;
  loading: boolean;
  error: string | null;
}

const UserContext = createContext<UserContextValue | null>(null);

/** Owns the "who am I browsing as" selection + backend health, shared app-wide. */
export function UserProvider({ children }: { children: React.ReactNode }) {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.users(), api.health()])
      .then(([userList, healthInfo]) => {
        if (cancelled) return;
        setUsers(userList);
        setHealth(healthInfo);
        if (userList.length) setCurrentUserId(userList[0].id);
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : String(err)),
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<UserContextValue>(
    () => ({
      users,
      currentUserId,
      currentUser: users.find((u) => u.id === currentUserId) ?? null,
      setCurrentUserId,
      health,
      loading,
      error,
    }),
    [users, currentUserId, health, loading, error],
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used within <UserProvider>");
  return ctx;
}
