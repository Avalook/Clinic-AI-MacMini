"use client";

// Dải đầu phiếu: hành chính + sinh hiệu (CHỈ ĐỌC) + ghi chú bác sĩ tư vấn (bác
// sĩ chính sửa tiếp được từ 27/09/2026 — `KhoiTuVan choSua`).
//
// Nguồn chốt: *"đồng bộ từ Điều dưỡng"*, *"không bắt nhập lại"*. Sinh hiệu sai
// thì sửa ở màn đo sinh hiệu; ở đây không có ô nào để gõ đè. Thứ tự và khoá lấy
// từ `HANH_CHINH.lien_ket.truong` của khung, nhãn lấy từ máy chủ.

import { hienThi, type DauPhieu } from "@/lib/phieu-kham";
import OTuVanTuLuu from "./OTuVanTuLuu";

function gioVn(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export function KhoiHanhChinh({
  dau,
  truong,
}: {
  dau: DauPhieu;
  truong: string[];
}) {
  // Ô của khung phiếu + ô HỒ SƠ đồng bộ từ form khách (Tuyền 24/09/2026:
  // "các thông tin trong này phải thực sự đồng bộ cho hồ sơ khám").
  const hanhChinh = [
    ...truong.filter((k) => !k.startsWith("vitals.")),
    ...(dau.ho_so ?? []).filter((k) => !truong.includes(k)),
  ];
  const sinhHieu = truong.filter((k) => k.startsWith("vitals."));
  return (
    <div className="space-y-2 rounded-card border border-hairline bg-surface-muted p-3">
      <dl className="flex flex-wrap gap-x-6 gap-y-1 text-body">
        {hanhChinh.map((k) => (
          <div key={k} className="flex gap-1">
            <dt className="font-semibold text-ink">{dau.nhan[k] ?? k}:</dt>
            <dd className="text-ink">{hienThi(dau.hanh_chinh[k])}</dd>
          </div>
        ))}
      </dl>
      <dl className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-body">
        <span className="font-semibold text-ink">Sinh hiệu:</span>
        {sinhHieu.map((k) => (
          <div key={k} className="flex gap-1 tabular-nums">
            <dt className="text-ink-muted">{dau.nhan[k] ?? k}</dt>
            <dd className="font-medium text-ink">{hienThi(dau.sinh_hieu[k])}</dd>
          </div>
        ))}
        <span className="text-meta text-ink-faint">
          {dau.sinh_hieu_luc
            ? `đồng bộ từ Điều dưỡng · ${gioVn(dau.sinh_hieu_luc)}`
            : "chưa đo sinh hiệu"}
        </span>
      </dl>
    </div>
  );
}

function DanhSachGhiChu({ ds }: { ds: DauPhieu["tu_van"] }) {
  return (
    <ul className="mt-1 space-y-1">
      {ds.map((g) => (
        <li key={`${g.luc}-${g.noi_dung.slice(0, 16)}`} className="text-body text-ink">
          <span className="mr-2 text-meta text-ink-faint">{gioVn(g.luc)}</span>
          <span className="whitespace-pre-wrap">{g.noi_dung}</span>
        </li>
      ))}
    </ul>
  );
}

/** Mục A — "Bác sĩ tư vấn ghi".
 *
 *  `choSua` (27/09/2026, bản mẫu mục 12 — "bác sĩ chính sửa tiếp được"): mỗi phiên
 *  tư vấn của lượt là một ô tự lưu, CÙNG lệnh với bàn tư vấn; máy chủ quyết ai
 *  ghi được (khối Tư vấn hoặc quyền ghi phiếu khám) và giữ mọi bản cũ. Ghi chú
 *  khám ban đầu đời cũ (phiên khám chính) vẫn chỉ đọc. */
export function KhoiTuVan({ dau, choSua = false }: { dau: DauPhieu; choSua?: boolean }) {
  const phien = dau.phien_tu_van ?? [];
  if (!choSua || phien.length === 0) {
    return (
      <div className="rounded-card border border-hairline bg-surface-muted p-3">
        <p className="text-meta font-semibold text-ink-muted">
          Dữ liệu mang sang từ phần khám/tư vấn ban đầu
        </p>
        {dau.tu_van.length === 0 ? (
          <p className="mt-1 text-body text-ink-faint">—</p>
        ) : (
          <DanhSachGhiChu ds={dau.tu_van} />
        )}
      </div>
    );
  }
  const cuaPhien = new Set(phien.map((p) => p.consultation_id));
  const ghiChuCu = dau.tu_van.filter((g) => !g.consultation_id || !cuaPhien.has(g.consultation_id));
  return (
    <div className="space-y-3">
      {phien.map((p, i) => (
        <div key={p.consultation_id} className="space-y-1">
          {phien.length > 1 ? (
            <p className="text-meta font-semibold text-ink-muted">Phiên tư vấn {i + 1}</p>
          ) : null}
          <OTuVanTuLuu
            consultationId={p.consultation_id}
            banDau={p.noi_dung}
            choGhi
            nhan={`Nội dung bác sĩ tư vấn ghi${phien.length > 1 ? ` — phiên ${i + 1}` : ""}`}
            placeholder="Bác sĩ tư vấn chưa ghi gì — bác sĩ chính ghi bổ sung được."
          />
          {p.luc ? (
            <p className="text-meta text-ink-faint">
              Bản đang có: {gioVn(p.luc)}
              {p.nguoi ? ` · ${p.nguoi}` : ""}
            </p>
          ) : null}
        </div>
      ))}
      {ghiChuCu.length > 0 ? (
        <div className="rounded-card border border-hairline bg-surface-muted p-3">
          <p className="text-meta font-semibold text-ink-muted">Ghi chú khám ban đầu (chỉ xem)</p>
          <DanhSachGhiChu ds={ghiChuCu} />
        </div>
      ) : null}
    </div>
  );
}
