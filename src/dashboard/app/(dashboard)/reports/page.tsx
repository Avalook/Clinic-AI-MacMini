// Báo cáo vận hành (admin-only, defense-in-depth gate giữ nguyên).
// KPI thật đọc qua backend (/reports/*): hôm nay / ngày mai / theo bác sĩ / 30 ngày /
// 7 ngày gần nhất / nguồn đặt lịch. Read-only, KHÔNG hiển thị CCCD.

import StatCard from "../StatCard";
import Link from "next/link";
import { Fragment } from "react";
import { buttonClass } from "@/components/ui/Button";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import { requireNavAccess } from "../../../lib/clinic-session";
import { fmtDate, VN_TZ } from "../../../lib/datetime";
import PrintReportButton from "./PrintReportButton";
import CuoiNgay from "./CuoiNgay";

export const dynamic = "force-dynamic";

function pct(n: number, total: number): string {
  if (total <= 0) return "—";
  return `${Math.round((n / total) * 100)}%`;
}

// Hai tab (29/09/2026): Vận hành (các ô đếm cũ) · Cuối ngày (tài chính kiểu
// KiotViet — `CuoiNgay.tsx` → `/api/reports/cuoi-ngay`). Cùng cửa `report.view`.
const TAB = [
  { ma: "van-hanh", ten: "Vận hành" },
  { ma: "cuoi-ngay", ten: "Cuối ngày" },
] as const;
type MaTab = (typeof TAB)[number]["ma"];

// Khi in / lưu PDF: ẩn thanh bên, thanh tab, nút bấm.
const IN_CSS = `
  @media print {
    [data-sidebar], nav, aside, [class*="sidebar"],
    #print-report-btn { display: none !important; }
    body { background: var(--color-surface) !important; }
    .space-y-6 > * { page-break-inside: avoid; }
  }
`;

function ThanhTabBaoCao({ dangMo }: { dangMo: MaTab }) {
  return (
    <nav aria-label="Báo cáo" className="flex flex-wrap gap-2">
      {TAB.map((t) => (
        <Link
          key={t.ma}
          href={t.ma === "van-hanh" ? "/reports" : `/reports?tab=${t.ma}`}
          aria-current={t.ma === dangMo ? "page" : undefined}
          className={buttonClass(t.ma === dangMo ? "primary" : "ghost", "sm")}
        >
          {t.ten}
        </Link>
      ))}
    </nav>
  );
}

export default async function ReportsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  // Cửa theo LEGO Báo cáo (27/09/2026) — trước gác vai isOpsAdmin, nên cấp
  // lego cho người khác vai thì mục hiện trên thanh bên mà bấm vào bị đá về.
  await requireNavAccess("/reports");
  const { tab } = await searchParams;
  // Tham số lạ (gõ tay, link hỏng) thì về tab đầu, không ném.
  const dangMo: MaTab = TAB.some((t) => t.ma === tab) ? (tab as MaTab) : "van-hanh";
  if (dangMo === "cuoi-ngay") {
    return (
      <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
        <style>{IN_CSS}</style>
        <ThanhTabBaoCao dangMo={dangMo} />
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">Báo cáo cuối ngày</h1>
        <CuoiNgay />
      </main>
    );
  }

  // 24/09/2026: mọi ô đếm đọc qua backend MỘT lượt (`/reports/tong-quan`) —
  // trang từng bắn 12 truy vấn Supabase rời ở 12 thời điểm khác nhau.
  const tq = await fetchFromBackend<{
    hom_nay: number;
    hom_nay_xong: number;
    hom_nay_cho: number;
    hom_nay_chua_xn: number;
    hom_nay_khong_den: number;
    ngay_mai: number;
    ngay_mai_xn: number;
    xong_30: number;
    khong_den_30: number;
    khach_moi_30: number;
    theo_bac_si: { name: string; total: number; done: number; waiting: number }[];
    theo_ngay: { ngay: string; count: number }[];
  }>(`/api/v1/reports/tong-quan`);

  // ---- Khối 1 + 2 ----
  const todayTotal = tq?.hom_nay ?? 0;
  const tmrTotal = tq?.ngay_mai ?? 0;
  const tmrConfirmed = tq?.ngay_mai_xn ?? 0;

  // ---- Khối 3: theo bác sĩ (backend đã gom) ----
  const doctorStats = tq?.theo_bac_si ?? [];

  // ---- Khối 4: 30 ngày ----
  const done30 = tq?.xong_30 ?? 0;
  const noShow30 = tq?.khong_den_30 ?? 0;

  // ---- Khối 5: đếm lịch hẹn từng ngày (7 ngày gần nhất, theo ngày VN) ----
  const dayBuckets = (tq?.theo_ngay ?? []).map((b) => ({
    // Giữa ngày VN, an toàn khi format.
    label: new Date(`${b.ngay}T12:00:00+07:00`).toLocaleDateString("vi-VN", {
      timeZone: VN_TZ,
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
    }),
    count: b.count,
  }));
  const maxDay = Math.max(1, ...dayBuckets.map((b) => b.count));

  // ---- Khối 6: nguồn đặt lịch 30 ngày ----
  //
  // MỘT truy vấn, không phải 8. Trước đây chỗ này lấy danh sách kênh (7 dòng)
  // rồi bắn một truy vấn đếm cho TỪNG kênh, cộng một truy vấn nữa cho kênh
  // trống — và số truy vấn lớn dần theo số kênh, nên thêm một kênh Zalo mới là
  // thêm một lượt mạng. GROUP BY trả tất cả trong một lượt.
  //
  // Nó cũng đúng hơn về số liệu: 8 truy vấn rời chạy ở 8 thời điểm khác nhau
  // nên tổng các phần có thể không bằng tổng.
  //
  // Và "ngoài danh mục" nay là con số ĐỌC ĐƯỢC chứ không phải phần dư suy ra.
  // Trên prod đang có 1 lịch khai kênh "Zalo" trong khi danh mục ghi "ZALO_PK"
  // — cách cũ nhét nó vào ô "Khác" nên không ai biết là gõ sai chính tả.
  const chan = await fetchFromBackend<{
    items: { code: string; name: string; count: number }[];
    unset: number;
    unknown: number;
  }>(`/api/v1/reports/booking-channels?days=30`);
  // KPI ĐẶT LỊCH THEO NHÂN VIÊN. Đọc qua backend: "ai đặt lịch này" chỉ trả lời
  // được từ sổ sự kiện (`appointment` không có cột người tạo), và đó là một phép
  // gộp — kéo cả sổ về trình duyệt để đếm là sai chỗ.
  const kpi = await fetchFromBackend<{
    items: {
      ten: string;
      bo_phan: string | null;
      ngay: { tong: number; tai_kham: number; kham_moi: number };
      tuan: { tong: number; tai_kham: number; kham_moi: number };
      thang: { tong: number; tai_kham: number; kham_moi: number };
    }[];
  }>(`/api/v1/reports/kpi-dat-lich`);
  const kpiRows = kpi?.items ?? [];

  const channelStats = (chan?.items ?? [])
    .filter((c) => c.count > 0)
    .map((c) => ({ name: c.name, count: c.count }));
  const nullChannel = chan?.unset ?? 0;
  const otherChannel = chan?.unknown ?? 0;
  const maxChannel = Math.max(
    1,
    ...channelStats.map((c) => c.count),
    nullChannel,
    otherChannel,
  );

  // Số đếm nguồn đặt lịch nay do FastAPI trả; `chan === null` nghĩa là backend
  // không trả lời — cũng là một lỗi đọc, phải hiện ra như các lỗi kia.
  const queryError =
    (tq ? null : { message: "Không đọc được số liệu báo cáo từ máy chủ." }) ??
    (chan ? null : { message: "Không đọc được nguồn đặt lịch từ máy chủ." });

  return (
    <main className="page-in min-w-0 space-y-6 p-4 lg:p-5">
      {/* Print CSS: khi in / lưu PDF ẩn sidebar, nav, nút bấm */}
      <style>{IN_CSS}</style>
      <ThanhTabBaoCao dangMo={dangMo} />

      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">Báo cáo vận hành</h1>
          <p className="mt-1 text-sm text-ink-muted">
            KPI vận hành phòng khám · {fmtDate(new Date())} · chỉ đọc
          </p>
        </div>
        <PrintReportButton />
      </header>

      {queryError && (
        <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
          {queryError.message}
        </div>
      )}

      {/* Khối 1 — Hôm nay */}
      <Section title="Hôm nay">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Tổng lịch hẹn" value={todayTotal} />
          <StatCard label="Đã khám xong" value={tq?.hom_nay_xong ?? 0} />
          <StatCard label="Đang chờ" value={tq?.hom_nay_cho ?? 0} />
          {/* Ô này đếm status = SCHEDULED, mà từ 04/08/2026 lịch mới vào
              thẳng CONFIRMED — vòng gọi-xác-nhận đã bỏ. Nên nó chỉ còn đếm
              LỊCH CŨ đặt trước ngày đó, và sẽ về 0 khi đám cũ khám xong.
              Giữ ô lại nhưng gọi đúng tên: để nguyên nhãn "Chưa xác nhận" thì
              một số 0 vĩnh viễn trông như "mọi thứ đều ổn" chứ không như
              "phép đếm này đã hết ý nghĩa". */}
          <StatCard
            label="Lịch cũ chờ xác nhận"
            value={tq?.hom_nay_chua_xn ?? 0}
          />
          <StatCard label="Không đến" value={tq?.hom_nay_khong_den ?? 0} />
        </div>
      </Section>

      {/* Khối 2 — Ngày mai: CSKH đã gọi xác nhận đủ chưa */}
      <Section title="Ngày mai">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard label="Tổng lịch hẹn" value={tmrTotal} />
          <StatCard
            label="Đã xác nhận (CSKH gọi)"
            value={`${tmrConfirmed}/${tmrTotal}`}
          />
          <StatCard
            label="Tỷ lệ xác nhận"
            value={pct(tmrConfirmed, tmrTotal)}
          />
        </div>
      </Section>

      {/* Khối 3 — Theo bác sĩ (hôm nay) */}
      <Section title="Theo bác sĩ (hôm nay)">
        <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-line bg-surface-muted text-left text-xs text-ink-muted">
                <th className="px-4 py-2 font-medium">Bác sĩ</th>
                <th className="px-4 py-2 text-right font-medium">Số ca</th>
                <th className="px-4 py-2 text-right font-medium">
                  Đã khám xong
                </th>
                <th className="px-4 py-2 text-right font-medium">Đang chờ</th>
              </tr>
            </thead>
            <tbody>
              {doctorStats.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-6 text-center text-ink-muted"
                  >
                    Hôm nay chưa có lịch hẹn.
                  </td>
                </tr>
              ) : (
                doctorStats.map((d) => (
                  <tr
                    key={d.name}
                    className="border-b border-surface-sunken last:border-b-0"
                  >
                    <td className="px-4 py-2 text-ink">{d.name}</td>
                    <td className="px-4 py-2 text-right text-ink">
                      {d.total}
                    </td>
                    <td className="px-4 py-2 text-right text-ink">
                      {d.done}
                    </td>
                    <td className="px-4 py-2 text-right text-ink">
                      {d.waiting}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Khối 3b — KPI đặt lịch theo nhân viên.
          Tuyền 14/08/2026: *"cho hiện theo nhân viên, mỗi nhân viên sẽ đạt được
          bao nhiêu đặt lịch khám trong 1 ngày/tuần/tháng, và phân theo bao nhiêu
          lịch tái khám và lịch khám mới"*. Đặt ngay dưới bảng bác sĩ, vì hai
          bảng trả lời hai nửa của cùng một câu: ai KHÁM và ai ĐƯA KHÁCH TỚI. */}
      <Section title="Đặt lịch theo nhân viên">
        <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-line bg-surface-muted text-left text-xs text-ink-muted">
                <th className="px-4 py-2 font-medium" rowSpan={2}>
                  Nhân viên
                </th>
                <th className="border-l border-line px-4 py-2 text-center font-medium" colSpan={3}>
                  Hôm nay
                </th>
                <th className="border-l border-line px-4 py-2 text-center font-medium" colSpan={3}>
                  Tuần này
                </th>
                <th className="border-l border-line px-4 py-2 text-center font-medium" colSpan={3}>
                  Tháng này
                </th>
              </tr>
              <tr className="border-b border-line bg-surface-muted text-left text-label text-ink-faint">
                {["Hôm nay", "Tuần này", "Tháng này"].map((ky) => (
                  <Fragment key={ky}>
                    <th className="border-l border-line px-3 py-1.5 text-right font-medium">
                      Tổng
                    </th>
                    <th className="px-3 py-1.5 text-right font-medium">Mới</th>
                    <th className="px-3 py-1.5 text-right font-medium">Tái khám</th>
                  </Fragment>
                ))}
              </tr>
            </thead>
            <tbody>
              {kpiRows.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-6 text-center text-ink-muted">
                    Tháng này chưa ai đặt lịch.
                  </td>
                </tr>
              ) : (
                kpiRows.map((n) => (
                  <tr
                    key={n.ten}
                    className="border-b border-surface-sunken last:border-b-0"
                  >
                    <td className="px-4 py-2 text-ink">
                      {n.ten}
                      {n.bo_phan ? (
                        <span className="ml-1.5 text-xs text-ink-muted">
                          {n.bo_phan}
                        </span>
                      ) : null}
                    </td>
                    {[n.ngay, n.tuan, n.thang].map((k, i) => (
                      <Fragment key={i}>
                        <td className="border-l border-line px-3 py-2 text-right font-semibold text-ink tabular-nums">
                          {k.tong}
                        </td>
                        <td className="px-3 py-2 text-right text-ink-muted tabular-nums">
                          {k.kham_moi}
                        </td>
                        <td className="px-3 py-2 text-right text-ink-muted tabular-nums">
                          {k.tai_kham}
                        </td>
                      </Fragment>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-ink-muted">
          Đếm theo người BẤM NÚT ĐẶT LỊCH, đọc từ sổ thao tác. Lịch đặt trước khi
          sổ ghi người thực hiện sẽ nằm ở dòng “không rõ người đặt”. Tuần tính từ
          thứ Hai. “Tái khám” là lịch nối vào một lượt khám trước — khách cũ đặt
          một dịch vụ mới vẫn tính là khám mới.
        </p>
      </Section>

      {/* Khối 4 — 30 ngày */}
      <Section title="30 ngày qua">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Lượt khám xong" value={done30} />
          <StatCard label="Không đến (no-show)" value={noShow30} />
          <StatCard
            label="Tỷ lệ no-show"
            value={pct(noShow30, done30 + noShow30)}
          />
          <StatCard
            label="Bệnh nhân mới"
            value={tq?.khach_moi_30 ?? 0}
          />
        </div>
      </Section>

      {/* Khối 5 — 7 ngày gần nhất: bar CSS thuần */}
      <Section title="Lịch hẹn 7 ngày gần nhất">
        <div className="rounded-card border border-line bg-surface p-5 shadow-card">
          <div className="space-y-2">
            {dayBuckets.map((b) => (
              <div key={b.label} className="flex items-center gap-3 text-sm">
                <span className="w-24 shrink-0 text-xs text-ink-muted">
                  {b.label}
                </span>
                <div className="h-4 flex-1 rounded bg-surface-sunken">
                  <div
                    className="h-4 rounded bg-ink"
                    style={{ width: `${(b.count / maxDay) * 100}%` }}
                  />
                </div>
                <span className="w-8 shrink-0 text-right text-ink">
                  {b.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* Khối 6 — Nguồn đặt lịch (booking_channel, 30 ngày) */}
      <Section title="Nguồn đặt lịch (30 ngày)">
        <div className="rounded-card border border-line bg-surface p-5 shadow-card">
          {channelStats.length === 0 && nullChannel === 0 && otherChannel === 0 ? (
            <p className="text-sm text-ink-muted">
              Chưa có lịch hẹn trong 30 ngày qua.
            </p>
          ) : (
            <div className="space-y-2">
              {[
                ...channelStats,
                ...(otherChannel > 0
                  ? [{ name: "Kênh khác", count: otherChannel }]
                  : []),
                ...(nullChannel > 0
                  ? [{ name: "Không ghi nhận", count: nullChannel }]
                  : []),
              ].map((c) => (
                <div key={c.name} className="flex items-center gap-3 text-sm">
                  <span className="w-44 shrink-0 truncate text-xs text-ink-muted">
                    {c.name}
                  </span>
                  <div className="h-4 flex-1 rounded bg-surface-sunken">
                    <div
                      className="h-4 rounded bg-ink"
                      style={{ width: `${(c.count / maxChannel) * 100}%` }}
                    />
                  </div>
                  <span className="w-8 shrink-0 text-right text-ink">
                    {c.count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Section>

      <p className="text-xs text-ink-muted">
        Doanh thu: xem tab “Cuối ngày”.
      </p>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
      <h2 className="font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}
