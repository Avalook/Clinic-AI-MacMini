"use client";

// ẢNH CHUYỂN KHOẢN của một lần thu (Tuyền 01/10/2026) — xem lại, thêm, gỡ nhầm.
//
// Lưu theo cơ chế tệp sẵn có (ổ VPS trước → Viettel CFS) ở bảng riêng
// `anh_chuyen_khoan`; máy chủ kiểm quyền (thu đúng loại tiền) và kiểu ảnh.
// Ảnh thu nhỏ trước khi gửi (≤ 1600px JPEG) — ảnh chụp điện thoại vài MB thành
// vài trăm KB, và HEIC của iPhone (trình duyệt đọc được) thành JPEG máy tính
// phòng khám xem được.

import { useState } from "react";

import Button from "@/components/ui/Button";

export interface AnhCk {
  id: string;
  luc: string | null;
  boi: string | null;
}

const CANH_TOI_DA = 1600;

async function thuNho(tep: File): Promise<Blob> {
  try {
    const bmp = await createImageBitmap(tep);
    const tile = Math.min(1, CANH_TOI_DA / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * tile);
    canvas.height = Math.round(bmp.height * tile);
    canvas.getContext("2d")?.drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, "image/jpeg", 0.85));
    return blob ?? tep;
  } catch {
    // Trình duyệt không đọc được ảnh này: gửi nguyên — máy chủ tự kiểm kiểu.
    return tep;
  }
}

/** Tải một ảnh chuyển khoản lên lần thu; trả câu lỗi hoặc null. */
export async function taiAnhChuyenKhoan(cycleId: string, tep: File): Promise<string | null> {
  const fd = new FormData();
  fd.set("payment_cycle_id", cycleId);
  fd.set("file", await thuNho(tep), "chuyen-khoan.jpg");
  try {
    const r = await fetch("/api/payment/anh-ck", { method: "POST", body: fd });
    if (r.ok) return null;
    const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
    return d?.message ?? d?.error ?? "Không lưu được ảnh chuyển khoản.";
  } catch {
    return "Mất kết nối — ảnh chuyển khoản CHƯA được lưu.";
  }
}

export default function AnhChuyenKhoan({
  cycleId,
  ds,
  choThem = true,
  onDoi,
}: {
  cycleId: string;
  ds: AnhCk[] | null | undefined;
  /** Hiện nút thêm ảnh (lần thu chuyển khoản còn hiệu lực). */
  choThem?: boolean;
  onDoi: () => void;
}) {
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const anh = ds ?? [];
  if (anh.length === 0 && !choThem) return null;

  async function them(tep: File | undefined) {
    if (!tep) return;
    setDang(true);
    setLoi(null);
    const l = await taiAnhChuyenKhoan(cycleId, tep);
    setDang(false);
    if (l) setLoi(l);
    else onDoi();
  }

  async function go(id: string) {
    setDang(true);
    setLoi(null);
    const r = await fetch(`/api/payment/anh-ck?id=${encodeURIComponent(id)}`, { method: "DELETE" });
    setDang(false);
    if (!r.ok) {
      const d = (await r.json().catch(() => null)) as { message?: string } | null;
      setLoi(d?.message ?? "Không gỡ được ảnh.");
    } else onDoi();
  }

  return (
    <div className="mt-1 space-y-1">
      {anh.length > 0 ? (
        <ul className="flex flex-wrap gap-2" aria-label="Ảnh chuyển khoản">
          {anh.map((a) => (
            <li key={a.id} className="flex flex-col items-start gap-1">
              <a
                href={`/api/payment/anh-ck?id=${encodeURIComponent(a.id)}`}
                target="_blank"
                rel="noopener"
                title="Xem ảnh chuyển khoản"
                className="block size-16 overflow-hidden rounded-control border border-line bg-surface-sunken"
              >
                {/* eslint-disable-next-line @next/next/no-img-element --
                    ảnh đi qua route XÁC THỰC, không qua bộ tối ưu ảnh dùng chung. */}
                <img
                  src={`/api/payment/anh-ck?id=${encodeURIComponent(a.id)}`}
                  alt="Ảnh chuyển khoản"
                  loading="lazy"
                  className="size-full object-cover"
                />
              </a>
              <Button size="sm" variant="ghost" disabled={dang} onClick={() => void go(a.id)}>
                Gỡ ảnh
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {choThem ? (
        <label className="flex flex-wrap items-center gap-2 text-meta text-ink-soft">
          {anh.length > 0 ? "Thêm ảnh chuyển khoản" : "Ảnh chuyển khoản (không bắt buộc)"}
          <input
            type="file"
            accept="image/*"
            capture="environment"
            disabled={dang}
            onChange={(e) => void them(e.target.files?.[0])}
            className="max-w-full text-meta text-ink-soft file:mr-2 file:min-h-8 file:rounded-control file:border-0 file:bg-surface-muted file:px-3 file:text-meta file:font-medium file:text-ink"
          />
        </label>
      ) : null}
      {dang ? <p className="text-meta text-ink-muted">Đang lưu ảnh…</p> : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
