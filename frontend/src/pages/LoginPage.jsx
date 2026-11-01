import { useState } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import { loginRequest, registerRequest, setToken } from "../services/authApi.js";
import { friendlyAuthError } from "../services/authErrors.js";
import { Button, Card, Input } from "../components/ui/index.js";

const PENDING_MESSAGE = "Your account is awaiting administrator approval.";

export default function LoginPage() {
  const { setUser } = useAuth();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [accountType, setAccountType] = useState("EMPLOYEE");
  const [adminCode, setAdminCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pendingName, setPendingName] = useState("");

  function switchMode(next) {
    setMode(next);
    setError("");
    setPendingName("");
  }

  function backToLogin() {
    setMode("login");
    setError("");
    setPendingName("");
    setPassword("");
    setConfirmPassword("");
    setAdminCode("");
  }

  async function handleLogin(event) {
    event.preventDefault();
    setError("");
    if (!username.trim() || !password) {
      setError("Please enter your username and password.");
      return;
    }
    setBusy(true);
    try {
      const body = await loginRequest(username.trim(), password);
      setToken(body.access_token);
      setUser(body.user);
    } catch (err) {
      setError(friendlyAuthError(err, "Login failed. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  async function handleRegister(event) {
    event.preventDefault();
    setError("");
    if (username.trim().length < 3) {
      setError("Username must contain at least 3 characters.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (accountType === "ADMIN" && !adminCode.trim()) {
      setError("Administrator Security Code is required.");
      return;
    }
    setBusy(true);
    try {
      const body = await registerRequest({
        username: username.trim(),
        password,
        confirmPassword,
        accountType,
        adminCode: adminCode.trim(),
      });
      if (body?.user?.status === "PENDING") {
        setPendingName(body.user.username || username.trim());
        setMode("pending");
        setPassword("");
        setConfirmPassword("");
        setAdminCode("");
        return;
      }
      backToLogin();
    } catch (err) {
      setError(friendlyAuthError(err, "Registration failed. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-canvas px-4 py-10">
      <div
        className="pointer-events-none absolute inset-0 opacity-60"
        aria-hidden="true"
        style={{
          background:
            "radial-gradient(60% 40% at 50% 0%, rgb(var(--accent-soft)) 0%, transparent 70%)",
        }}
      />
      <Card className="relative w-full max-w-md" padding="lg">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-control bg-accent text-accentContrast shadow-xs">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M4 7.5A3.5 3.5 0 0 1 7.5 4h9A3.5 3.5 0 0 1 20 7.5v5A3.5 3.5 0 0 1 16.5 16H11l-4.5 4v-4H7.5A3.5 3.5 0 0 1 4 12.5v-5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            </svg>
          </span>
          <div>
            <p className="type-overline text-accentText">SweaterCo · Track 1</p>
            <h1 className="type-h3 text-foreground">General Manager&apos;s Co-Pilot</h1>
          </div>
        </div>

        {mode === "pending" ? (
          <div className="mt-6 rounded-card border border-accent/30 bg-accentSoft p-5 text-center">
            <h2 className="type-h3 text-foreground">Account Created</h2>
            <p className="mt-2 type-body text-foreground/90">
              {pendingName ? `${pendingName}, ` : ""}
              {PENDING_MESSAGE}
            </p>
            <p className="mt-1 type-caption text-muted">
              You will be able to sign in after an administrator approves your account.
            </p>
            <Button className="mt-4 w-full" onClick={backToLogin}>
              Back to Log In
            </Button>
          </div>
        ) : (
          <>
            <p className="mt-2 type-sm text-muted">
              {mode === "login" ? "Log in to continue." : "Create an account."}
            </p>

            {mode === "login" ? (
              <form onSubmit={handleLogin} className="mt-5 space-y-4">
                <Input
                  label="Username"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  leadingIcon={
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.8" />
                      <path d="M5 20c0-3.3 3.1-6 7-6s7 2.7 7 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    </svg>
                  }
                />
                <Input
                  label="Password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                {error && <p className="type-caption text-danger">{error}</p>}
                <Button type="submit" fullWidth disabled={busy} loading={busy}>
                  {busy ? "Logging in…" : "Log In"}
                </Button>
                <button
                  type="button"
                  onClick={() => switchMode("register")}
                  className="focus-ring block w-full text-center type-sm text-muted underline-offset-2 transition-colors hover:text-foreground hover:underline"
                >
                  Create Account
                </button>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="mt-5 space-y-4">
                <Input
                  label="Username"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
                <Input
                  label="Password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  hint="Password must be at least 8 characters."
                />
                <Input
                  label="Confirm Password"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
                <fieldset>
                  <legend className="mb-1.5 type-sm font-medium text-foreground">Account Type</legend>
                  <div className="flex gap-4 type-sm text-foreground">
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="account-type"
                        value="EMPLOYEE"
                        checked={accountType === "EMPLOYEE"}
                        onChange={() => setAccountType("EMPLOYEE")}
                        className="h-4 w-4 accent-[rgb(var(--accent))]"
                      />
                      Employee
                    </label>
                    <label className="flex items-center gap-2">
                      <input
                        type="radio"
                        name="account-type"
                        value="ADMIN"
                        checked={accountType === "ADMIN"}
                        onChange={() => setAccountType("ADMIN")}
                        className="h-4 w-4 accent-[rgb(var(--accent))]"
                      />
                      Administrator
                    </label>
                  </div>
                </fieldset>
                {accountType === "ADMIN" && (
                  <Input
                    label="Administrator Security Code"
                    autoComplete="off"
                    value={adminCode}
                    onChange={(e) => setAdminCode(e.target.value)}
                  />
                )}
                {error && <p className="type-caption text-danger">{error}</p>}
                <Button type="submit" fullWidth disabled={busy} loading={busy}>
                  {busy ? "Creating…" : "Create Account"}
                </Button>
                <button
                  type="button"
                  onClick={backToLogin}
                  className="focus-ring block w-full text-center type-sm text-muted underline-offset-2 transition-colors hover:text-foreground hover:underline"
                >
                  Back to Log In
                </button>
              </form>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
