"use client";

// GIAO DỊCH ĐÃ GHI — batch pilot 18/09/2026 (Pack B, vai Thu ngân).
//
// "Đã thanh toán hôm nay" và "Lịch sử giao dịch" đọc cùng MỘT nguồn — SỔ CÁC LẦN
// THU (`payment_cycle`, contract tiền–thuốc CP2) — qua máy chủ, chỉ đọc. Mỗi
// lần thu một dòng: đã thu, đã huỷ (ai, vì sao), chờ xác minh, đã huỷ chờ.
// Phiếu thu trước CP2 không có phương thức: hiện "không rõ (phiếu cũ)", không đoán.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";

import XemLuot from "../_lam-viec/XemLuot";

interface GiaoDichDong {
  id: string;
  visit_id: string | null;
  ten: string | null;
  ma_bn: string | null;
  loai: string;
  trang_thai: string;
  so_tien: number | null;
  luc: string | null;
  nguoi_thu: string | null;
  phuong_thuc: "CASH" | "TRANSFER" | "QR" | null;
  ma_giao_dich: string | null;
  legacy: boolean;
  can_doi_soat: boolean;
  sau_khi_dong_luot: boolean;
  huy_luc: string | null;
  nguoi_huy: string | null;
  ly_do_huy: string | null;
}

const TEN_PT: Record<string, string> = { CASH: "tiền mặt", TRANSFER: "chuyển khoản", QR: "QR" };
const TRANG_THAI: Record<string, string> = {
  PAID: "Đã thu",
  VOIDED: "Đã huỷ phiếu",
  PENDING_VERIFICATION: "Chờ xác minh",
  CANCELLED: "Đã huỷ lần chờ",
};

const INPUT = "min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink";

function homNay(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Ho_Chi_Minh" });
}
function ngayGio(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    dateStyle: "short",
    timeStyle: "short",
  });
}

export default function GiaoDich({ lichSu }: { lichSu: boolean }) {
  const [tu, setTu] = useState(homNay);
  const [den, setDen] = useState(homNay);
  const [hoi, setHoi] = useState<{ tu: string; den: string }>(() => ({ tu: homNay(), den: homNay() }));
  const [kq, setKq] = useState<{ khoa: string; ds?: GiaoDichDong[]; loi?: string } | null>(null);
  const [xem, setXem] = useState<string | null>(null);
  const khoa = `${hoi.tu}|${hoi.den}`;

  useEffect(() => {
    let huy = false;
    void fetch(`/api/cashier?xem=giao-dich&tu=${hoi.tu}&den=${hoi.den}`, { cache: "no-store" })
      .then(async (r) => ({ ok: r.ok, d: await r.json().catch(() => null) }))
      .then(({ ok, d }) => {
        if (huy) return;
        setKq(
          ok
            ? { khoa: `${hoi.tu}|${hoi.den}`, ds: (d as { giao_dich: GiaoDichDong[] }).giao_dich }
            : { khoa: `${hoi.tu}|${hoi.den}`, loi: (d as { message?: string; error?: string } | null)?.message ?? "Không đọc được giao dịch." },
        );
      });
    return () => {
      huy = true;
    };
  }, [hoi]);

  const ds = kq?.khoa === khoa ? kq.ds : undefined;
  const loi = kq?.khoa === khoa ? kq.loi : undefined;
  // Chỉ lần thu ĐÃ THU mới cộng — chờ xác minh chưa phải tiền đã nhận.
  const tong = (ds ?? [])
    .filter((g) => g.trang_thai === "PAID")
    .reduce((t, g) => t + (g.so_tien ?? 0), 0);

  return (
    <section className="space-y-3">
      {lichSu ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="grid gap-1 text-xs font-semibold text-ink">
            Từ ngày
            <input type="date" value={tu} onChange={(e) => setTu(e.target.value)} className={INPUT} />
          </label>
          <label className="grid gap-1 text-xs font-semibold text-ink">
            Đến ngày
            <input type="date" value={den} onChange={(e) => setDen(e.target.value)} className={INPUT} />
          </label>
          <Button onClick={() => setHoi({ tu, den })}>Xem</Button>
        </div>
      ) : null}
      {loi ? (
        <p role="alert" className="text-sm text-danger">
          {loi}
        </p>
      ) : !ds ? (
        <p className="text-sm text-ink-muted">Đang tải…</p>
      ) : ds.length === 0 ? (
        <p className="text-sm text-ink-muted">Chưa có giao dịch nào trong khoảng này.</p>
      ) : (
        <>
          <p className="text-sm text-ink-soft">
            {ds.length} giao dịch · đã thu (không tính dòng huỷ):{" "}
            <b className="text-ink">{tong.toLocaleString("vi-VN")} đ</b>
          </p>
          <ul className="grid gap-2">
            {ds.map((g) => (
              <li key={g.id} className="rounded-card border border-line bg-surface p-3 shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-ink">
                    {g.ten ?? "—"} <span className="text-xs font-normal text-ink-muted">{g.ma_bn ?? ""}</span>
                  </p>
                  <p className={`text-sm font-semibold ${g.trang_thai === "PAID" ? "text-ink" : "text-ink-faint line-through"}`}>
                    {(g.so_tien ?? 0).toLocaleString("vi-VN")} đ · {TRANG_THAI[g.trang_thai] ?? g.trang_thai}
                  </p>
                </div>
                <p className="text-xs text-ink-soft">
                  {g.loai === "thuoc" ? "Thuốc" : "Dịch vụ"} · {ngayGio(g.luc)} · {g.nguoi_thu ?? "—"} · phương thức:{" "}
                  {g.phuong_thuc ? TEN_PT[g.phuong_thuc] : g.legacy ? "không rõ (phiếu cũ)" : "—"}
                  {g.ma_giao_dich ? ` · mã GD ${g.ma_giao_dich}` : ""}
                </p>
                {g.can_doi_soat ? (
                  // Tiền THẬT đã nhận theo ảnh chụp hoá đơn lúc chờ; hoá đơn hiện
                  // tại đã khác → cần xử lý tài chính, không phải "chưa trả".
                  <p className="text-xs font-medium text-warning">
                    Cần đối soát: hoá đơn đã đổi trong lúc chờ xác minh.
                  </p>
                ) : null}
                {g.huy_luc ? (
                  <p className="text-xs text-danger">
                    Đã huỷ {ngayGio(g.huy_luc)} — {g.nguoi_huy ?? "?"}: {g.ly_do_huy ?? ""}
                    {g.sau_khi_dong_luot ? " · phát sinh SAU khi đóng lượt" : ""}
                  </p>
                ) : null}
                {g.visit_id ? (
                  <Button size="sm" variant="ghost" className="mt-1 -ml-3" onClick={() => setXem(g.visit_id)}>
                    Xem chi tiết lượt
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      )}
      {xem ? <XemLuot visitId={xem} onDong={() => setXem(null)} /> : null}
    </section>
  );
}
