"use client";

/**
 * "Sửa lần cuối" dưới một ô giá + nút Lịch sử (Tuyền duyệt 21/10/2026).
 *
 * Hoá đơn tính theo giá LÚC THU — giá đổi giữa lúc chỉ định và lúc thu thì khách
 * trả giá mới. Dòng này để ai cũng trả lời được "sao khách trả số này". Máy chủ
 * gửi sẵn lần đổi gần nhất (`gia_sua_cuoi`); bấm Lịch sử mới tải cả danh sách.
 * Dòng chưa từng đổi giá thì không vẽ gì.
 */

import { History } from "lucide-react";
import { useState } from "react";

import PopoverNeo from "./PopoverNeo";

export interface LanDoiGia {
  luc: string;
  boi: string;
  hanh_dong: "THEM" | "SUA" | "XOA" | string;
  gia_cu: number | null;
  gia_moi: number | null;
}

const VIEC: Record<string, string> = { THEM: "Thêm", SUA: "Sửa", XOA: "Xoá" };

const tien = (n: number | null) =>
  n == null ? "chưa có giá" : `${n.toLocaleString("vi-VN")}đ`;

const gio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

export default function GiaSuaCuoi({
  sua,
  ten,
  duongLichSu,
  canhPhai = false,
}: {
  /** Ô giá căn phải ở máy rộng (bảng giá dạng lưới) → dòng này căn theo. */
  canhPhai?: boolean;
  sua: LanDoiGia | null | undefined;
  /** Tên dòng giá — đầu hộp lịch sử. */
  ten: string;
  /** GET proxy trả `{ items: LanDoiGia[] }` — mọi lần đổi giá của dòng. */
  duongLichSu: string;
}) {
  // Nút neo giữ trong state (không đọc ref lúc vẽ); null = hộp đang đóng.
  const [neo, setNeo] = useState<HTMLElement | null>(null);
  const [ds, setDs] = useState<LanDoiGia[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  if (!sua) return null;

  async function moLichSu(nut: HTMLElement) {
    setNeo(nut);
    setLoi(null);
    try {
      const r = await fetch(duongLichSu, { cache: "no-store" });
      const d = (await r.json().catch(() => null)) as
        | { items?: LanDoiGia[]; message?: string; error?: string }
        | null;
      if (!r.ok) throw new Error(d?.message ?? d?.error ?? "Máy chủ từ chối.");
      setDs(d?.items ?? []);
    } catch (e) {
      setLoi(e instanceof Error ? e.message : "Không tải được lịch sử giá.");
    }
  }

  return (
    <div
      className={`mt-0.5 flex flex-wrap items-center gap-x-1.5 text-meta text-ink-muted ${
        canhPhai ? "lg:justify-end" : "justify-end"
      }`}
    >
      <span>
        {VIEC[sua.hanh_dong] ?? sua.hanh_dong} {gio(sua.luc)} · {sua.boi} ·{" "}
        <span className="tabular-nums">
          {tien(sua.gia_cu)} → {tien(sua.gia_moi)}
        </span>
      </span>
      <button
        type="button"
        onClick={(e) => void moLichSu(e.currentTarget)}
        className="inline-flex items-center gap-1 rounded-control px-1 text-brand-700 hover:bg-surface-sunken"
      >
        <History className="size-3" aria-hidden />
        Lịch sử
      </button>
      {neo ? (
        <PopoverNeo
          neo={neo}
          onDong={() => setNeo(null)}
          dau={
            <>
              <p className="text-body font-semibold text-ink">Lịch sử giá</p>
              <p className="truncate text-meta text-ink-muted">{ten}</p>
            </>
          }
        >
          {loi ? (
            <p className="text-body text-danger">{loi}</p>
          ) : ds == null ? (
            <p className="text-body text-ink-muted">Đang tải…</p>
          ) : (
            <ol className="divide-y divide-hairline">
              {ds.map((x) => (
                <li key={`${x.luc}-${x.hanh_dong}`} className="py-2 text-body">
                  <p className="tabular-nums text-ink">
                    {tien(x.gia_cu)} → <span className="font-semibold">{tien(x.gia_moi)}</span>
                  </p>
                  <p className="text-meta text-ink-muted">
                    {VIEC[x.hanh_dong] ?? x.hanh_dong} · {gio(x.luc)} · {x.boi}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </PopoverNeo>
      ) : null}
    </div>
  );
}
