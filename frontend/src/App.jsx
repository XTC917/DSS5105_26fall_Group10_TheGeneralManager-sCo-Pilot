import { AuthProvider, useAuth } from "./auth/AuthContext.jsx";
import Home from "./pages/Home.jsx";
import LoginPage from "./pages/LoginPage.jsx";

function Shell() {
  const { user, isAuthenticated, authLoading } = useAuth();

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <p className="text-sm text-ink/60">Loading…</p>
      </div>
    );
  }

  if (!isAuthenticated) return <LoginPage />;
  return <Home key={user.id} />;
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
