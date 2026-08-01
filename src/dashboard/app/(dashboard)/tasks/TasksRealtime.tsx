"use client";

import { useEffect, useRef, useState } from "react";
import { getSupabaseBrowser } from "../../../lib/supabase-browser";

export interface TaskRow {
  task_id: string;
  location_id: string | null;
  task_type: string;
  priority: string;
  status: string;
  assigned_to: string | null;
  title: string;
  description: string | null;
  due_at: string | null;
  sla_hours: number;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  staff: { full_name: string; short_name: string | null } | null;
}

const PRIORITY_COLOR: Record<string, string> = {
  URGENT: "bg-status-overdue-bg text-status-overdue",
  HIGH: "bg-warning-bg text-warning",
  NORMAL: "bg-surface-sunken text-ink-soft",
};

const STATUS_COLOR: Record<string, string> = {
  PENDING: "bg-status-ready-bg text-status-ready",
  IN_PROGRESS: "bg-status-in-progress-bg text-status-in-progress",
  DONE: "bg-status-completed-bg text-status-completed",
  CANCELLED: "bg-status-cancelled-bg text-status-cancelled",
};

export default function TasksRealtime({
  initialRows,
}: {
  initialRows: TaskRow[];
}) {
  const [rows, setRows] = useState<TaskRow[]>(initialRows);
  const [liveCount, setLiveCount] = useState<number>(0);
  const seenIdsRef = useRef<Set<string>>(
    new Set(initialRows.map((r) => r.task_id)),
  );

  useEffect(() => {
    const supabase = getSupabaseBrowser();
    const channel = supabase
      .channel("staff_task-pending")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "staff_task",
          filter: "status=eq.PENDING",
        },
        (payload) => {
          if (payload.eventType === "INSERT") {
            const r = payload.new as TaskRow;
            if (seenIdsRef.current.has(r.task_id)) return;
            seenIdsRef.current.add(r.task_id);
            setRows((prev) => [r, ...prev]);
            setLiveCount((c) => c + 1);
          } else if (payload.eventType === "UPDATE") {
            const r = payload.new as TaskRow;
            setRows((prev) =>
              prev.map((existing) =>
                existing.task_id === r.task_id ? { ...existing, ...r } : existing,
              ),
            );
          } else if (payload.eventType === "DELETE") {
            const r = payload.old as Partial<TaskRow>;
            if (!r.task_id) return;
            seenIdsRef.current.delete(r.task_id);
            setRows((prev) => prev.filter((x) => x.task_id !== r.task_id));
          }
        },
      )
      .subscribe();
    return () => {
      void supabase.removeChannel(channel);
    };
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="inline-flex h-2 w-2 animate-pulse rounded-full bg-success motion-reduce:animate-none" />
        <span className="text-xs text-ink-muted">
          Realtime live
          {liveCount > 0 && (
            <span className="ml-2 rounded-chip bg-success-bg px-2 py-0.5 font-medium text-success">
              +{liveCount} mới
            </span>
          )}
        </span>
      </div>

      {/* Mobile: card list (<md). */}
      <ul className="space-y-2 md:hidden">
        {rows.map((t) => (
          <li
            key={t.task_id}
            className="rounded-card border border-line bg-surface p-3 shadow-card"
          >
            <div className="flex items-start justify-between gap-2">
              <p className="font-medium text-ink">{t.title}</p>
              <span
                className={`shrink-0 rounded-chip px-2 py-0.5 text-[11px] ${STATUS_COLOR[t.status] ?? ""}`}
              >
                {t.status}
              </span>
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              <span
                className={`mr-1 rounded-chip px-1.5 py-0.5 text-[11px] ${PRIORITY_COLOR[t.priority] ?? ""}`}
              >
                {t.priority}
              </span>
              <span className="font-mono">{t.task_type}</span>
            </p>
            <p className="mt-1 text-xs text-ink-faint">
              {t.staff?.full_name ?? t.staff?.short_name ?? "—"}
              {" · "}SLA {t.sla_hours}h{" · "}
              <span className="font-mono">
                {t.created_at.slice(0, 16).replace("T", " ")}
              </span>
            </p>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="rounded-card border border-line bg-surface px-4 py-6 text-center text-sm text-ink-faint">
            Chưa có task.
          </li>
        )}
      </ul>

      {/* Desktop: table (≥md). */}
      <div className="hidden overflow-x-auto rounded-card border border-line bg-surface md:block">
        <table className="min-w-full divide-y divide-line text-sm">
          <thead className="bg-surface-muted text-left text-xs uppercase text-ink-muted">
            <tr>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Priority</th>
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Assigned</th>
              <th className="px-3 py-2">SLA (h)</th>
              <th className="px-3 py-2">Tạo lúc</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((t) => (
              <tr key={t.task_id}>
                <td className="px-3 py-2 font-mono text-xs">{t.task_type}</td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-chip px-2 py-0.5 text-xs ${STATUS_COLOR[t.status] ?? ""}`}
                  >
                    {t.status}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-chip px-2 py-0.5 text-xs ${PRIORITY_COLOR[t.priority] ?? ""}`}
                  >
                    {t.priority}
                  </span>
                </td>
                <td className="px-3 py-2">{t.title}</td>
                <td className="px-3 py-2">
                  {t.staff?.full_name ?? t.staff?.short_name ?? "—"}
                </td>
                <td className="px-3 py-2 font-mono text-xs">{t.sla_hours}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {t.created_at.slice(0, 16).replace("T", " ")}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-ink-faint">
                  Chưa có task.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
