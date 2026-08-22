import { useEffect, useMemo, useState } from "react";
import Sidebar from "../components/Sidebar.jsx";
import ChatPanel from "../components/ChatPanel.jsx";
import { fetchHealth } from "../services/api.js";

function newConversationId() {
  return `gm-${Date.now()}`;
}

export default function Home() {
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const conversationId = useMemo(newConversationId, []);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err) => setHealthError(err.message));
  }, []);

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-ink/10 bg-ink text-paper">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-brass">
              SweaterCo · Track 1
            </p>
            <h1 className="text-lg font-semibold">General Manager&apos;s Co-Pilot</h1>
          </div>
          <div className="text-right text-xs text-paper/70">
            <p>Factory date: 1 Apr 2026</p>
            <p>
              {healthError && <span className="text-red-300">API offline — {healthError}</span>}
              {!healthError && health && (
                <span>
                  API {health.ok ? "ready" : "down"}
                  {health.llm_configured ? "" : " · set OPENAI_API_KEY for chat"}
                </span>
              )}
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-5 px-5 py-5 lg:grid-cols-[260px_1fr]">
        <Sidebar />
        <ChatPanel conversationId={conversationId} llmReady={Boolean(health?.llm_configured)} />
      </main>
    </div>
  );
}
