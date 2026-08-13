"use client";

// Hàng chờ xếp bác sĩ — mỗi dòng là một lịch khách đã hẹn nhưng chưa có người khám.
//
// Việc của quản lý ở màn này là DUY NHẤT: chọn bác sĩ rồi bấm xếp. Không đổi
// giờ, không huỷ — hai việc ấy đã có màn riêng và cần lý do riêng.

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CalendarClock, UserPlus, TriangleAlert } from "lucide-react";
import { fmtDateTimeOrDate, VN_OFFSET } from "../../../../lib/datetime";

export interface DongCho {
  id: string;
  slot_start: string;
  slot_end: string;
  clinic_patient_id: string | null;
  status: string;
  notes: string | null;
  benh_nhan: string | null;
  patient_code: string | null;
  phone_primary: string | null;
  dich_vu: string | null;
  tuan_da_chot: boolean;
  /** Vì sao dòng này nằm ở hàng chờ. Xem ghi chú ở khối vẽ nhãn bên dưới. */
  ly_do?: "CHUA_XEP" | "MAT_BAC_SI";
  /** Bác sĩ vừa rời khỏi lịch — chỉ có với `MAT_BAC_SI`. */
  bac_si_cu?: string | null;
}

export interface BacSi {
  id: string;
  label: string;
}

export default function HangChoView({
  rows,
  doctors,
}: {
  rows: DongCho[];
  doctors: BacSi[];
}) {
  const router = useRouter();
  const [chon, setChon] = useState<Record<string, string>>({});
  // Giờ quản lý muốn xếp. Rỗng = giữ nguyên giờ CSKH đã đặt.
  const [gio, setGio] = useState<Record<string, string>>({});
  const [dangXep, setDangXep] = useState<string | null>(null);
  const [loi, setLoi] = useState<Record<string, string>>({});
  const [xongRoi, setXongRoi] = useState<Record<string, string>>({});

  async function xep(r: DongCho) {
    const id = r.id;
    const bacSi = chon[id];
    if (!bacSi) {
      setLoi((c) => ({ ...c, [id]: "Chọn bác sĩ trước." }));
      return;
    }
    setDangXep(id);
    setLoi((c) => ({ ...c, [id]: "" }));

    // GIỜ MỚI (nếu quản lý đổi). Dùng chính độ dài khung của lịch cũ để không
    // tự bịa ra một độ dài khác với luật phòng khám.
    const gioMoi = gio[id] ?? "";
    const doiGio = Boolean(gioMoi) && gioMoi !== gioCuaLich(r);
    const body: Record<string, unknown> = doiGio
      ? {
          id,
          // MỘT lời gọi cho cả hai việc: `reschedule` nhận luôn doctor_id, nên
          // không có khoảnh khắc lịch đã đổi giờ mà chưa có bác sĩ.
          action: "reschedule",
          doctor_id: bacSi,
          slot_start: ghepGio(r.slot_start, gioMoi),
          slot_end: ghepGio(
            r.slot_start,
            gioMoi,
            new Date(r.slot_end).getTime() - new Date(r.slot_start).getTime(),
          ),
        }
      : { id, action: "assign_doctor", doctor_id: bacSi };

    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setDangXep(null);
    if (!res.ok) {
      const chiTiet = await res
        .json()
        .then((d: { error?: string }) => d.error)
        .catch(() => null);
      // Câu hay gặp nhất ở đây là "Khung giờ đã đầy" — trần số chỗ áp đúng lúc
      // gán người. Hiện nguyên văn để quản lý biết phải chọn bác sĩ khác.
      setLoi((c) => ({
        ...c,
        [id]: chiTiet ?? `Không xếp được (lỗi ${res.status}).`,
      }));
      return;
    }

    // ĐỔI GIỜ THÌ PHẢI ĐỂ LẠI DẤU VẾT CHO CSKH.
    //
    // Khách đã được nghe một giờ; quản lý xếp sang giờ khác thì người gọi lại
    // cho khách phải BIẾT là có chênh lệch, và chênh từ mấy giờ sang mấy giờ.
    // Ghi vào sổ tương tác (`tuong_tac_cskh`) chứ không giữ trong bộ nhớ màn
    // này — màn Quản lý khách hàng đọc chính sổ ấy.
    if (doiGio && r.clinic_patient_id) {
      await fetch("/api/cskh/tuong-tac", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: r.clinic_patient_id,
          appointment_id: id,
          loai: "KHAC",
          kenh: "KHONG_LIEN_HE",
          ket_qua: "BO_QUA",
          trang_thai_ma: "QUAN_LY_DOI_GIO",
          noi_dung: `Quản lý xếp bác sĩ và ĐỔI GIỜ: ${gioCuaLich(r)} → ${gioMoi}. Gọi báo khách trước khi xác nhận lịch.`,
        }),
      }).catch(() => {
        // Ghi sổ hỏng thì lịch vẫn đã đổi đúng. Không chặn quản lý ở đây.
      });
    }

    setXongRoi((c) => ({ ...c, [id]: r.clinic_patient_id ?? "" }));
    router.refresh();
  }

  /** "HH:mm" của lịch, theo giờ Việt Nam. */
  function gioCuaLich(r: DongCho): string {
    return new Date(r.slot_start).toLocaleTimeString("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "Asia/Ho_Chi_Minh",
    });
  }

  /** Giữ NGÀY của lịch cũ, thay GIỜ bằng "HH:mm" quản lý chọn.
   *  `themMs` để dựng giờ kết thúc với đúng độ dài khung cũ. */
  function ghepGio(slotStart: string, hhmm: string, themMs = 0): string {
    const ngay = new Date(slotStart).toLocaleDateString("en-CA", {
      timeZone: "Asia/Ho_Chi_Minh",
    });
    const moc = new Date(`${ngay}T${hhmm}:00${VN_OFFSET}`);
    return new Date(moc.getTime() + themMs).toISOString();
  }

  if (rows.length === 0) {
    return (
      <p className="rounded-card bg-success-bg px-4 py-3 text-sm text-success">
        Không còn lịch nào chờ xếp bác sĩ.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-card bg-surface shadow-card">
      <ul className="divide-y divide-line-soft">
        {rows.map((r) => (
          <li key={r.id} className="grid gap-2 px-4 py-3 lg:grid-cols-[1.4fr_1fr_auto] lg:items-center">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">
                {r.benh_nhan ?? "Chưa có tên"}
                {r.phone_primary && (
                  <span className="ml-2 font-mono text-xs font-normal text-ink-muted">
                    {r.phone_primary}
                  </span>
                )}
              </p>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
                <span className="inline-flex items-center gap-1">
                  <CalendarClock className="size-3.5" aria-hidden="true" />
                  {fmtDateTimeOrDate(r.slot_start)}
                </span>
                <span>{r.dich_vu ?? "Chưa chọn dịch vụ"}</span>
                {r.patient_code && (
                  <span className="font-mono">{r.patient_code}</span>
                )}
              </p>
              {/* HAI LÝ DO NẰM Ở HÀNG CHỜ, và chúng khẩn cấp khác nhau.
                  · CHUA_XEP    — lịch chưa từng xếp ai. Bình thường, xếp là xong.
                  · MAT_BAC_SI  — KHÁCH ĐÃ ĐƯỢC HẸN VỚI MỘT BÁC SĨ CỤ THỂ, rồi bác
                    sĩ ấy mất ca trực. Khách vẫn tưởng lịch của mình còn nguyên.
                    Nếu không ai xếp lại, khách đến quầy mới biết — nên dòng này
                    phải nổi bật hơn, và phải nói RÕ TÊN bác sĩ đã rời đi để quản
                    lý biết còn ai khác cùng cảnh.
                  Thêm 11/08/2026: trước đó màn này chỉ hỏi `doctor_id IS NULL`
                  nên loại thứ hai vô hình hoàn toàn. */}
              {r.ly_do === "MAT_BAC_SI" && (
                <p className="mt-1 inline-flex items-center gap-1 rounded-chip bg-danger-bg px-2 py-0.5 text-[11px] font-medium text-danger">
                  <TriangleAlert className="size-3" aria-hidden="true" />
                  {r.bac_si_cu
                    ? `${r.bac_si_cu} không còn ca trực ngày này — cần xếp lại`
                    : "Bác sĩ đã hẹn không còn ca trực ngày này — cần xếp lại"}
                </p>
              )}
              {/* Xếp bác sĩ cho một tuần chưa chốt là xếp dựa trên bản nháp —
                  lịch trực tuần đó còn đổi được. Nói ra chứ đừng chặn. */}
              {!r.tuan_da_chot && (
                <p className="mt-1 inline-flex items-center gap-1 rounded-chip bg-warning-bg px-2 py-0.5 text-[11px] text-warning">
                  <TriangleAlert className="size-3" aria-hidden="true" />
                  Tuần này chưa áp dụng lịch trực
                </p>
              )}
              {r.notes && (
                <p className="mt-1 line-clamp-2 text-xs text-ink-soft">{r.notes}</p>
              )}
            </div>

            <select
              value={chon[r.id] ?? ""}
              onChange={(e) => setChon((c) => ({ ...c, [r.id]: e.target.value }))}
              className="h-9 w-full rounded-control border border-line bg-surface px-2 text-sm text-ink outline-none focus:border-brand-600"
            >
              <option value="">— Chọn bác sĩ —</option>
              {doctors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.label}
                </option>
              ))}
            </select>

            <div className="flex flex-col items-start gap-1">
              {/* GIỜ KHÁM — quản lý đổi được, không chỉ xếp người.
                  Bỏ trống = giữ nguyên giờ CSKH đã hẹn với khách. */}
              <label className="flex items-center gap-1.5 text-[11px] text-ink-muted">
                Giờ
                <input
                  type="time"
                  value={gio[r.id] ?? gioCuaLich(r)}
                  onChange={(e) =>
                    setGio((c) => ({ ...c, [r.id]: e.target.value }))
                  }
                  className="rounded-control border border-line bg-surface px-1.5 py-1 text-xs text-ink"
                />
              </label>
              {(gio[r.id] ?? gioCuaLich(r)) !== gioCuaLich(r) && (
                <p className="text-[11px] font-medium text-warning">
                  Lệch giờ CSKH hẹn ({gioCuaLich(r)}) — hệ thống sẽ ghi lại để
                  CSKH gọi báo khách.
                </p>
              )}
              <button
                type="button"
                onClick={() => xep(r)}
                disabled={dangXep === r.id}
                className="inline-flex items-center gap-1.5 rounded-control bg-brand-600 px-3 py-2 text-sm font-medium text-surface transition-colors hover:bg-brand-700 disabled:opacity-50"
              >
                <UserPlus className="size-4" aria-hidden="true" />
                {dangXep === r.id ? "Đang xếp…" : "Xếp bác sĩ"}
              </button>
              {xongRoi[r.id] !== undefined && (
                <Link
                  href={
                    xongRoi[r.id]
                      ? `/customers?selected=${encodeURIComponent(xongRoi[r.id])}`
                      : "/customers"
                  }
                  className="inline-flex items-center gap-1.5 rounded-control border border-brand-500 px-3 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-50"
                >
                  Xác nhận lịch trước 7 ngày →
                </Link>
              )}
              {loi[r.id] && (
                <span className="max-w-64 text-xs text-danger">{loi[r.id]}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
