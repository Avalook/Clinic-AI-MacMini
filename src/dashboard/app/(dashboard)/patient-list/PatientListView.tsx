"use client";

// "Danh sách bệnh nhân" — chỉ BN ĐÃ KHÁM (có lịch hẹn COMPLETED). Gom theo BN:
//   • Khám lần đầu = mới khám 1 lần.
//   • Tái khám    = đã khám từ 2 lần trở lên.
// Tìm tên/mã/SĐT + lọc theo phân loại (client-side, data đã nạp sẵn từ server).

import { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fmtDate } from "../../../lib/datetime";
import { unaccentVi } from "../../../lib/validation";
import { TBL_WRAP, TBL_HEAD, TBL_DIV } from "../form-ui";
import ClinicalRecordForm from "../tasks/ClinicalRecordForm";
import type { DoctorApptRow } from "../tasks/DoctorWorkBoard";
import SplitPane from "../SplitPane";
import QuickBookingModal from "./QuickBookingModal";
import type { Option } from "../patients/AppointmentBooking";

export interface ExaminedRow {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  phone_primary: string | null;
  date_of_birth: string | null;
  gender: string | null;
  visit_count: number;
  latest: string;
  phan_loai: "Khám lần đầu" | "Tái khám";
  /** Lượt khám GẦN NHẤT — mở popup hồ sơ lâm sàng (chỉ đọc) khi bấm tên BN. */
  appt: DoctorApptRow;
}

type Filter = "all" | "first" | "return";

function PhanLoai({ value }: { value: ExaminedRow["phan_loai"] }) {
  const first = value === "Khám lần đầu";
  return (
    <span
      className={
        "inline-block rounded-full px-2 py-0.5 text-[11px] font-medium " +
        (first ? "bg-success-bg text-success" : "bg-warning-bg text-warning")
      }
    >
      {value}
    </span>
  );
}

export default function PatientListView({
  rows,
  enablePopup = false,
  canEditAdmin = false,
  showPreVisitBrief = false,
  showRebook = false,
  walkinRebook = false,
  enableVisitPager = false,
  services = [],
  doctors = [],
  locations = [],
}: {
  rows: ExaminedRow[];
  /** Lễ tân + Bác sĩ: bấm tên BN mở hồ sơ (chỉ đọc) trượt sang phải (SplitPane)
   *  thay vì chuyển trang. CSKH/Quản lý = false → giữ điều hướng /patients/[id]
   *  (còn nút đặt lịch ở đó). */
  enablePopup?: boolean;
  /** Cho sửa mục I Hành chính trong popup hồ sơ (Lễ tân + Bác sĩ). */
  canEditAdmin?: boolean;
  /** Hiện nút "Xem tóm tắt trước khám" trong popup — chỉ BÁC SĨ bật từ server. */
  showPreVisitBrief?: boolean;
  /** Hiện nút "Tái khám" trong popup hồ sơ — CSKH + Lễ tân (server bật theo vai). */
  showRebook?: boolean;
  /** Lễ tân: đặt tái khám vào chỗ Ưu tiên (ô xanh, vãng lai) thay vì ô hồng. */
  walkinRebook?: boolean;
  /** Hiện pager ◀ ▶ lượt khám trong phiếu — BÁC SĨ (server bật theo vai). */
  enableVisitPager?: boolean;
  /** Dữ liệu cho MODAL đặt lịch nhanh (chỉ cần truyền khi showRebook). */
  services?: Option[];
  doctors?: Option[];
  locations?: Option[];
}) {
  const router = useRouter();
  const [term, setTerm] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  // BN đang mở trong popup hồ sơ lâm sàng (chỉ đọc). null = đóng.
  const [openAppt, setOpenAppt] = useState<DoctorApptRow | null>(null);
  // BN đang đặt lịch nhanh qua MODAL (bấm "Tái khám"). null = đóng.
  const [bookingAppt, setBookingAppt] = useState<DoctorApptRow | null>(null);

  const shown = useMemo(() => {
    // Tìm KHÔNG phân biệt dấu / hoa-thường + khớp MỘT PHẦN (unaccentVi: "Hoà"/"Hòa"
    // /"HOA" đều ra). Trước dùng toLowerCase → kẹt dấu tiếng Việt (feedback PM).
    const t = unaccentVi(term.trim());
    return rows.filter((r) => {
      if (filter === "first" && r.phan_loai !== "Khám lần đầu") return false;
      if (filter === "return" && r.phan_loai !== "Tái khám") return false;
      if (!t) return true;
      return (
        unaccentVi(r.full_name).includes(t) ||
        unaccentVi(r.patient_code).includes(t) ||
        unaccentVi(r.phone_primary ?? "").includes(t)
      );
    });
  }, [rows, term, filter]);

  const nFirst = rows.filter((r) => r.phan_loai === "Khám lần đầu").length;
  const nReturn = rows.length - nFirst;

  const FILTERS: { key: Filter; label: string }[] = [
    { key: "all", label: `Tất cả (${rows.length})` },
    { key: "first", label: `Khám lần đầu (${nFirst})` },
    { key: "return", label: `Tái khám (${nReturn})` },
  ];

  // Bảng danh sách (cột TRÁI khi mở hồ sơ). Tách ra để đặt vào SplitPane.
  const tableEl = (
    <div className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={
                "rounded-full px-3 py-1 text-xs font-medium transition-colors " +
                (filter === f.key
                  ? "bg-brand-600 text-white"
                  : "border border-brand-100 bg-white text-brand-800 hover:bg-brand-50")
              }
            >
              {f.label}
            </button>
          ))}
        </div>
        <input
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="Tìm tên / mã BN / SĐT…"
          className="min-h-9 w-full rounded-lg border border-line bg-white px-3 text-sm outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-600/15 sm:w-64"
        />
      </div>

      <div className={TBL_WRAP + " max-h-[78vh] overflow-auto"}>
        <table className="w-full border-collapse text-sm">
          <thead className={TBL_HEAD + " sticky top-0 z-10"}>
            <tr>
              <th className="px-3 py-2 text-left">Họ tên</th>
              <th className="px-3 py-2 text-left">Mã BN</th>
              <th className="px-3 py-2 text-left">SĐT</th>
              <th className="px-3 py-2 text-center">Số lần khám</th>
              <th className="px-3 py-2 text-left">Lần gần nhất</th>
              <th className="px-3 py-2 text-left">Phân loại</th>
            </tr>
          </thead>
          <tbody className={TBL_DIV}>
            {shown.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-12 text-center text-ink-faint">
                  Chưa có bệnh nhân đã khám nào.
                </td>
              </tr>
            ) : (
              shown.map((r) => (
                <tr key={r.clinic_patient_id} className="hover:bg-brand-50">
                  <td className="px-3 py-2">
                    {enablePopup ? (
                      // Bật popup hồ sơ lâm sàng (chỉ đọc) — không chuyển trang.
                      <button
                        onClick={() => setOpenAppt(r.appt)}
                        className="text-left font-medium text-status-cancelled hover:underline"
                      >
                        {r.full_name}
                      </button>
                    ) : (
                      <Link
                        href={`/patients/${r.clinic_patient_id}`}
                        className="font-medium text-status-cancelled hover:underline"
                      >
                        {r.full_name}
                      </Link>
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-ink-soft">
                    {r.patient_code}
                  </td>
                  <td className="px-3 py-2 text-ink-soft">
                    {r.phone_primary ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-center font-medium text-ink">
                    {r.visit_count}
                  </td>
                  <td className="px-3 py-2 text-ink-soft">{fmtDate(r.latest)}</td>
                  <td className="px-3 py-2">
                    <PhanLoai value={r.phan_loai} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );

  if (!openAppt) return tableEl;

  // Mở hồ sơ: bảng TRÁI · hồ sơ lâm sàng (CHỈ ĐỌC) trượt sang PHẢI — y hệt
  // "Công việc của tôi" của bác sĩ (cùng SplitPane), KHÔNG phải modal nhảy giữa.
  return (
    <>
      <p className="mb-2 text-[11px] text-brand-300">
        ↔ Kéo thanh hồng ở GIỮA 2 bảng để chỉnh độ rộng (kéo trái: bảng co, hồ
        sơ rộng ra).
      </p>
      <SplitPane
        className="md:h-[78vh]"
        initialLeftPct={52}
        left={tableEl}
        right={
          <ClinicalRecordForm
            key={openAppt.id}
            appt={openAppt}
            staffId={null}
            fill
            readOnly
            canEditAdmin={canEditAdmin}
            showPreVisitBrief={showPreVisitBrief}
            showRebook={showRebook}
            enableVisitPager={enableVisitPager}
            onRebook={() => setBookingAppt(openAppt)}
            onClose={() => setOpenAppt(null)}
          />
        }
      />
      {bookingAppt?.patient && (
        <QuickBookingModal
          patient={bookingAppt.patient}
          services={services}
          doctors={doctors}
          locations={locations}
          walkin={walkinRebook}
          onClose={() => setBookingAppt(null)}
          onBooked={() => {
            setBookingAppt(null);
            router.refresh();
          }}
        />
      )}
    </>
  );
}
