"use client";

// BÀN TƯ VẤN — phần thân hồ sơ của `BanKham` chế độ `tu_van` (/tu-van).
//
// Y HỆT bản giao diện mẫu `manTuVan` (M/app.js:701-724, Tuyền duyệt; làm 27/09/2026
// — mục 8 kế hoạch giao diện):
//   1. Thẻ khách + thẻ sinh hiệu dùng chung với phiếu bác sĩ chính.
//   2. Khối "✎ Bác sĩ tư vấn · tự lưu" — MỘT ô chữ to (`ONhapTuVan`).
//   3. Công tắc "Thông tin cơ bản" (mặc định đóng) = mục B của CHÍNH phiếu khám
//      lượt; chip "N ô đã điền" + "đồng bộ bác sĩ chính".
//   4. Thanh DÍNH ĐÁY "[Xong tư vấn — chuyển bác sĩ chính]" (lệnh `xong-tu-van`
//      do `BanKham` dựng). Dưới md có BottomNav cố định cao 64px → dính ở
//      bottom-16 để nút nằm TRÊN thanh điều hướng (cách đã bấm thật ở 375, 27/09).
//
// Màn chỉ vẽ. Ai ghi được, ai bấm Xong được là việc của máy chủ.

import { useCallback, useEffect, useState, type ReactNode } from "react";

import { gopCong, type ClinicalCompletionGate } from "@/lib/clinical-completion";

import CongTacThongTinCoBan from "../_lam-viec/phieu-kham/CongTacThongTinCoBan";
import PhieuKhamLuot from "../_lam-viec/phieu-kham/PhieuKhamLuot";
import type { DatChiDinh } from "@/lib/phieu-kham";
import ONhapTuVan from "./ONhapTuVan";

export default function BanTuVan({
  visitId,
  consultationId,
  clinicPatientId,
  coPhieu,
  choGhi,
  onTrangThai,
  datChiDinh,
  onDaDat,
  nutXong,
}: {
  visitId: string;
  /** Phiên TƯ VẤN (ref_id của dòng hàng chờ tư vấn). */
  consultationId: string;
  clinicPatientId: string;
  /** Loại khám của lượt đã gắn phiếu khám v5 → có mục B để mở. */
  coPhieu: boolean;
  choGhi: boolean;
  onTrangThai: (g: ClinicalCompletionGate) => void;
  datChiDinh: DatChiDinh;
  onDaDat: () => void;
  /** Nút [Xong tư vấn — chuyển bác sĩ chính] + lỗi của nó (null = chưa bắt đầu). */
  nutXong: ReactNode;
}) {
  const [soDien, setSoDien] = useState(0);
  const [tenPhieu, setTenPhieu] = useState<string | undefined>(undefined);
  const baoTomTat = useCallback((n: number, ten: string) => {
    setSoDien(n);
    setTenPhieu(ten);
  }, []);
  // [Xong tư vấn] đợi CẢ ô tư vấn lẫn mục B lưu xong (đợt 3, 27/09/2026) —
  // trước đây mục B không báo cổng, gõ mục B rồi bấm Xong ngay là lỡ chữ.
  const [congTuVan, setCongTuVan] = useState<ClinicalCompletionGate | null>(null);
  const [congPhieu, setCongPhieu] = useState<ClinicalCompletionGate | null>(null);
  useEffect(() => {
    const g = gopCong(congTuVan, congPhieu);
    if (g) onTrangThai(g);
  }, [congTuVan, congPhieu, onTrangThai]);

  return (
    <div className="space-y-4">
      <ONhapTuVan
        visitId={visitId}
        consultationId={consultationId}
        choGhi={choGhi}
        onTrangThai={setCongTuVan}
      />
      {coPhieu ? (
        <CongTacThongTinCoBan tenPhieu={tenPhieu} soDien={soDien}>
          <PhieuKhamLuot
            key={`b-${visitId}`}
            visitId={visitId}
            clinicPatientId={clinicPatientId}
            choGhi={choGhi}
            chiMuc={["B"]}
            datChiDinh={datChiDinh}
            onDaDat={onDaDat}
            onTomTat={baoTomTat}
            onTrangThai={setCongPhieu}
          />
        </CongTacThongTinCoBan>
      ) : null}
      {nutXong ? (
        <div className="sticky bottom-16 z-10 flex flex-wrap items-center justify-end gap-2 rounded-card border border-hairline bg-surface p-4 md:bottom-3">
          <div className="w-full sm:w-auto">{nutXong}</div>
        </div>
      ) : null}
    </div>
  );
}
