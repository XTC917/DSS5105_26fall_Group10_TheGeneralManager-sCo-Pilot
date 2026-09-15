import { useState } from "react";
import DataUpload from "../components/dataAdmin/DataUpload.jsx";
import DataSourceList from "../components/dataAdmin/DataSourceList.jsx";

export default function DataManagement() {
  const [tab, setTab] = useState("upload");

  return (
    <section className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Data Management</h2>
          <p className="text-xs text-ink/55">
            Upload CSV/Excel into the three factory tables and preview dataset contents.
            Served by the integrated backend on :8000.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setTab("upload")}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium ${
              tab === "upload"
                ? "border-ink bg-ink text-paper"
                : "border-ink/15 text-ink/70 hover:border-brass"
            }`}
          >
            Upload Data
          </button>
          <button
            type="button"
            onClick={() => setTab("sources")}
            className={`rounded-full border px-4 py-1.5 text-sm font-medium ${
              tab === "sources"
                ? "border-ink bg-ink text-paper"
                : "border-ink/15 text-ink/70 hover:border-brass"
            }`}
          >
            Data Sources
          </button>
        </div>
      </div>

      <div className="mt-4 border-t border-ink/10 pt-4">
        {tab === "upload" ? <DataUpload /> : <DataSourceList />}
      </div>
    </section>
  );
}
