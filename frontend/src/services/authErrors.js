const TOKEN_KEY = "sweaterco_token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

export function authHeaders(extra = {}) {
  const token = getToken();
  if (!token) return { ...extra };
  return { ...extra, Authorization: `Bearer ${token}` };
}

export function setStoredToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage unavailable; auth simply won't persist
  }
}

/** Normalize any auth/API error into a short human-readable message. Never raw JSON. */
export function friendlyAuthError(err, fallback) {
  const fallbackMsg = fallback || "Something went wrong. Please try again.";
  if (!err) return fallbackMsg;
  const raw = typeof err === "string" ? err : err.message || "";
  if (!raw) return fallbackMsg;
  const text = String(raw);
  const lower = text.toLowerCase();

  if (lower.includes("failed to fetch") || lower.includes("networkerror") || lower.includes("network error")) {
    return "Cannot reach the server. Please check your connection and try again.";
  }
  if (lower.includes("at least 8 characters") || lower.includes("string_too_short")) {
    return "Password must be at least 8 characters.";
  }
  if (lower.includes("password confirmation does not match") || lower.includes("passwords do not match")) {
    return "Passwords do not match.";
  }
  if (lower.includes("username already exists") || lower.includes("already registered")) {
    return "This username is already registered.";
  }
  if (lower.includes("invalid administrator security code")) {
    return "Invalid administrator security code.";
  }
  if (lower.includes("awaiting administrator approval")) {
    return "Your account is awaiting administrator approval. You will be able to sign in after an administrator approves your account.";
  }
  if (lower.includes("invalid username or password")) {
    return "Incorrect username or password. Please try again.";
  }
  if (lower.includes("registration was rejected")) {
    return "Your registration was rejected. Please contact an administrator.";
  }
  if (lower.includes("account is disabled")) {
    return "Your account is disabled. Please contact an administrator.";
  }
  if (lower.includes("has been deactivated") || lower.includes("account is not active")) {
    return "This account has been deactivated.";
  }
  if (lower.includes("administrator access required")) {
    return "Administrator access required.";
  }
  if (lower.includes("session expired") || lower.includes("not authenticated") || lower.includes("invalid or expired")) {
    return "Your session has expired. Please log in again.";
  }
  // FastAPI sometimes returns a JSON array string for validation errors.
  if (text.trim().startsWith("[") || text.trim().startsWith("{")) {
    if (lower.includes("password")) return "Password must be at least 8 characters.";
    return fallbackMsg;
  }
  // Keep backend one-liners, but cap length so nothing verbose leaks through.
  return text.length > 160 ? fallbackMsg : text;
}
