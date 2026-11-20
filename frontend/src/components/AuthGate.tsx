import { useEffect, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Button, Card, Input, Label } from "./ui";

/** Shows a password screen when the server requires one (public deployments). */
export default function AuthGate({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["auth"], queryFn: api.auth.me, retry: false, staleTime: Infinity });
  const [locked, setLocked] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onLocked = () => setLocked(true);
    window.addEventListener("auth-required", onLocked);
    return () => window.removeEventListener("auth-required", onLocked);
  }, []);

  if (me.isLoading) return null;
  const needsLogin = locked || (me.data?.auth_required && !me.data.authenticated);
  if (!needsLogin) return <>{children}</>;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.auth.login(password);
      setLocked(false);
      setPassword("");
      await queryClient.invalidateQueries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <form onSubmit={submit} className="space-y-4 p-6">
          <h1 className="text-lg font-semibold">Deal Finder</h1>
          <div>
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {error ? <p className="text-xs text-danger">{error}</p> : null}
          <Button type="submit" variant="primary" className="w-full" disabled={busy || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
