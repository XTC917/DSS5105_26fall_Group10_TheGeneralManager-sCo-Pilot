import { lazy, Suspense, useEffect, useState } from "react";
import { AuthProvider, useAuth } from "./auth/AuthContext.jsx";
import Home from "./pages/Home.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import ThemePreview from "./pages/ThemePreview.jsx";

const DesignPreview = import.meta.env.DEV
  ? lazy(() => import("./pages/design-preview/DesignPreview.jsx"))
  : null;

function useDevPreviewRoute(target) {
  const [active, setActive] = useState(() => {
    if (!import.meta.env.DEV || typeof window === "undefined") return false;
    return window.location.hash.replace(/^#\/?/, "") === target;
  });

  useEffect(() => {
    if (!import.meta.env.DEV || typeof window === "undefined") return undefined;
    const readRoute = () => window.location.hash.replace(/^#\/?/, "") === target;
    const syncRoute = () => setActive(readRoute());
    syncRoute();
    window.addEventListener("hashchange", syncRoute);
    window.addEventListener("popstate", syncRoute);
    return () => {
      window.removeEventListener("hashchange", syncRoute);
      window.removeEventListener("popstate", syncRoute);
    };
  }, [target]);

  return active;
}

/**
 * Dev-only design-system preview. Reached via `/#theme-preview` while running
 * `vite` locally. It is compiled out of the production render path
 * (`import.meta.env.DEV` is false in builds) and never affects auth/routing.
 */
function isThemePreview() {
  if (!import.meta.env.DEV || typeof window === "undefined") return false;
  return window.location.hash.replace(/^#\/?/, "") === "theme-preview";
}

/**
 * Phase 5A Soft Intelligence preview. Dev-only, static, and mounted before
 * auth so it never touches the login, conversation or API flows. The lazy
 * import keeps the preview out of the production entry bundle.
 */
function PreviewFallback() {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-canvas">
      <p className="text-sm text-muted">Loading design preview…</p>
    </div>
  );
}


function Shell() {
  const { isAuthenticated, authLoading } = useAuth();

  if (isThemePreview()) {
    return <ThemePreview />;
  }

  if (authLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-paper">
        <p className="text-sm text-ink/60">Loading…</p>
      </div>
    );
  }

  if (!isAuthenticated) return <LoginPage />;
  return <Home />;
}

export default function App() {
  const showDesignPreview = useDevPreviewRoute("design-preview");

  if (showDesignPreview) {
    return (
      <Suspense fallback={<PreviewFallback />}>
        <DesignPreview />
      </Suspense>
    );
  }

  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
