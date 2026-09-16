import { useCallback, useEffect, useState } from "react";
import { approveUser, disableUser, listAllUsers, listPendingUsers, rejectUser } from "../services/usersApi.js";
import { friendlyAuthError } from "../services/authErrors.js";

function fmtTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString();
}

export default function UserManagement() {
  const [pending, setPending] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirmReject, setConfirmReject] = useState(null);
  const [confirmDisable, setConfirmDisable] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [p, all] = await Promise.all([listPendingUsers(), listAllUsers()]);
      setPending(p.items || []);
      const items = all.items || [];
      setUsers(items.filter((u) => u.status !== "PENDING"));
    } catch (err) {
      setError(friendlyAuthError(err, "Failed to load users."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleApprove(user) {
    setBusyId(user.id);
    setError("");
    setNotice("");
    try {
      await approveUser(user.id);
      setPending((prev) => prev.filter((u) => u.id !== user.id));
      setNotice(`${user.username} approved and now ACTIVE.`);
      load();
    } catch (err) {
      setError(friendlyAuthError(err, "Approve failed."));
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(user) {
    setBusyId(user.id);
    setError("");
    setNotice("");
    try {
      await rejectUser(user.id);
      setPending((prev) => prev.filter((u) => u.id !== user.id));
      setNotice(`${user.username} rejected.`);
      setConfirmReject(null);
    } catch (err) {
      setError(friendlyAuthError(err, "Reject failed."));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDisable(user) {
    setBusyId(user.id);
    setError("");
    setNotice("");
    try {
      await disableUser(user.id);
      setNotice(`${user.username} disabled.`);
      setConfirmDisable(null);
      load();
    } catch (err) {
      setError(friendlyAuthError(err, "Disable failed."));
    } finally {
      setBusyId(null);
    }
  }

  const active = users.filter((u) => u.status === "ACTIVE");
  const others = users.filter((u) => u.status !== "ACTIVE");

  return (
    <section className="rounded-lg border border-ink/10 bg-white p-5 shadow-sm">
      <div className="mb-1">
        <h2 className="text-sm font-semibold text-ink">User Management</h2>
        <p className="text-xs text-ink/55">Approve employee registrations and manage account access.</p>
      </div>
      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}
      {notice && <p className="mt-3 text-xs text-green-700">{notice}</p>}
      {loading ? (
        <p className="mt-4 text-sm text-ink/60">Loading users…</p>
      ) : (
        <div className="mt-4 space-y-6">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/60">
              Pending Approvals ({pending.length})
            </h3>
            {pending.length === 0 ? (
              <p className="mt-2 text-sm text-ink/55">No pending registrations.</p>
            ) : (
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-ink/10 text-xs text-ink/55">
                      <th className="py-2 pr-3 font-medium">Username</th>
                      <th className="py-2 pr-3 font-medium">Email</th>
                      <th className="py-2 pr-3 font-medium">Requested</th>
                      <th className="py-2 pr-3 font-medium">Status</th>
                      <th className="py-2 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pending.map((u) => (
                      <tr key={u.id} className="border-b border-ink/5">
                        <td className="py-2 pr-3 font-medium text-ink">{u.username}</td>
                        <td className="py-2 pr-3 text-ink/70">{u.email || "—"}</td>
                        <td className="py-2 pr-3 text-ink/70">{fmtTime(u.created_at)}</td>
                        <td className="py-2 pr-3 text-ink/70">{u.status}</td>
                        <td className="py-2">
                          {confirmReject === u.id ? (
                            <span className="inline-flex items-center gap-2 text-xs">
                              <span className="text-ink/70">Reject {u.username}?</span>
                              <button
                                type="button"
                                disabled={busyId === u.id}
                                onClick={() => handleReject(u)}
                                className="rounded-md bg-red-600 px-2.5 py-1 font-medium text-white disabled:opacity-60"
                              >
                                Confirm reject
                              </button>
                              <button
                                type="button"
                                onClick={() => setConfirmReject(null)}
                                className="rounded-md border border-ink/15 px-2.5 py-1 text-ink/70"
                              >
                                Cancel
                              </button>
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-2">
                              <button
                                type="button"
                                disabled={busyId === u.id}
                                onClick={() => handleApprove(u)}
                                className="rounded-md bg-ink px-2.5 py-1 text-xs font-medium text-paper disabled:opacity-60"
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                onClick={() => setConfirmReject(u.id)}
                                className="rounded-md border border-ink/15 px-2.5 py-1 text-xs text-ink/70"
                              >
                                Reject
                              </button>
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/60">
              Active Users ({active.length})
            </h3>
            {active.length === 0 ? (
              <p className="mt-2 text-sm text-ink/55">No active users.</p>
            ) : (
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-ink/10 text-xs text-ink/55">
                      <th className="py-2 pr-3 font-medium">Username</th>
                      <th className="py-2 pr-3 font-medium">Role</th>
                      <th className="py-2 pr-3 font-medium">Status</th>
                      <th className="py-2 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {active.map((u) => (
                      <tr key={u.id} className="border-b border-ink/5">
                        <td className="py-2 pr-3 font-medium text-ink">{u.username}</td>
                        <td className="py-2 pr-3 text-ink/70">{u.role}</td>
                        <td className="py-2 pr-3 text-ink/70">{u.status}</td>
                        <td className="py-2">
                          {confirmDisable === u.id ? (
                            <span className="inline-flex items-center gap-2 text-xs">
                              <span className="text-ink/70">Disable {u.username}?</span>
                              <button
                                type="button"
                                disabled={busyId === u.id}
                                onClick={() => handleDisable(u)}
                                className="rounded-md bg-red-600 px-2.5 py-1 font-medium text-white disabled:opacity-60"
                              >
                                Confirm disable
                              </button>
                              <button
                                type="button"
                                onClick={() => setConfirmDisable(null)}
                                className="rounded-md border border-ink/15 px-2.5 py-1 text-ink/70"
                              >
                                Cancel
                              </button>
                            </span>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setConfirmDisable(u.id)}
                              className="rounded-md border border-ink/15 px-2.5 py-1 text-xs text-ink/70"
                            >
                              Disable
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {others.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/60">
                Other Accounts ({others.length})
              </h3>
              <ul className="mt-2 space-y-1 text-sm text-ink/70">
                {others.map((u) => (
                  <li key={u.id}>
                    {u.username} · {u.role} · {u.status}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
