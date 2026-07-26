"use client";

import { Lock, Mail, User, X } from "lucide-react";
import { useState } from "react";

import { Drawer } from "@/components/motion/drawer";
import { Input } from "@/components/motion/input";
import { StatefulButton, type ButtonState } from "@/components/motion/button";
import { useLogin, useRegister } from "@/hooks/api/use-auth";
import { ApiError } from "@/lib/api/client";

type Mode = "login" | "register";

function errorText(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}

/** Sign-in / sign-up panel. beui Drawer + Input + StatefulButton over the auth mutations. */
export function AuthDrawer({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  const login = useLogin();
  const register = useRegister();
  const active = mode === "login" ? login : register;

  const state: ButtonState = active.isPending
    ? "loading"
    : active.isError
      ? "error"
      : active.isSuccess
        ? "success"
        : "idle";

  const submit = () => {
    if (mode === "login") {
      login.mutate({ email, password }, { onSuccess: () => onOpenChange(false) });
    } else {
      register.mutate(
        { email, password, display_name: displayName },
        { onSuccess: () => onOpenChange(false) },
      );
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    login.reset();
    register.reset();
  };

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      ariaLabel="Account"
      backdropClassName="bg-black/60 backdrop-blur"
      // Opaque, slightly-elevated surface so nothing bleeds through the panel.
      className="w-[420px] max-w-[92vw] gap-0 border-l border-border bg-card p-0"
    >
      {/* Branded header */}
      <div className="relative overflow-hidden border-b border-border bg-gradient-to-br from-primary/15 via-transparent to-chart-4/10 px-7 pb-6 pt-7">
        <button
          type="button"
          onClick={() => onOpenChange(false)}
          aria-label="Close"
          className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>

        <p className="text-xs font-black uppercase tracking-[0.2em] text-primary">
          Bolsillo
        </p>
        <h2 className="mt-2 text-2xl font-bold text-foreground">
          {mode === "login" ? "Welcome back" : "Create your account"}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {mode === "login"
            ? "Sign in to get personalised picks."
            : "Join to unlock your “For You” rail."}
        </p>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col gap-5 px-7 py-6">
        {/* Segmented toggle */}
        <div className="grid grid-cols-2 gap-1 rounded-full bg-muted p-1 text-sm">
          {(["login", "register"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => switchMode(m)}
              className={`rounded-full py-2 font-semibold transition-colors ${
                mode === m
                  ? "bg-primary text-primary-foreground shadow"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {m === "login" ? "Sign in" : "Sign up"}
            </button>
          ))}
        </div>

        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          {mode === "register" && (
            <Input
              label="Display name"
              placeholder="Your name"
              leftIcon={<User />}
              value={displayName}
              onChange={setDisplayName}
              autoComplete="name"
            />
          )}

          <Input
            label="Email"
            type="email"
            placeholder="you@example.com"
            leftIcon={<Mail />}
            value={email}
            onChange={setEmail}
            autoComplete="email"
            required
          />

          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            leftIcon={<Lock />}
            value={password}
            onChange={setPassword}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            error={active.isError ? errorText(active.error) : undefined}
            required
          />

          <StatefulButton
            type="submit"
            size="lg"
            className="mt-1 w-full"
            state={state}
            loadingText={mode === "login" ? "Signing in" : "Creating"}
            successText="Welcome!"
            errorText="Try again"
          >
            {mode === "login" ? "Sign in" : "Create account"}
          </StatefulButton>
        </form>

        <p className="mt-auto border-t border-border pt-4 text-xs leading-relaxed text-muted-foreground">
          Your listening is logged to your account and powers the “For You” rail
          and creator insights.
        </p>
      </div>
    </Drawer>
  );
}
