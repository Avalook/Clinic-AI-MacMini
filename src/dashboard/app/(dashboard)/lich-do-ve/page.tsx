// "Lịch đổ về" — Quản lý xem TOÀN BỘ lịch một tuần, kèm thống kê theo khung giờ.
//
// Tuyền 14/08/2026: *"Thêm 1 giao diện (1 nút ở sidebar) trong tài khoản Quản lý
// hệ thống cho phép xem toàn bộ lịch đổ về: cần thống kê số slot theo từng mốc
// khung h và phân ra theo khám mới, khám cũ & dịch vụ"*.
//
// VÌ SAO KHÔNG THÊM VÀO TRANG CHỦ. Bảng lịch tuần ở trang chủ trả lời câu hỏi
// của người TRỰC: hôm nay ai tới, ai cần check-in. Màn này trả lời câu hỏi của
// người QUẢN LÝ: giờ nào đang dồn, dịch vụ nào kéo khách, tỉ lệ khách mới trên
// khách cũ ra sao. Cùng dữ liệu, hai câu hỏi — và nhồi cả hai vào một bảng thì
// bảng ấy phục vụ kém cả hai người.
//
// ĐỌC LẠI ĐÚNG NGUỒN CỦA TRANG CHỦ (`/appointments/week`), không viết truy vấn
// mới: phan_loai và tên dịch vụ đã được backend tính sẵn ở đó, và một bản tính
// thứ hai là một bản chờ ngày lệch với bản đầu.

import { Fragment } from "react";
import { redirect } from "next/navigation";
import Link from "next/link";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import { getClinicRole } from "../../../lib/clinic-session";
import { isOpsAdmin } from "../../../lib/roles";
import { currentWeekStartVn, shiftWeek, weekStartOf, fmtDayMonth, dayLabel } from "../../../lib/roster";
import { thongKeTheoKhungGio, tongKet, khungGioVN, type LichDeDem } from "../../../lib/thong-ke-khung-gio";
import { nhanPhanLoaiKham } from "../../../lib/phan-loai-kham";
import { chipClass } from "../../../components/ui/Chip";
import { VN_TZ } from "../../../lib/datetime";

export const dynamic = "force-dynamic";

interface Dong extends LichDeDem {
  id: string;
  doctor: { full_name: string } | null;
  patient: { full_name: string; patient_code: string } | null;
}

// DESIGN.md §6: chỉ kẻ ngang bằng hairline — cùng khuôn với bảng lịch tuần.
const TH =
  "border-b border-hairline bg-surface-muted px-3 py-2 text-left text-label font-semibold uppercase tracking-wide text-ink-muted";
const TD = "border-b border-hairline px-3 py-2 align-top";

export default async function LichDoVePage({
  searchParams,
}: {
  searchParams: Promise<{ week?: string }>;
}) {
  const role = await getClinicRole();
  // Cùng cửa với màn Báo cáo. Đây là số liệu so sánh cả phòng khám.
  if (!isOpsAdmin(role)) redirect("/home");

  const sp = await searchParams;
  // `weekStartOf` trả null cho chuỗi rác thay vì ném — cùng luật với các hàm
  // nhận ngày từ người dùng (đã ba lần 500 vì luật này bị bỏ qua).
  const week = (sp.week ? weekStartOf(sp.week) : null) ?? currentWeekStartVn();

  // `fetchFromBackend` trả null khi chưa cấu hình backend hoặc phiên hết hạn —
  // coi như "chưa có lịch nào" và vẽ bảng rỗng, thay vì để trang nổ. Bảng rỗng
  // nói đúng sự thật là màn này chưa đọc được gì; một trang lỗi thì không.
  const ket = await fetchFromBackend<{ items: Dong[] }>(
    `/api/v1/appointments/week?week_start=${week}`,
  );
  const items = ket?.items ?? [];

  const dong = thongKeTheoKhungGio(items);
  const tong = tongKet(items);

  // Danh sách chi tiết, gom theo ngày — cùng thứ tự người ta đọc lịch.
  const theoNgay = new Map<string, Dong[]>();
  for (const a of items) {
    const d = new Date(a.slot_start);
    if (Number.isNaN(d.getTime())) continue;
    const ngay = d.toLocaleDateString("en-CA", { timeZone: VN_TZ });
    const arr = theoNgay.get(ngay);
    if (arr) arr.push(a);
    else theoNgay.set(ngay, [a]);
  }
  const ngayXep = [...theoNgay.keys()].sort();

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-brand-800">Lịch đổ về</h1>
          <p className="text-sm text-ink-muted">
            Toàn bộ lịch hẹn của tuần, thống kê theo mốc khung giờ · chỉ đọc
          </p>
        </div>
        <nav className="flex items-center gap-2 text-sm">
          <Link
            href={`/lich-do-ve?week=${shiftWeek(week, -1)}`}
            className="rounded-md border border-line px-2.5 py-1 hover:bg-surface-muted"
          >
            ← Tuần trước
          </Link>
          <span className="font-medium text-ink">Tuần {fmtDayMonth(week)}</span>
          <Link
            href="/lich-do-ve"
            className="text-brand-600 hover:underline"
          >
            tuần này
          </Link>
          <Link
            href={`/lich-do-ve?week=${shiftWeek(week, 1)}`}
            className="rounded-md border border-line px-2.5 py-1 hover:bg-surface-muted"
          >
            Tuần sau →
          </Link>
        </nav>
      </header>

      {/* ── THỐNG KÊ THEO KHUNG GIỜ ─────────────────────────────────────── */}
      <section className="space-y-2">
        <h2 className="text-base font-semibold text-brand-800">
          Số lịch theo mốc khung giờ
        </h2>
        <p className="text-xs text-ink-muted">
          Lịch đã huỷ / không đến / bác sĩ từ chối <strong>không được đếm</strong>{" "}
          — chúng không giữ chỗ của ai, và đếm vào thì khung còn trống bị báo là
          kín.
        </p>
        <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
          <table className="w-full min-w-max border-collapse text-sm">
            <thead>
              <tr>
                <th className={`${TH} min-w-[86px]`}>Khung giờ</th>
                <th className={`${TH} text-right`}>Tổng</th>
                <th className={`${TH} text-right`}>Khám mới</th>
                <th className={`${TH} text-right`}>Khám cũ</th>
                <th className={`${TH} text-right`}>Chưa rõ</th>
                <th className={`${TH} min-w-[260px]`}>Dịch vụ</th>
              </tr>
            </thead>
            <tbody>
              {dong.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-ink-muted" colSpan={6}>
                    Tuần này chưa có lịch nào.
                  </td>
                </tr>
              ) : (
                dong.map((d) => (
                  <tr key={d.khung} className="hover:bg-surface-muted">
                    <td className={`${TD} font-mono font-medium text-ink`}>
                      {d.khung}
                    </td>
                    <td className={`${TD} text-right font-semibold text-ink`}>
                      {d.tong}
                    </td>
                    <td className={`${TD} text-right text-success`}>{d.khamMoi}</td>
                    <td className={`${TD} text-right text-warning`}>{d.khamCu}</td>
                    <td className={`${TD} text-right text-ink-faint`}>
                      {d.chuaRo || "—"}
                    </td>
                    <td className={`${TD} text-xs text-ink-soft`}>
                      {d.dichVu.map((x) => `${x.ten} (${x.so})`).join(" · ")}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
            {dong.length > 0 && (
              <tfoot>
                <tr className="bg-brand-50 font-semibold text-brand-800">
                  <td className={TD}>Tổng</td>
                  <td className={`${TD} text-right`}>{tong.tong}</td>
                  <td className={`${TD} text-right`}>{tong.khamMoi}</td>
                  <td className={`${TD} text-right`}>{tong.khamCu}</td>
                  <td className={`${TD} text-right`}>{tong.chuaRo || "—"}</td>
                  <td className={`${TD} text-xs font-normal`}>
                    {tong.dichVu.map((x) => `${x.ten} (${x.so})`).join(" · ")}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </section>

      {/* ── DANH SÁCH CHI TIẾT ──────────────────────────────────────────── */}
      <section className="space-y-2">
        <h2 className="text-base font-semibold text-brand-800">
          Chi tiết từng lịch
        </h2>
        <div className="max-h-[70vh] overflow-auto rounded-card border border-line bg-surface shadow-card">
          <table className="w-full min-w-max border-collapse text-xs">
            <thead className="sticky top-0 z-10">
              <tr>
                <th className={`${TH} min-w-[86px]`}>Khung giờ</th>
                <th className={`${TH} min-w-[150px]`}>Bác sĩ</th>
                <th className={`${TH} min-w-[190px]`}>Thông tin</th>
                <th className={`${TH} min-w-[130px]`}>Dịch vụ khám</th>
                <th className={`${TH} min-w-[100px]`}>Phân loại khám</th>
              </tr>
            </thead>
            <tbody>
              {ngayXep.length === 0 ? (
                <tr>
                  <td className="px-3 py-6 text-center text-ink-muted" colSpan={5}>
                    Tuần này chưa có lịch nào.
                  </td>
                </tr>
              ) : (
                ngayXep.map((ngay) => {
                  const ds = [...(theoNgay.get(ngay) ?? [])].sort((a, b) =>
                    a.slot_start.localeCompare(b.slot_start),
                  );
                  return (
                    <Fragment key={ngay}>
                      {/* Dòng tiêu đề NGÀY, gộp cả 5 cột — cùng cách bảng lịch
                          tuần ở trang chủ làm, để hai bảng đọc giống nhau. */}
                      <tr className="bg-surface-muted">
                        <td
                          colSpan={5}
                          className="border-b border-hairline border-l-[3px] border-l-brand-600 px-3 py-1.5 text-sm font-semibold text-ink"
                        >
                          {dayLabel(ngay)} · {fmtDayMonth(ngay)}
                          <span className={`ml-2 ${chipClass("neutral")}`}>
                            {ds.length} lịch
                          </span>
                        </td>
                      </tr>
                      {ds.map((a) => (
                        <tr key={a.id} className="hover:bg-surface-muted">
                          <td className={`${TD} whitespace-nowrap font-mono`}>
                            {khungGioVN(a.slot_start)}
                          </td>
                          <td className={TD}>
                            {a.doctor?.full_name ?? (
                              <span className="text-ink-faint">Chưa phân bác sĩ</span>
                            )}
                          </td>
                          <td className={TD}>
                            <span className="block font-medium text-ink">
                              {a.patient?.full_name ?? "—"}
                            </span>
                            <span className="block font-mono text-[10px] text-ink-muted">
                              {a.patient?.patient_code}
                            </span>
                          </td>
                          <td className={`${TD} text-ink-soft`}>
                            {a.service?.name ?? (
                              <span className="text-ink-faint">—</span>
                            )}
                          </td>
                          <td className={TD}>
                            {nhanPhanLoaiKham(a.phan_loai) || (
                              <span className="text-ink-faint">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </Fragment>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
