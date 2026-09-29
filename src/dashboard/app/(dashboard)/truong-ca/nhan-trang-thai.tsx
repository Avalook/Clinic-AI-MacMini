"use client";

// NHÃN TRẠNG THÁI trên màn Điều phối ca (Tuyền 29/09/2026): "nhìn là biết, không
// chuyển bừa". MÁY CHỦ quyết trạng thái + mốc giờ
// (`services/nhan_trang_thai_dieu_phoi.py`); ở đây chỉ vẽ chip và đổi mốc giờ
// thành "từ HH:MM · N′" / "chờ N′" theo đồng hồ.

import { useEffect, useState } from "react";

import Chip, { type ChipTone } from "@/components/ui/Chip";

export interface NhanTrangThai {
  ma: string;
  nhan: string;
  tu_luc: string | null;
  stt: number | null;
  so_truoc: number | null;
  chuyen_duoc: boolean;
  dat_phong_duoc?: boolean;
}

const TONE: Record<string, ChipTone> = {
  DANG_CHO: "warning",
  DA_GOI: "info",
  DANG_LAM: "run",
  XONG: "success",
  CHO_KQ_DOI_TAC: "doi_tac",
  KHACH_VE: "neutral",
  CHUA_THU: "warning",
  CHO_XEP: "warning",
  DA_DUNG: "danger",
  KHONG_LAM: "neutral",
  DOI_TAC_LAM: "doi_tac",
  CHO_BUOC_KHAC: "neutral",
  CHUA_VAO_HANG: "neutral",
};

function gio(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
}

/** Đồng hồ vẽ lại mỗi 30 giây để số phút nhích. */
function useBayGio(): number {
  const [bayGio, setBayGio] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setBayGio(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);
  return bayGio;
}

export function chuNhan(t: NhanTrangThai, bayGio: number): string {
  const phan: string[] = [t.nhan];
  if (t.stt != null) phan.push(`STT ${t.stt}`);
  if (t.so_truoc != null && t.so_truoc > 0) phan.push(`${t.so_truoc} người trước`);
  if (t.tu_luc) {
    const ms = new Date(t.tu_luc).getTime();
    const p = Number.isNaN(ms) ? null : Math.max(0, Math.floor((bayGio - ms) / 60_000));
    if (t.ma === "DANG_LAM") phan.push(`từ ${gio(t.tu_luc)}${p != null ? ` · ${p}′` : ""}`);
    else if (t.ma === "DANG_CHO" && p != null) phan.push(`chờ ${p}′`);
    else if (t.ma === "DA_GOI" || t.ma === "XONG") phan.push(gio(t.tu_luc));
  }
  return phan.join(" · ");
}

export function ChipTrangThai({ t }: { t: NhanTrangThai }) {
  const bayGio = useBayGio();
  return (
    <Chip tone={TONE[t.ma] ?? "neutral"} className="shrink-0 tabular-nums">
      {chuNhan(t, bayGio)}
    </Chip>
  );
}
