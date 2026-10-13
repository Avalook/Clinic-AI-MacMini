"use client";

// Khách đã KHÁM XONG ra bàn tư vấn để điền đơn thuốc (Tuyền 13/10/2026): bác sĩ
// chính ghi thuốc trên tờ phơi / điền dở, bác sĩ tư vấn điền tiếp đúng đơn của
// lượt và in tại bàn. Thẻ khách + sinh hiệu dùng chung với bàn tư vấn; thân là
// khối Đơn thuốc mở sẵn. Không có nút Bắt đầu / Xong — đơn tự lưu, Hoàn tất của
// bác sĩ chính đã chốt phần khám.

import { useEffect, useState } from "react";

import type { ClinicalCompletionGate } from "@/lib/clinical-completion";
import type { DatChiDinh, DauPhieu } from "@/lib/phieu-kham";

import { TheKhach, TheSinhHieu } from "../_lam-viec/phieu-kham/TheKhach";
import KhoiDonThuocBanTuVan from "./KhoiDonThuocBanTuVan";

export default function BanDienDonThuoc({
  visitId,
  clinicPatientId,
  choGhi,
  onTrangThai,
  datChiDinh,
  onDaDat,
}: {
  visitId: string;
  clinicPatientId: string;
  choGhi: boolean;
  onTrangThai: (g: ClinicalCompletionGate) => void;
  datChiDinh: DatChiDinh;
  onDaDat: () => void;
}) {
  const [dau, setDau] = useState<DauPhieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let bo = false;
    fetch(`/api/phieu-kham?visit_id=${visitId}&xem=dau-phieu`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: DauPhieu | null) => {
        if (bo) return;
        setDau(d);
        if (!d) setLoi("Không đọc được hồ sơ khách — tải lại trang.");
      })
      .catch(() => {
        if (!bo) setLoi("Mất kết nối — không đọc được hồ sơ khách.");
      });
    return () => {
      bo = true;
    };
  }, [visitId]);

  return (
    <div className="space-y-4">
      {dau ? (
        <>
          <TheKhach dau={dau} />
          <TheSinhHieu dau={dau} />
        </>
      ) : loi ? (
        <p role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : (
        <p className="text-body text-ink-muted">Đang tải…</p>
      )}
      <KhoiDonThuocBanTuVan
        visitId={visitId}
        clinicPatientId={clinicPatientId}
        choGhi={choGhi}
        moSan
        onTrangThai={onTrangThai}
        datChiDinh={datChiDinh}
        onDaDat={onDaDat}
      />
    </div>
  );
}
