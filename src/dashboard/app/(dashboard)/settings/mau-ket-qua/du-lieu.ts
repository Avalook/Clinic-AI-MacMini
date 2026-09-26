// Kiểu dữ liệu + gọi API của màn Mẫu kết quả.

import { nhanLoi, type ThanLoi } from "@/lib/loi-api";
import type { MucMau } from "@/lib/sua-mau";

export interface MauNgan {
  ma: string;
  nhom: string;
  ten: string;
  form_id: string;
  version: number | null;
  xuat_ban_luc: string | null;
}

export interface DichVuGan {
  service_code: string;
  ma_kiotviet: string | null;
  ten: string;
  phong: string | null;
  mau: string[];
}

export interface BangGan {
  quyen: { gan: boolean; sua: boolean; xuat_ban: boolean };
  mau: MauNgan[];
  dich_vu: DichVuGan[];
}

export interface DeXuat {
  ma_dich_vu: string;
  ten_dich_vu: string;
  mau: string;
  ten_mau: string;
  so_tu_trung: number;
}

export interface BieuMau {
  form_id: string;
  version: number;
  ten: string;
  nhom: string;
  khung: MucMau[];
  xuat_ban_luc: string | null;
  so_phieu_da_dien: number;
}

export type KetQua<T> = { ok: true; d: T } | { ok: false; loi: string; status: number };

async function goi<T>(url: string, init?: RequestInit): Promise<KetQua<T>> {
  const r = await fetch(url, { cache: "no-store", ...init }).catch(() => null);
  if (!r) return { ok: false, loi: "Mất kết nối tới máy chủ.", status: 0 };
  const d = (await r.json().catch(() => null)) as unknown;
  if (!r.ok) return { ok: false, loi: nhanLoi(d as ThanLoi | null, "Máy chủ từ chối."), status: r.status };
  return { ok: true, d: d as T };
}

export const docJson = <T>(url: string) => goi<T>(url);

export const guiLenh = <T>(than: Record<string, unknown>) =>
  goi<T>("/api/mau-ket-qua", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(than),
  });
