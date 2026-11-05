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
import { thuNho } from "@/lib/thu-nho-anh";

export interface AnhCk {
  id: string;
  luc: string | null;
  boi: string | null;
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

/** Đường đi của ảnh — mặc định là ảnh của LẦN THU quầy (`/api/payment/anh-ck`). Sổ
 *  thu hộ đối tác truyền đường của nó (bảng riêng, kế hoạch XN 4.4 b) — cùng khung. */
export interface DichAnhCk {
  tai: (tep: File) => Promise<string | null>;
  xem: (id: string) => string;
  go: (id: string) => Promise<string | null>;
}

async function goQuay(id: string): Promise<string | null> {
  const r = await fetch(`/api/payment/anh-ck?id=${encodeURIComponent(id)}`, { method: "DELETE" });
  if (r.ok) return null;
  const d = (await r.json().catch(() => null)) as { message?: string } | null;
  return d?.message ?? "Không gỡ được ảnh.";
}

export default function AnhChuyenKhoan({
  cycleId,
  ds,
  choThem = true,
  chiXem = false,
  onDoi,
  dich,
}: {
  cycleId: string;
  ds: AnhCk[] | null | undefined;
  /** Hiện nút thêm ảnh (lần thu chuyển khoản còn hiệu lực). */
  choThem?: boolean;
  chiXem?: boolean;
  onDoi: () => void;
  dich?: DichAnhCk;
}) {
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const anh = ds ?? [];
  if (anh.length === 0 && !choThem) return null;
  const xem = dich?.xem ?? ((id: string) => `/api/payment/anh-ck?id=${encodeURIComponent(id)}`);

  async function them(tep: File | undefined) {
    if (!tep) return;
    setDang(true);
    setLoi(null);
    const l = dich ? await dich.tai(tep) : await taiAnhChuyenKhoan(cycleId, tep);
    setDang(false);
    if (l) setLoi(l);
    else onDoi();
  }

  async function go(id: string) {
    setDang(true);
    setLoi(null);
    const l = await (dich?.go ?? goQuay)(id);
    setDang(false);
    if (l) setLoi(l);
    else onDoi();
  }

  return (
    <div className="mt-1 space-y-1">
      {anh.length > 0 ? (
        <ul className="flex flex-wrap gap-2" aria-label="Ảnh chuyển khoản">
          {anh.map((a) => (
            <li key={a.id} className="flex flex-col items-start gap-1">
              <a
                href={xem(a.id)}
                target="_blank"
                rel="noopener"
                title="Xem ảnh chuyển khoản"
                className="block size-16 overflow-hidden rounded-control border border-line bg-surface-sunken"
              >
                {/* eslint-disable-next-line @next/next/no-img-element --
                    ảnh đi qua route XÁC THỰC, không qua bộ tối ưu ảnh dùng chung. */}
                <img
                  src={xem(a.id)}
                  alt="Ảnh chuyển khoản"
                  loading="lazy"
                  className="size-full object-cover"
                />
              </a>
              {!chiXem ? <Button size="sm" variant="ghost" disabled={dang} onClick={() => void go(a.id)}>
                Gỡ ảnh
              </Button> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {choThem && !chiXem ? (
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
