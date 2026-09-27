"use client";

// Ô chữ TỰ DO của bác sĩ tư vấn (Tuyền 24/09/2026).
//
// "Chỗ bác sĩ tư vấn chỉ cần 1 ô vuông to để điền tự do — không phải dùng form
// của bác sĩ chính, để còn đồng bộ sang 'Dữ liệu mang sang từ phần khám/tư vấn
// ban đầu' của bác sĩ chính." Trước đó bàn tư vấn ghi vào chính phiếu khám v5.
//
// Y HỆT bản giao diện mẫu `manTuVan` (Tuyền duyệt, làm 27/09/2026 — mục 8): thẻ
// khách + thẻ sinh hiệu DÙNG CHUNG với phiếu bác sĩ chính (`TheKhach`), rồi khối
// "✎ Bác sĩ tư vấn · tự lưu" với một ô chữ to (`OTuVanTuLuu` — cùng ô bác sĩ
// chính sửa tiếp ở khối 1 phiếu của mình). Tự lưu → lệnh `noi-dung-tu-van`; máy
// chủ giữ mọi bản đã lưu. Nút "Xong tư vấn" đợi ô này lưu xong — báo qua
// `onTrangThai` giống phiếu khám.

import { useEffect, useState } from "react";

import type { ClinicalCompletionGate } from "@/lib/clinical-completion";
import type { DauPhieu } from "@/lib/phieu-kham";

import OTuVanTuLuu from "../_lam-viec/phieu-kham/OTuVanTuLuu";
import { TheKhach, TheSinhHieu } from "../_lam-viec/phieu-kham/TheKhach";
import TieuDeKhoi from "../_lam-viec/phieu-kham/TieuDeKhoi";

export default function ONhapTuVan({
  visitId,
  consultationId,
  choGhi,
  onTrangThai,
}: {
  visitId: string;
  /** Phiên TƯ VẤN (ref_id của dòng hàng chờ tư vấn). */
  consultationId: string;
  choGhi: boolean;
  onTrangThai: (g: ClinicalCompletionGate) => void;
}) {
  const [dau, setDau] = useState<DauPhieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  // Đầu phiếu (thẻ khách + sinh hiệu) + bản đang có của ĐÚNG phiên tư vấn này.
  useEffect(() => {
    let bo = false;
    fetch(`/api/phieu-kham?visit_id=${visitId}&xem=dau-phieu`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: DauPhieu | null) => {
        if (bo) return;
        setDau(d);
        if (!d) setLoi("Không đọc được nội dung đã ghi — tải lại trang.");
      })
      .catch(() => {
        if (!bo) setLoi("Mất kết nối — không đọc được nội dung đã ghi.");
      });
    return () => {
      bo = true;
    };
  }, [visitId, consultationId]);

  // Chưa có ô thì chưa "sẵn sàng" — ô đã vẽ thì chính nó báo trạng thái lưu.
  useEffect(() => {
    if (dau) return;
    onTrangThai({
      ok: false,
      code: loi ? "UNSAVED_CHANGES" : "FORM_NOT_READY",
      message: loi ?? "Đang tải nội dung tư vấn…",
    });
  }, [dau, loi, onTrangThai]);

  if (!dau) {
    return loi ? (
      <p role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-meta text-danger">
        {loi}
      </p>
    ) : (
      <p className="text-body text-ink-muted">Đang tải…</p>
    );
  }

  const phien = (dau.phien_tu_van ?? []).find((p) => p.consultation_id === consultationId);
  const cu = dau.tu_van.filter((g) => g.consultation_id === consultationId);
  const banDau = phien ? phien.noi_dung : cu.length ? cu[cu.length - 1]!.noi_dung : "";

  return (
    <div className="space-y-4">
      <TheKhach dau={dau} />
      <TheSinhHieu dau={dau} />
      <TieuDeKhoi so="✎" ten="Bác sĩ tư vấn" phu="tự lưu" phuLuonHien />
      <section className="rounded-card border border-hairline bg-surface p-4">
        <OTuVanTuLuu
          key={consultationId}
          consultationId={consultationId}
          banDau={banDau}
          choGhi={choGhi}
          onTrangThai={onTrangThai}
          to
          nhan="Nội dung tư vấn — bác sĩ chính thấy ở khối Thông tin cơ bản"
          placeholder="Hỏi bệnh, ghi tự do…"
        />
      </section>
    </div>
  );
}
