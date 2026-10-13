"use client";

// ĐƠN THUỐC ở BÀN TƯ VẤN (Tuyền chốt 13/10/2026): bác sĩ chính điền thuốc dở /
// vội, khách ra bàn tư vấn thì bác sĩ tư vấn điền tiếp ĐÚNG đơn của lượt — không
// có "đơn thứ hai". Cùng form mục E của phiếu khám (`PhieuKhamLuot chiMuc=["E"]`),
// tự lưu, sửa / xoá dòng được như ở bàn khám.
//
// Màn chỉ vẽ. Người kê ghi đúng người bấm và quyền lưu do máy chủ quyết
// (`PhieuKhamService.luu_don_thuoc`); đơn in kèm tên người kê.

import { useState } from "react";

import Chip from "@/components/ui/Chip";
import CongTac from "@/components/ui/CongTac";
import { buttonClass } from "@/components/ui/Button";
import type { ClinicalCompletionGate } from "@/lib/clinical-completion";
import type { DatChiDinh } from "@/lib/phieu-kham";

import PhieuKhamLuot from "../_lam-viec/phieu-kham/PhieuKhamLuot";

export default function KhoiDonThuocBanTuVan({
  visitId,
  clinicPatientId,
  choGhi,
  moSan = false,
  onTrangThai,
  datChiDinh,
  onDaDat,
}: {
  visitId: string;
  clinicPatientId: string;
  choGhi: boolean;
  /** Mở sẵn khi khách ra bàn tư vấn CHỈ để điền đơn (đã khám xong). */
  moSan?: boolean;
  onTrangThai: (g: ClinicalCompletionGate) => void;
  datChiDinh: DatChiDinh;
  onDaDat: () => void;
}) {
  const [mo, setMo] = useState(moSan);
  return (
    <section className="overflow-hidden rounded-card border border-hairline bg-surface">
      <div className="flex flex-wrap items-center gap-3 px-4 py-2">
        <CongTac bat={mo} nhan={`Đơn thuốc: ${mo ? "đang mở" : "đang đóng"}`} onDoi={setMo} />
        <div className="min-w-48 flex-1">
          <p className="text-emph font-semibold text-ink">Đơn thuốc</p>
          <p className="text-meta text-ink-muted">
            {mo
              ? "Điền tiếp đơn bác sĩ chính đã ghi · lưu tự động"
              : "Bật để điền / sửa đơn thuốc của khách"}
          </p>
        </div>
        <Chip tone="brand">đơn chung với bác sĩ chính</Chip>
        <a
          href={`/print/phieu-kham/${visitId}?phan=don`}
          target="_blank"
          rel="noopener"
          className={buttonClass("secondary", "md")}
        >
          In đơn thuốc
        </a>
      </div>
      <div className={mo ? "border-t border-hairline p-4" : "hidden"}>
        <PhieuKhamLuot
          key={`e-${visitId}`}
          visitId={visitId}
          clinicPatientId={clinicPatientId}
          choGhi={choGhi}
          chiMuc={["E"]}
          datChiDinh={datChiDinh}
          onDaDat={onDaDat}
          onTrangThai={onTrangThai}
        />
      </div>
    </section>
  );
}
