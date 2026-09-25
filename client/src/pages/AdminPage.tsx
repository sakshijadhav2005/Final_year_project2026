import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listAdminJobs, listAdminUsers, listAudit, setUserRole, type UserRole } from "@/lib/api";
import { GoldenShell } from "@/layouts/GoldenShell";
import { useAuthStore } from "@/store/auth";

export function AdminPage() {
  const token = useAuthStore((s) => s.accessToken) as string;
  const currentUser = useAuthStore((s) => s.user);
  const role = currentUser?.role;
  const queryClient = useQueryClient();

  const [selectedRoles, setSelectedRoles] = useState<Record<string, UserRole>>({});
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const jobs = useQuery({ queryKey: ["admin-jobs"], queryFn: () => listAdminJobs(token), enabled: role === "admin" });
  const audit = useQuery({ queryKey: ["audit"], queryFn: () => listAudit(token), enabled: role === "admin" });
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => listAdminUsers(token), enabled: role === "admin" });

  const updateRoleMutation = useMutation({
    mutationFn: async ({ userId, newRole }: { userId: string; newRole: UserRole }) => {
      setUpdatingUserId(userId);
      return setUserRole(token, userId, newRole);
    },
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      queryClient.invalidateQueries({ queryKey: ["audit"] });
      setSelectedRoles((prev) => {
        const next = { ...prev };
        delete next[updated.id];
        return next;
      });
      setStatusMessage({
        type: "success",
        text: `Successfully updated role for ${updated.email} to ${updated.role.replace("_", " ")}.`,
      });
      setTimeout(() => setStatusMessage(null), 4000);
    },
    onError: (err: Error) => {
      setStatusMessage({
        type: "error",
        text: err.message || "Failed to update user role.",
      });
      setTimeout(() => setStatusMessage(null), 5000);
    },
    onSettled: () => {
      setUpdatingUserId(null);
    },
  });

  function handleRoleSelect(userId: string, newRole: UserRole) {
    setSelectedRoles((prev) => ({ ...prev, [userId]: newRole }));
  }

  function handleSaveRole(userId: string, currentRole: UserRole) {
    const targetRole = selectedRoles[userId] ?? currentRole;
    if (targetRole === currentRole) return;
    setStatusMessage(null);
    updateRoleMutation.mutate({ userId, newRole: targetRole });
  }

  if (role !== "admin") {
    return (
      <GoldenShell>
        <div className="max-w-md mx-auto py-55 text-center">
          <h1 className="font-display text-2xl font-bold text-ink-light dark:text-ink-dark">Admin Console</h1>
          <p className="mt-13 text-sm text-ink-dim">Admin role required. Sign in or register as an administrator.</p>
        </div>
      </GoldenShell>
    );
  }

  return (
    <GoldenShell>
      <div className="space-y-34">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-gold">System Management</p>
          <h1 className="font-display text-3xl font-normal italic text-ink-light dark:text-ink-dark">
            Administrative <em className="not-italic text-gold-soft">Overview</em>
          </h1>
        </div>

        {/* User & Role Management Section */}
        <div className="glass p-21 sm:p-26 space-y-16">
          <div className="flex flex-wrap items-center justify-between gap-10 border-b border-[#D8B478]/15 pb-13">
            <div>
              <div className="flex items-center gap-8">
                <span className="text-lg">🛡️</span>
                <h2 className="font-display text-xl text-ink-light dark:text-ink-dark">
                  User &amp; Role Management
                </h2>
                <span className="rounded-full border border-gold/30 bg-gold/10 px-8 py-0.5 text-xs font-medium text-gold-soft">
                  {(users.data ?? []).length} Accounts
                </span>
              </div>
              <p className="text-xs text-ink-dim mt-1">
                Configure role assignments and system permissions across all registered EventAI users.
              </p>
            </div>
          </div>

          {/* Feedback Banner */}
          {statusMessage && (
            <div
              className={`rounded-card border p-13 text-xs flex items-center justify-between transition-all ${
                statusMessage.type === "success"
                  ? "border-teal/40 bg-teal/15 text-teal"
                  : "border-danger/40 bg-danger/15 text-danger"
              }`}
            >
              <span>{statusMessage.type === "success" ? "✓" : "⚠️"} {statusMessage.text}</span>
              <button
                type="button"
                onClick={() => setStatusMessage(null)}
                className="opacity-70 hover:opacity-100 font-bold px-2 py-0.5"
              >
                ✕
              </button>
            </div>
          )}

          {/* Users Table / List */}
          <div className="overflow-x-auto">
            {users.isLoading ? (
              <div className="p-34 text-center">
                <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gold border-t-transparent" />
                <p className="mt-8 text-xs text-ink-dim">Loading user accounts...</p>
              </div>
            ) : (users.data ?? []).length === 0 ? (
              <p className="text-xs opacity-60 text-center py-21">No registered users found.</p>
            ) : (
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-ink-dim uppercase text-[10px] tracking-wider">
                    <th className="py-8 px-8 font-semibold">User</th>
                    <th className="py-8 px-8 font-semibold">Current Role</th>
                    <th className="py-8 px-8 font-semibold">Registered</th>
                    <th className="py-8 px-8 font-semibold text-right">Role Assignment</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {users.data?.map((user) => {
                    const isSelf = user.id === currentUser?.id;
                    const isBootstrapAdmin = user.email.toLowerCase() === "admin@example.com";
                    const selectedRole = selectedRoles[user.id] ?? user.role;
                    const isChanged = selectedRole !== user.role;
                    const isUpdating = updatingUserId === user.id;

                    const formattedDate = user.created_at
                      ? new Date(user.created_at).toLocaleDateString(undefined, {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                        })
                      : "—";

                    return (
                      <tr key={user.id} className="hover:bg-white/[0.02] transition-colors">
                        {/* User Email & Name */}
                        <td className="py-13 px-8">
                          <div className="flex flex-col">
                            <span className="font-medium text-ink-light dark:text-ink-dark">
                              {user.email}
                            </span>
                            {user.profile?.full_name && (
                              <span className="text-[11px] text-ink-dim">
                                {user.profile.full_name}
                                {user.profile.organization ? ` • ${user.profile.organization}` : ""}
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Current Role Badge */}
                        <td className="py-13 px-8">
                          <span
                            className={`inline-block rounded-full px-8 py-1 text-[10px] font-semibold uppercase tracking-wider ${
                              user.role === "admin"
                                ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                                : user.role === "event_organizer"
                                ? "bg-gold/15 text-gold-soft border border-gold/30"
                                : user.role === "content_creator"
                                ? "bg-teal/15 text-teal border border-teal/30"
                                : "bg-white/10 text-ink-dim border border-white/15"
                            }`}
                          >
                            {user.role.replace("_", " ")}
                          </span>
                        </td>

                        {/* Registration Date */}
                        <td className="py-13 px-8 text-ink-dim text-[11px]">
                          {formattedDate}
                        </td>

                        {/* Role Assignment Action */}
                        <td className="py-13 px-8 text-right">
                          {isSelf ? (
                            <span className="text-[11px] text-ink-dim italic">
                              Current Session (Protected)
                            </span>
                          ) : isBootstrapAdmin ? (
                            <span className="rounded-full bg-gold/10 border border-gold/30 px-8 py-2 text-[10px] font-semibold text-gold-soft uppercase">
                              Bootstrap Admin (Protected)
                            </span>
                          ) : (
                            <div className="inline-flex items-center gap-8 justify-end">
                              <select
                                value={selectedRole}
                                onChange={(e) => handleRoleSelect(user.id, e.target.value as UserRole)}
                                disabled={isUpdating}
                                className="rounded-lg border border-gold/30 bg-surface-light dark:bg-surface-dark px-8 py-4 text-xs text-ink-light dark:text-ink-dark focus:border-gold focus:outline-none"
                              >
                                <option value="regular_user">Regular User</option>
                                <option value="event_organizer">Event Organizer</option>
                                <option value="content_creator">Content Creator</option>
                                <option value="admin">Administrator</option>
                              </select>

                              <button
                                type="button"
                                onClick={() => handleSaveRole(user.id, user.role)}
                                disabled={!isChanged || isUpdating}
                                className="inline-flex items-center gap-4 rounded-full border border-gold/40 bg-gold/15 px-13 py-4 text-xs font-medium text-gold-soft hover:bg-gold/25 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                              >
                                {isUpdating ? (
                                  <>
                                    <div className="h-3 w-3 animate-spin rounded-full border border-gold-soft border-t-transparent" />
                                    <span>Saving…</span>
                                  </>
                                ) : (
                                  <span>Save</span>
                                )}
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Existing Sections: Jobs List & Audit Trail */}
        <div className="grid md:grid-cols-2 gap-21">
          {/* Jobs List */}
          <div className="glass p-21 space-y-13">
            <h2 className="font-display text-lg text-ink-light dark:text-ink-dark border-b border-[#D8B478]/15 pb-8">
              All Workspace Jobs
            </h2>
            <div className="flex flex-col gap-8 max-h-[60vh] overflow-y-auto">
              {(jobs.data ?? []).length === 0 ? (
                <p className="text-xs opacity-60">No jobs recorded yet.</p>
              ) : (
                jobs.data?.map((job) => (
                  <div key={job.id} className="glass p-13 text-xs flex justify-between items-center">
                    <span className="font-mono text-[11px] opacity-80">{job.id.slice(0, 10)}</span>
                    <span className="font-semibold uppercase text-gold-soft text-[10px] bg-gold/10 px-8 py-2 rounded-full">
                      {job.status}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Audit Trail */}
          <div className="glass p-21 space-y-13">
            <h2 className="font-display text-lg text-ink-light dark:text-ink-dark border-b border-[#D8B478]/15 pb-8">
              Audit Trail
            </h2>
            <div className="flex flex-col gap-8 max-h-[60vh] overflow-y-auto">
              {(audit.data ?? []).length === 0 ? (
                <p className="text-xs opacity-60">No audit events logged.</p>
              ) : (
                audit.data?.slice(0, 20).map((row) => (
                  <div key={String(row.id)} className="glass p-13 text-xs flex justify-between">
                    <span className="font-medium text-ink-light dark:text-ink-dark">{row.action}</span>
                    <span className="opacity-60 text-[11px]">{row.resource_type}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </GoldenShell>
  );
}
