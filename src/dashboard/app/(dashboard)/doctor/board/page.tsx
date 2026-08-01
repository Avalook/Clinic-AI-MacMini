/**
 * Bàn khám — the doctor's board.
 *
 * Reads the same worklist endpoint as reception with workspace=khu_bac_si. The
 * seven nodes in that workspace come from the clinic's own catalogue, so a
 * clinic that adds a consultation type gets it on the board without a deploy.
 */

import StatCard, { StatRow } from "@/components/ui/StatCard";
import { requireNavAccess } from "@/lib/clinic-session";
import { fetchWorklist } from "@/lib/worklist-server";

import DoctorBoard from "./DoctorBoard";

export const metadata = { title: "Bàn khám · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function DoctorBoardPage() {
  await requireNavAccess("/doctor/board");
  const result = await fetchWorklist("khu_bac_si");

  const today = new Date().toLocaleDateString("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

  return (
    <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-ink">
            Danh sách khám bệnh đang mở
          </h1>
          <p className="text-sm text-ink-muted">
            Khám, ra chỉ định và hoàn tất lượt khám trong một workspace.
          </p>
        </div>
        <span className="rounded-control border border-line bg-surface px-4 py-2 text-sm font-medium text-ink-soft shadow-card">
          {today}
        </span>
      </header>

      {!result.ok ? (
        /* An outage must not look like an empty clinic. */
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">Không tải được bàn khám</p>
          <p className="mt-1 text-sm text-danger">
            {result.reason === "no-session"
              ? "Phiên đăng nhập đã hết hạn — đăng nhập lại."
              : "Không kết nối được máy chủ. ĐỪNG coi đây là bàn khám trống."}
            {result.detail ? ` (${result.detail})` : ""}
          </p>
        </div>
      ) : (
        <>
          <StatRow>
            <StatCard
              label="Chờ khám"
              value={
                result.items.filter((i) => i.status === "PENDING" && !i.blocked).length
              }
              tone="brand"
            />
            <StatCard
              label="Đang khám"
              value={result.items.filter((i) => i.status === "IN_PROGRESS").length}
              tone="neutral"
            />
            <StatCard
              label="Chờ bước trước"
              value={
                result.items.filter((i) => i.status === "PENDING" && i.blocked).length
              }
              tone="warning"
            />
            <StatCard label="Tổng bước đang mở" value={result.items.length} tone="neutral" />
          </StatRow>

          <DoctorBoard
            items={[...result.items].sort(
              (a, b) =>
                new Date(a.created_at ?? 0).getTime() -
                new Date(b.created_at ?? 0).getTime(),
            )}
          />
        </>
      )}
    </main>
  );
}
