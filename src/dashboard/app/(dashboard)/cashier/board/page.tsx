/**
 * Bàn thu ngân — đối soát, thanh toán, đóng lượt.
 *
 * The workspace contains reconciliation, payment and close-out nodes so the
 * KPI row can show their live state. The board itself deliberately receives
 * LUOTKHAM-13 only: one visit must not appear three times in a reconciliation
 * list just because it has three downstream work items.
 */

import { CircleCheck, Clock3, Hand, TriangleAlert } from "lucide-react";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import { fetchWorklist } from "@/lib/worklist-server";

import CashierBoard from "./CashierBoard";

export const metadata = { title: "Bàn thu ngân · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function CashierBoardPage() {
  const result = await fetchWorklist("thu_ngan_dong_luot");
  const today = new Date().toLocaleDateString("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Đối soát chi phí</h1>
          <p className="text-sm text-ink-muted">
            So khớp dịch vụ đã thực hiện, thuốc thực cấp và các nghĩa vụ trước khi đóng lượt.
          </p>
        </div>
        <span className="rounded-control border border-line bg-surface px-3 py-1.5 text-sm text-ink-soft">
          {today}
        </span>
      </header>

      {!result.ok ? (
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">Không tải được bàn thu ngân</p>
          <p className="mt-1 text-sm text-danger">
            {result.reason === "no-session"
              ? "Phiên đăng nhập đã hết hạn."
              : "Không kết nối được máy chủ. ĐỪNG coi đây là không có ai chờ thu."}
          </p>
        </div>
      ) : (
        <>
          <StatRow>
            <StatCard
              label="Chờ đối soát"
              value={result.items.filter(
                (item) => item.node_code === "LUOTKHAM-13" && item.status !== "COMPLETED",
              ).length}
              icon={<Clock3 className="size-5" />}
              tone="warning"
            />
            <StatCard
              label="Có sai lệch · chưa có nguồn"
              value="—"
              icon={<TriangleAlert className="size-5" />}
              tone="danger"
            />
            <StatCard
              label="Đã cân bằng · chưa có nguồn"
              value="—"
              icon={<CircleCheck className="size-5" />}
              tone="success"
            />
            <StatCard
              label="Chặn đóng lượt"
              value={result.items.filter(
                (item) => item.node_code === "LUOTKHAM-15" && item.blocked,
              ).length}
              icon={<Hand className="size-5" />}
              tone="danger"
            />
          </StatRow>
          <CashierBoard
            items={result.items
              .filter((item) => item.node_code === "LUOTKHAM-13")
              .sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""))}
          />
        </>
      )}
    </main>
  );
}
