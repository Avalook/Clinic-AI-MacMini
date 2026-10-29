"use client";

// Các lượt khám TRƯỚC của bệnh nhân đang mở — nay chỉ còn dải "đang xem lại"
// và khối phản hồi sau dùng thuốc. Danh sách lượt cũ (+ tóm tắt khi rê chuột)
// đã gộp vào nút [Lịch sử khám] (`_lam-viec/LichSuKham.tsx`, 29/10/2026).
//
// RANH GIỚI QUAN TRỌNG NHẤT: phiếu cũ mở ở chế độ CHỈ XEM.
// Không có ranh giới đó thì bác sĩ gõ vào một phiếu tưởng là hôm nay và ghi
// đè lên bệnh án tháng trước — mà bệnh án đã ký thì luật cấm sửa. Nên khi
// đang xem lại, cả màn đổi màu và nút "Lưu phiếu" biến mất.
//
// Chưa khám lần nào thì component này không hiện gì.
//
// PHẢN HỒI SAU DÙNG THUỐC (10/10/2026): CSKH ghi ở khung khách, gắn lượt có đơn
// → hiện NGAY dưới hàng lượt (không cần rê chuột), chỉ đọc; tự cập nhật khi sổ
// chăm sóc đổi (NOTIFY `tuong_tac_cskh`). Máy chủ trả theo KHÁCH
// (`phan_hoi_thuoc` cạnh `items`), không theo lượt có phiếu — lượt có đơn mà
// chưa ghi phiếu vẫn hiện.

import { useEffect, useState } from "react";
import { History, RotateCcw } from "lucide-react";

import { type NhanLuot } from "../../../../lib/nhan-luot";
import { DongPhanHoiThuoc, type PhanHoiThuoc } from "../../_lam-viec/PhanHoiThuocKhach";
import { useNgheBang } from "../../dung-nghe-bang";

export interface LuotTruoc {
  visit_id: string;
  service_code: string;
  ten_dich_vu: string | null;
  bac_si: string | null;
  kham_luc: string | null;
  visit_status: string;
  form_data: Record<string, unknown>;
  /** Lượt ghi phiếu khám v5 (`phieu_kham_luot`, 29/09/2026): xem lại bằng
   *  phiếu v5 chỉ-xem; `form_data` là {khoá ô: chữ đọc được}, chẩn đoán đầu. */
  phieu_v5?: boolean;
  chan_doan?: string | null;
  /** Nhãn đếm lượt máy chủ tính ("Lượt khám 3", "Buổi 2/10"…). */
  nhan_luot?: NhanLuot | null;
}

function ngay(iso: string | null): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  return Number.isFinite(t) ? new Date(t).toLocaleDateString("vi-VN") : "—";
}

export default function LuotKhamTruoc({
  clinicPatientId,
  dangXem,
  onXem,
}: {
  clinicPatientId: string | null;
  /** Giữ chữ ký cũ cho màn gọi; danh sách lượt đã sang [Lịch sử khám]. */
  visitIdHienTai?: string | null;
  /** Lượt đang xem lại, hoặc null khi đang khám hôm nay. */
  dangXem: LuotTruoc | null;
  onXem: (luot: LuotTruoc | null) => void;
}) {
  const [phanHoiKhach, setPhanHoiKhach] = useState<PhanHoiThuoc[]>([]);
  const [lan, setLan] = useState(0);
  useNgheBang(["tuong_tac_cskh"], () => setLan((n) => n + 1));

  useEffect(() => {
    // Dọn trong nhánh async (setState đồng bộ trong thân effect bị React
    // compiler chặn — kéo theo một lượt render thừa).
    let bo = false;
    if (!clinicPatientId) {
      const t = setTimeout(() => {
        if (!bo) setPhanHoiKhach([]);
      }, 0);
      return () => {
        bo = true;
        clearTimeout(t);
      };
    }
    fetch(`/api/clinical-forms/history?clinic_patient_id=${clinicPatientId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { phan_hoi_thuoc?: PhanHoiThuoc[] } | null) => {
        if (bo || !d) return;
        setPhanHoiKhach(d.phan_hoi_thuoc ?? []);
      })
      .catch(() => {});
    return () => {
      bo = true;
    };
  }, [clinicPatientId, lan]);

  // Không đang xem lại và không có phản hồi thuốc nào thì thôi.
  if (!dangXem && phanHoiKhach.length === 0) return null;

  // Đang xem lại một lượt → chỉ phản hồi của lượt ấy; còn lại → mọi phản hồi.
  const phanHoi = dangXem
    ? phanHoiKhach.filter((p) => p.visit_id === dangXem.visit_id)
    : phanHoiKhach;

  return (
    <div className="relative mt-2">
      {dangXem ? (
        <div className="flex flex-wrap items-center gap-2 rounded-control bg-warning-bg px-3 py-2 text-xs text-warning">
          <History className="size-3.5 shrink-0" aria-hidden="true" />
          <span>
            Đang xem lại lượt khám ngày{" "}
            <strong>{ngay(dangXem.kham_luc)}</strong>
            {dangXem.bac_si ? ` · ${dangXem.bac_si}` : ""} — chỉ xem, không sửa
            được.
          </span>
          <button
            type="button"
            onClick={() => onXem(null)}
            className="ml-auto inline-flex items-center gap-1.5 rounded-control bg-brand-600 px-2.5 py-1 text-xs font-medium text-surface hover:bg-brand-700"
          >
            <RotateCcw className="size-3.5" aria-hidden="true" />
            Quay lại khám tiếp
          </button>
        </div>
      ) : null}
      {/* Dòng chip "Lượt khám trước" (+ tóm tắt khi rê chuột) đã gộp vào nút
          [Lịch sử khám] ở đầu phiếu — bấm là bung danh sách (Tuyền 29/10/2026). */}

      {phanHoi.length ? (
        <div className="mt-2 rounded-control bg-surface-muted px-3 py-2">
          <p className="text-meta font-semibold text-ink">
            Phản hồi sau dùng thuốc (CSKH ghi)
          </p>
          <ul className="mt-1 max-h-48 space-y-2 overflow-y-auto overscroll-contain">
            {phanHoi.map((p) => (
              <li key={p.id}>
                <DongPhanHoiThuoc p={p} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
