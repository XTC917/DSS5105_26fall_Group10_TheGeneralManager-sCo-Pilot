import { useEffect, useMemo, useState } from "react";
import Sidebar from "../components/Sidebar.jsx";
import ChatPanel from "../components/ChatPanel.jsx";
import DataManagement from "./DataManagement.jsx";
import { fetchHealth } from "../services/api.js";

function newConversationId() {
  return `gm-${Date.now()}`;
}

export default function Home() {
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [boardTick, setBoardTick] = useState(0);
  const [activeView, setActiveView] = useState("copilot");
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
                  {health.llm_configured ? "" : " · set GOOGLE_API_KEY (gemini) or OPENAI_API_KEY for chat"}
                </span>
              )}
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-5 px-5 py-5 lg:grid-cols-[260px_1fr]">
        <div className="space-y-3">
          <nav className="rounded-lg border border-ink/10 bg-white p-2 shadow-sm">
            <button
              type="button"
              onClick={() => setActiveView("copilot")}
              className={`block w-full rounded-md px-3 py-2 text-left text-sm font-medium ${
                activeView === "copilot"
                  ? "bg-ink text-paper"
                  : "text-ink/70 hover:bg-paper"
              }`}
            >
              GM Co-Pilot
            </button>
            <button
              type="button"
              onClick={() => setActiveView("data")}
              className={`mt-1 block w-full rounded-md px-3 py-2 text-left text-sm font-medium ${
                activeView === "data"
                  ? "bg-ink text-paper"
                  : "text-ink/70 hover:bg-paper"
              }`}
            >
              Data Management
            </button>
          </nav>
          {activeView === "copilot" && <Sidebar refreshToken={boardTick} />}
        </div>
        {activeView === "copilot" ? (
          <ChatPanel
            conversationId={conversationId}
            llmReady={Boolean(health?.llm_configured)}
            onBoardChanged={() => setBoardTick((n) => n + 1)}
          />
        ) : (
          <DataManagement />
        )}
      </main>
    </div>
  );
}
