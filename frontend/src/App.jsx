import { AuthProvider, useAuth } from "./auth/AuthContext.jsx";
import Home from "./pages/Home.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import ThemePreview from "./pages/ThemePreview.jsx";

/**
 * Dev-only design-system preview. Reached via `/#theme-preview` while running
 * `vite` locally. It is compiled out of the production render path
 * (`import.meta.env.DEV` is false in builds) and never affects auth/routing.
 */
function isThemePreview() {
  if (!import.meta.env.DEV || typeof window === "undefined") return false;
  return window.location.hash.replace(/^#\/?/, "") === "theme-preview";
}

function Shell() {
  const { isAuthenticated, authLoading } = useAuth();

  if (isThemePreview()) {
    return <ThemePreview />;
  }

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <p className="text-sm text-ink/60">Loading…</p>
      </div>
    );
  }

  if (!isAuthenticated) return <LoginPage />;
  return <Home />;
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
