import { authHeaders, clearToken, getToken } from "./authErrors.js";

export { authHeaders, clearToken, getToken };

export function setToken(token) {
  try {
    if (token) localStorage.setItem("sweaterco_token", token);
    else localStorage.removeItem("sweaterco_token");
  } catch {
    // storage unavailable (private mode); auth simply won't persist
  }
}

async function parseBody(res) {
  const body = await res.json().catch(() => ({}));
  return body;
}

function rawMessage(body, fallback) {
  const detail = body?.detail ?? body?.message ?? fallback;
  return typeof detail === "string" ? detail : JSON.stringify(detail);
}

export async function loginRequest(username, password) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const body = await parseBody(res);
  if (!res.ok) throw new Error(rawMessage(body, "Login failed"));
  // Backend returns { access_token, token_type: "bearer", user }
  return body;
}

export async function registerRequest({ username, password, confirmPassword, accountType, adminCode }) {
  const payload = {
    username,
    password,
    confirm_password: confirmPassword,
    account_type: accountType,
  };
  if (accountType === "ADMIN") payload.admin_code = adminCode || null;
  const res = await fetch("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await parseBody(res);
  if (!res.ok) throw new Error(rawMessage(body, "Registration failed"));
  // Backend returns { user, message }
  return body;
}

export async function fetchMe() {
  const token = getToken();
  if (!token) throw new Error("Not authenticated");
  const res = await fetch("/api/auth/me", {
    headers: authHeaders(),
  });
  const body = await parseBody(res);
  if (!res.ok) throw new Error(rawMessage(body, "Session expired"));
  // Backend returns { user }
  return body.user;
}

export async function deactivateMe() {
  const res = await fetch("/api/auth/me", {
    method: "DELETE",
    headers: authHeaders(),
  });
  const body = await parseBody(res);
  if (!res.ok) throw new Error(rawMessage(body, "Deactivation failed"));
  return body;
}
