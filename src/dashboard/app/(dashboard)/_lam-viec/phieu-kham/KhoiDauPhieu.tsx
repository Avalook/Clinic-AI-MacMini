"use client";

// Dải đầu phiếu: hành chính + sinh hiệu + ghi chú bác sĩ tư vấn — CHỈ ĐỌC.
//
// Nguồn chốt: *"đồng bộ từ Điều dưỡng"*, *"không bắt nhập lại"*. Sinh hiệu sai
// thì sửa ở màn đo sinh hiệu; ở đây không có ô nào để gõ đè. Thứ tự và khoá lấy
// từ `HANH_CHINH.lien_ket.truong` của khung, nhãn lấy từ máy chủ.

import { hienThi, type DauPhieu } from "@/lib/phieu-kham";

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

export function KhoiTuVan({ dau }: { dau: DauPhieu }) {
  return (
    <div className="rounded-card border border-hairline bg-surface-muted p-3">
      <p className="text-meta font-semibold text-ink-muted">
        Dữ liệu mang sang từ phần khám/tư vấn ban đầu
      </p>
      {dau.tu_van.length === 0 ? (
        <p className="mt-1 text-body text-ink-faint">—</p>
      ) : (
        <ul className="mt-1 space-y-1">
          {dau.tu_van.map((g) => (
            <li key={`${g.luc}-${g.noi_dung.slice(0, 16)}`} className="text-body text-ink">
              <span className="mr-2 text-meta text-ink-faint">{gioVn(g.luc)}</span>
              <span className="whitespace-pre-wrap">{g.noi_dung}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
