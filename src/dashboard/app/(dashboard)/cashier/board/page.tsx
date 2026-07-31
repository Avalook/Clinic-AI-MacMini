/**
 * Bàn thu ngân — đối soát, thanh toán, đóng lượt.
 *
 * Same worklist endpoint as reception and the doctor, workspace
 * thu_ngan_dong_luot. Third board, still no second query.
 */

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
    <main className="page-in flex flex-col gap-5 p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Bàn thu ngân</h1>
          <p className="text-sm text-ink-muted">
            Đối soát dịch vụ đã thực hiện, thanh toán và đóng lượt khám.
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
              value={result.items.filter((i) => i.node_code === "LUOTKHAM-13").length}
              tone="brand"
            />
            <StatCard
              label="Chờ thanh toán"
              value={result.items.filter((i) => i.node_code === "LUOTKHAM-14").length}
              tone="neutral"
            />
            <StatCard
              label="Chờ đóng lượt"
              value={result.items.filter((i) => i.node_code === "LUOTKHAM-15").length}
              tone="neutral"
            />
            <StatCard
              label="Bị chặn"
              value={result.items.filter((i) => i.blocked).length}
              tone="warning"
            />
          </StatRow>
          <CashierBoard
            items={[...result.items].sort((a, b) =>
              (a.node_code + (a.created_at ?? "")).localeCompare(
                b.node_code + (b.created_at ?? ""),
              ),
            )}
          />
        </>
      )}
    </main>
  );
}
