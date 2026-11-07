import { useRef, useState } from "react";
import { authHeaders } from "../services/authApi.js";
import { Spinner } from "./ui/Spinner.jsx";

async function emailRequest(path, method = "GET", data) {
  const response = await fetch(path, {
    method,
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (response.status === 401) window.dispatchEvent(new Event("sweaterco:unauthorized"));
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof result.detail === "string" ? result.detail : "Email request failed.");
  }
  return result;
}

export default function EmailDraft({ draft, turnId, index, locked = false, zh = false }) {
  const path = `/api/email/turns/${turnId}/drafts/${index}`;
  const [saved, setSaved] = useState(null);
  const [edit, setEdit] = useState(null);
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState("");
  const [error, setError] = useState("");
  const pending = useRef(false);

  async function run(operation) {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (err) {
      setError(err.message);
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }

  function load() {
    return run(async () => {
      const row = await emailRequest(path);
      setSaved(row);
      setEdit({ recipient_email: row.recipient_email || "", subject: row.subject, body: row.body });
      setPreview(Boolean(row.version && row.status !== "FAILED"));
    });
  }

  function save(event) {
    event.preventDefault();
    return run(async () => {
      const row = await emailRequest(path, "PUT", { ...edit, version: saved.version });
      setSaved(row);
      setEdit({ recipient_email: row.recipient_email || "", subject: row.subject, body: row.body });
      setPreview(true);
    });
  }

  function send() {
    if (!preview || !saved.can_send || pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    setPhase("sending");
    emailRequest(`/api/email/drafts/${saved.id}/send`, "POST", {
      version: saved.version,
      content_hash: saved.content_hash,
    })
      .then((row) => {
        setSaved(row);
        setPhase(row.status === "SUBMITTED" ? "sent" : "");
      })
      .catch((err) => {
        setError(err.message);
        setPhase("");
      })
      .finally(() => {
        pending.current = false;
        setBusy(false);
      });
  }

  const statusText = {
    DRAFT: "Saved draft. Awaiting confirmation.",
    SUBMITTED: "Submitted to the email service.",
    SENDING: "Submission in progress.",
    UNKNOWN: "Submission status is uncertain. Check the email service before sending again.",
    FAILED: "The email service rejected the submission.",
    CANCELLED: "Draft cancelled.",
  };
  const sending = phase === "sending";
  const control = "focus-ring rounded-lg border border-line bg-surface px-3 py-1.5 type-caption disabled:opacity-50";
  const field = "mt-1 block w-full rounded-lg border border-line bg-surface p-2";

  if (locked) {
    return (
      <section className="space-y-2 rounded-xl border border-line bg-surfaceMuted/40 p-3 type-sm">
        <p className="break-words font-medium">{draft.subject}</p>
        {draft.body && <p className="whitespace-pre-wrap break-words text-muted">{draft.body}</p>}
      </section>
    );
  }

  return (
    <section className="space-y-2 rounded-xl border border-line bg-surfaceMuted/40 p-3 type-sm">
      <p className="break-words font-medium">{draft.subject}</p>
      {!saved && <button type="button" className={control} disabled={busy} onClick={load}>Open email draft</button>}
      {saved && !preview && (
        <form className="space-y-2" onSubmit={save}>
          <label className="block">
            Recipient
            <input className={field} type="email" maxLength={254} disabled={busy} value={edit.recipient_email}
              onChange={(event) => setEdit({ ...edit, recipient_email: event.target.value })} />
          </label>
          <label className="block">
            Subject
            <input className={field} required maxLength={998} disabled={busy} value={edit.subject}
              onChange={(event) => setEdit({ ...edit, subject: event.target.value })} />
          </label>
          <label className="block">
            Message
            <textarea className={field} rows={5} required maxLength={100000} disabled={busy} value={edit.body}
              onChange={(event) => setEdit({ ...edit, body: event.target.value })} />
          </label>
          {saved.status === "FAILED" && <p role="status">{statusText.FAILED}</p>}
          <button type="submit" className={control} disabled={busy}>Save and preview</button>
        </form>
      )}
      {saved && preview && (
        <div className="space-y-2">
          <p className="break-words">From {saved.from_address || "—"}</p>
          <p className="break-words">To {saved.recipient_email || "—"}</p>
          <p className="break-words font-medium">{saved.subject}</p>
          <p className="whitespace-pre-wrap break-words">{saved.body}</p>
          <p role="status">{statusText[saved.status]}</p>
          {saved.status === "DRAFT" && !saved.can_send && (
            <p className="text-muted">Sending requires an enabled email service and one recipient address.</p>
          )}
          <div className="flex flex-wrap gap-2">
            {["DRAFT", "FAILED"].includes(saved.status) && (
              <button type="button" className={control} disabled={busy || sending} onClick={() => setPreview(false)}>Edit draft</button>
            )}
            {saved.can_send && (
              <button type="button" className={control} disabled={busy} onClick={send}>Confirm and send</button>
            )}
          </div>
        </div>
      )}
      {saved && <button type="button" className={control} disabled={busy || sending} onClick={load}>Reload draft</button>}
      {sending && (
        <p role="status" className="flex items-center gap-2 text-muted">
          <Spinner size={14} />
          {zh ? "发送中" : "Sending"}
        </p>
      )}
      {phase === "sent" && (
        <p role="status" className="flex items-center gap-2 text-success">
          <span aria-hidden="true">✔</span>
          {zh ? "发送成功" : "Sent successfully"}
        </p>
      )}
      {error && <p role="alert" className="text-danger">{error}</p>}
    </section>
  );
}
