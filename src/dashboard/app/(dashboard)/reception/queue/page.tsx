/**
 * Hàng đợi tiếp nhận.
 *
 * The first screen to read the workflow kernel instead of staff_task. The board
 * is whatever the node catalogue puts in the `bang_dieu_phoi` workspace, so a
 * clinic that reorganises its front desk changes a row in node_definition, not
 * this file.
 */

import { CalendarDays, Hourglass, ShieldCheck, UsersRound, Activity } from "lucide-react";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import { waitedMinutes } from "@/lib/worklist";
import { fetchWorklist } from "@/lib/worklist-server";
import { isOverdue } from "@/lib/work-item-status";

import QueueBoard from "./QueueBoard";

export const metadata = { title: "Hàng đợi tiếp nhận · ClinicAI" };

// The queue is the page. Caching it would show the desk a stale room.
export const dynamic = "force-dynamic";

export default async function ReceptionQueuePage() {
  const result = await fetchWorklist("bang_dieu_phoi");

  const now = new Date();
  const today = now.toLocaleDateString("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
  return (
    <main className="page-in flex min-w-0 flex-col gap-3">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Hàng đợi tiếp nhận</h1>
          <p className="mt-0.5 text-sm text-ink-muted">
            Gọi người bệnh và xử lý hàng chờ tại khu vực tiếp nhận.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-ink-soft">
          <span className="flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2">
            <CalendarDays size={16} className="text-brand-600" aria-hidden />
            {today}
          </span>
        </div>
      </header>

      {!result.ok ? (
        /* An outage must not look like an empty waiting room. */
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">
            Không tải được hàng đợi
          </p>
          <p className="mt-1 text-sm text-danger">
            {result.reason === "no-session"
              ? "Phiên đăng nhập đã hết hạn — đăng nhập lại để xem hàng đợi."
              : result.reason === "unreachable"
                ? "Không kết nối được máy chủ. ĐỪNG coi đây là hàng đợi trống — hãy kiểm tra danh sách giấy."
                : "Máy chủ từ chối yêu cầu. ĐỪNG coi đây là hàng đợi trống."}
            {result.detail ? ` (${result.detail})` : ""}
          </p>
        </div>
      ) : (
        <>
          <StatRow>
            <StatCard
              label="Đang chờ tiếp nhận"
              value={result.items.filter((i) => i.status === "PENDING").length}
              tone="brand"
              icon={<UsersRound size={23} />}
            />
            <StatCard
              label="Đang xử lý"
              value={result.items.filter((i) => i.status === "IN_PROGRESS").length}
              tone="neutral"
              icon={<Activity size={23} />}
            />
            <StatCard
              label="Cần xác minh"
              value={result.items.filter((i) => i.node_code === "LUOTKHAM-02").length}
              tone="warning"
              icon={<ShieldCheck size={23} />}
            />
            <StatCard
              label="Quá SLA"
              value={result.items.filter((i) => isOverdue(i)).length}
              tone="danger"
              icon={<Hourglass size={23} />}
            />
          </StatRow>

          {/* Longest wait first among equal priorities — the desk's real order. */}
          <QueueBoard
            items={[...result.items].sort(
              (a, b) => waitedMinutes(b) - waitedMinutes(a),
            )}
          />
        </>
      )}
    </main>
  );
}
