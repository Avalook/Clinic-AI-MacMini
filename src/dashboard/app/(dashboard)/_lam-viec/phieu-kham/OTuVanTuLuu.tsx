"use client";

// Ô CHỮ TƯ VẤN TỰ LƯU — nội dung tư vấn của MỘT phiên tư vấn.
//
// Một ô, hai chỗ dùng (bản giao diện mẫu, Tuyền duyệt 27/09/2026):
//   · Bàn tư vấn — ô to "✎ Bác sĩ tư vấn · tự lưu" (`ban-kham/ONhapTuVan`).
//   · Khối 1 phiếu bác sĩ chính — "Bác sĩ tư vấn ghi … bác sĩ chính sửa tiếp
//     được" (`KhoiDauPhieu.KhoiTuVan`, mục 12).
// Cùng lệnh `noi-dung-tu-van` → máy chủ quyết AI ghi được (khối Tư vấn hoặc quyền
// ghi phiếu khám) và giữ mọi bản đã lưu (lịch sử). Màn không if theo vai.
//
// Tự lưu: dừng gõ ~1 giây hoặc rời ô. Trạng thái lưu báo lên qua `onTrangThai`
// để nút "Xong tư vấn" đợi chữ lưu xong.
//
// Đợt 3 (27/09/2026): ô này là CHUẨN cho mọi màn tự lưu, nay đi chung hàng đợi
// `lib/use-tu-luu` — thêm lưu nốt khi rời màn / đóng tab, lỗi mạng tự thử lại,
// [Lưu ngay] / [Thử lại], và cổng mang `luuNot` (Xong tư vấn tự lưu nốt).

import { useCallback, useEffect, useRef, useState } from "react";

import TrangThaiLuu from "@/components/ui/TrangThaiLuu";
import { congTuLuu, type ClinicalCompletionGate } from "@/lib/clinical-completion";
import { nenThuLai } from "@/lib/tu-luu";
import { useTuLuu } from "@/lib/use-tu-luu";
import { INPUT } from "../../form-ui";
import { guiThaoTac } from "../api";

const CHO_LUU_MS = 1000;

export default function OTuVanTuLuu({
  consultationId,
  banDau,
  choGhi,
  onTrangThai,
  to = false,
  nhan,
  placeholder = "Lý do đến khám, tiền sử, triệu chứng, đã tư vấn gì…",
}: {
  /** Phiên TƯ VẤN (consultation kind TU_VAN). */
  consultationId: string;
  /** Bản mới nhất máy chủ đang giữ. */
  banDau: string;
  /** Người đang mở có chỗ ghi — máy chủ vẫn kiểm lại quyền. */
  choGhi: boolean;
  onTrangThai?: (g: ClinicalCompletionGate) => void;
  /** Ô to của bàn tư vấn (bản mẫu `.ta.big` 240px); nhỏ = 160px. */
  to?: boolean;
  /** aria-label của ô. */
  nhan: string;
  placeholder?: string;
}) {
  const [chu, setChu] = useState(banDau);
  const daLuu = useRef(banDau);
  const chuRef = useRef(banDau);

  const gui = useCallback(async () => {
    const noiDung = chuRef.current;
    if (noiDung === daLuu.current) return { ok: true } as const;
    const kq = await guiThaoTac("noi-dung-tu-van", consultationId, { noi_dung: noiDung });
    if (!kq.ok) {
      return { ok: false, loi: kq.loi, thuLai: nenThuLai(kq.status) } as const;
    }
    daLuu.current = noiDung;
    return { ok: true } as const;
  }, [consultationId]);
  const tuLuu = useTuLuu({ gui, choMs: CHO_LUU_MS, tat: !choGhi });

  useEffect(() => {
    onTrangThai?.(congTuLuu(tuLuu.trangThai, tuLuu.luuNgay, "Nội dung tư vấn"));
  }, [tuLuu.trangThai, tuLuu.luuNgay, onTrangThai]);

  return (
    <div className="space-y-2">
      <textarea
        value={chu}
        aria-label={nhan}
        disabled={!choGhi}
        onChange={(e) => {
          chuRef.current = e.target.value;
          setChu(e.target.value);
          tuLuu.danhDau();
        }}
        onBlur={() => {
          if (tuLuu.trangThai.chua_luu) void tuLuu.luuNgay();
        }}
        placeholder={placeholder}
        className={`${INPUT} resize-y leading-relaxed ${to ? "min-h-60 sm:min-h-60" : "min-h-40 sm:min-h-40"}`}
      />
      {choGhi ? <TrangThaiLuu tt={tuLuu.trangThai} onLuuNgay={() => void tuLuu.luuNgay()} /> : null}
    </div>
  );
}
