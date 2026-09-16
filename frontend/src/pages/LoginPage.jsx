import { useState } from "react";
import { useAuth } from "../auth/AuthContext.jsx";
import { loginRequest, registerRequest, setToken } from "../services/authApi.js";
import { friendlyAuthError } from "../services/authErrors.js";

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
      // Only ACTIVE accounts reach here; PENDING/REJECTED/DISABLED get 403.
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
        // Dedicated pending state; never log a PENDING employee in.
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

  const inputClass =
    "w-full rounded-md border border-ink/15 bg-white px-3 py-2 text-sm text-ink placeholder:text-ink/40 focus:border-brass focus:outline-none";

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4">
      <div className="w-full max-w-md rounded-lg border border-ink/10 bg-white p-6 shadow-sm">
        <p className="text-[11px] uppercase tracking-[0.18em] text-brass">SweaterCo · Track 1</p>
        <h1 className="mt-1 text-lg font-semibold text-ink">General Manager&apos;s Co-Pilot</h1>

        {mode === "pending" ? (
          <div className="mt-5 rounded-md border border-brass/40 bg-paper p-5 text-center">
            <h2 className="text-base font-semibold text-ink">Account Created</h2>
            <p className="mt-2 text-sm text-ink/80">
              {pendingName ? `${pendingName}, ` : ""}{PENDING_MESSAGE}
            </p>
            <p className="mt-1 text-xs text-ink/55">
              You will be able to sign in after an administrator approves your account.
            </p>
            <button
              type="button"
              onClick={backToLogin}
              className="mt-4 w-full rounded-md bg-ink px-3 py-2 text-sm font-medium text-paper"
            >
              Back to Log In
            </button>
          </div>
        ) : (
          <>
            <p className="mt-1 text-xs text-ink/55">
              {mode === "login" ? "Log in to continue." : "Create an account."}
            </p>

            {mode === "login" ? (
              <form onSubmit={handleLogin} className="mt-5 space-y-3">
                <div>
                  <label htmlFor="login-username" className="mb-1 block text-xs font-medium text-ink/70">
                    Username
                  </label>
                  <input
                    id="login-username"
                    className={inputClass}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                  />
                </div>
                <div>
                  <label htmlFor="login-password" className="mb-1 block text-xs font-medium text-ink/70">
                    Password
                  </label>
                  <input
                    id="login-password"
                    type="password"
                    className={inputClass}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                  />
                </div>
                {error && <p className="text-xs text-red-600">{error}</p>}
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full rounded-md bg-ink px-3 py-2 text-sm font-medium text-paper disabled:opacity-60"
                >
                  {busy ? "Logging in…" : "Log In"}
                </button>
                <button
                  type="button"
                  onClick={() => switchMode("register")}
                  className="w-full text-center text-xs text-ink/60 underline-offset-2 hover:underline"
                >
                  Create Account
                </button>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="mt-5 space-y-3">
                <div>
                  <label htmlFor="reg-username" className="mb-1 block text-xs font-medium text-ink/70">
                    Username
                  </label>
                  <input
                    id="reg-username"
                    className={inputClass}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                  />
                </div>
                <div>
                  <label htmlFor="reg-password" className="mb-1 block text-xs font-medium text-ink/70">
                    Password
                  </label>
                  <input
                    id="reg-password"
                    type="password"
                    className={inputClass}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                  <p className="mt-1 text-[11px] text-ink/55">Password must be at least 8 characters.</p>
                </div>
                <div>
                  <label htmlFor="reg-confirm" className="mb-1 block text-xs font-medium text-ink/70">
                    Confirm Password
                  </label>
                  <input
                    id="reg-confirm"
                    type="password"
                    className={inputClass}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>
                <fieldset>
                  <legend className="mb-1 text-xs font-medium text-ink/70">Account Type</legend>
                  <div className="flex gap-4 text-sm text-ink">
                    <label className="flex items-center gap-1.5">
                      <input
                        type="radio"
                        name="account-type"
                        value="EMPLOYEE"
                        checked={accountType === "EMPLOYEE"}
                        onChange={() => setAccountType("EMPLOYEE")}
                      />
                      Employee
                    </label>
                    <label className="flex items-center gap-1.5">
                      <input
                        type="radio"
                        name="account-type"
                        value="ADMIN"
                        checked={accountType === "ADMIN"}
                        onChange={() => setAccountType("ADMIN")}
                      />
                      Administrator
                    </label>
                  </div>
                </fieldset>
                {accountType === "ADMIN" && (
                  <div>
                    <label htmlFor="reg-admin-code" className="mb-1 block text-xs font-medium text-ink/70">
                      Administrator Security Code
                    </label>
                    <input
                      id="reg-admin-code"
                      className={inputClass}
                      value={adminCode}
                      onChange={(e) => setAdminCode(e.target.value)}
                      autoComplete="off"
                    />
                  </div>
                )}
                {error && <p className="text-xs text-red-600">{error}</p>}
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full rounded-md bg-ink px-3 py-2 text-sm font-medium text-paper disabled:opacity-60"
                >
                  {busy ? "Creating…" : "Create Account"}
                </button>
                <button
                  type="button"
                  onClick={backToLogin}
                  className="w-full text-center text-xs text-ink/60 underline-offset-2 hover:underline"
                >
                  Back to Log In
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  );
}
