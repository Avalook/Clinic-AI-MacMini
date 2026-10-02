"use client";

// GIAO DỊCH ĐÃ GHI — batch pilot 18/09/2026 (Pack B, vai Thu ngân).
//
// "Đã thanh toán hôm nay" và "Lịch sử giao dịch" đọc cùng MỘT nguồn — SỔ CÁC LẦN
// THU (`payment_cycle`, contract tiền–thuốc CP2) — qua máy chủ, chỉ đọc. Mỗi
// lần thu một dòng: đã thu, đã huỷ (ai, vì sao), chờ xác minh, đã huỷ chờ.
// Phiếu thu trước CP2 không có phương thức: hiện "không rõ (phiếu cũ)", không đoán.
// Phương thức hiện ra là hình thức HIỆU LỰC; [Đổi hình thức] ở từng phiếu đã thu (V7).

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { useNgheBang } from "../dung-nghe-bang";

import { nhanPhan, tenHinhThuc, type PhanThu } from "@/lib/hinh-thuc-thu";
import XemLuot from "../_lam-viec/XemLuot";
import AnhChuyenKhoan, { type AnhCk } from "./AnhChuyenKhoan";
import DoiHinhThuc, { type TrangThaiDoi } from "./DoiHinhThuc";
import HoanTien, { type HoanCuaLanThu } from "./HoanTien";
import NutHoanTac from "./NutHoanTac";

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
  phuong_thuc: string | null;
  /** Chia TM + CK hiệu lực (01/10/2026). */
  phan?: PhanThu[];
  anh_ck?: AnhCk[];
  /** Nút Hoàn tác lần thu — máy chủ quyết. */
  hoan_tac?: { duoc: boolean; ly_do_khong: string | null } | null;
  ma_giao_dich: string | null;
  legacy: boolean;
  can_doi_soat: boolean;
  sau_khi_dong_luot: boolean;
  huy_luc: string | null;
  nguoi_huy: string | null;
  ly_do_huy: string | null;
  /** CP5: khoản hoàn + dòng còn hoàn được — chỉ lần thu đã từng thu. */
  hoan: HoanCuaLanThu | null;
  /** V7: đổi hình thức sau khi thu — cờ do máy chủ quyết + lịch sử đổi. */
  doi_hinh_thuc: TrangThaiDoi | null;
}

const TRANG_THAI: Record<string, string> = {
  PAID: "Đã thu",
  VOIDED: "Đã huỷ phiếu",
  PENDING_VERIFICATION: "Chờ xác minh",
  CANCELLED: "Đã huỷ lần chờ",
};

const INPUT = "min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink";

/** Hoàn tác / đổi hình thức / ảnh CK ở quầy khác → sổ ở đây tự mới (01/10/2026). */
const BANG_GIAO_DICH = [
  "payment_cycle",
  "payment_cycle_doi_hinh_thuc",
  "anh_chuyen_khoan",
  "payment",
] as const;

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

export default function GiaoDich({
  lichSu,
  quay,
  ngay,
}: {
  lichSu: boolean;
  /** Quầy đang đứng: chỉ xem / hoàn tác sổ của loại tiền mình (01/10/2026). */
  quay: "dich_vu" | "thuoc";
  /** Ngày trên thanh ngày của quầy (02/10/2026); không có = hôm nay. Đổi ngày
   *  thì TabThuNgan dựng lại tab này (`key`) — ô "Từ – Đến" chỉ để mở rộng sau đó. */
  ngay?: string;
}) {
  const ngayXem = ngay ?? homNay();
  const [tu, setTu] = useState(ngayXem);
  const [den, setDen] = useState(ngayXem);
  const [hoi, setHoi] = useState<{ tu: string; den: string; lan: number }>(() => ({
    tu: ngayXem,
    den: ngayXem,
    lan: 0,
  }));
  const [kq, setKq] = useState<{
    khoa: string;
    ds?: GiaoDichDong[];
    coQuyenHoan?: boolean;
    loi?: string;
  } | null>(null);
  const [xem, setXem] = useState<string | null>(null);
  const khoa = `${hoi.tu}|${hoi.den}`;
  useNgheBang(BANG_GIAO_DICH, () => setHoi((h) => ({ ...h, lan: h.lan + 1 })));

  useEffect(() => {
    let huy = false;
    void fetch(`/api/cashier?xem=giao-dich&kind=${quay}&tu=${hoi.tu}&den=${hoi.den}`, { cache: "no-store" })
      .then(async (r) => ({ ok: r.ok, d: await r.json().catch(() => null) }))
      .then(({ ok, d }) => {
        if (huy) return;
        setKq(
          ok
            ? {
                khoa: `${hoi.tu}|${hoi.den}`,
                ds: (d as { giao_dich: GiaoDichDong[] }).giao_dich,
                coQuyenHoan: (d as { co_quyen_hoan?: boolean }).co_quyen_hoan === true,
              }
            : { khoa: `${hoi.tu}|${hoi.den}`, loi: (d as { message?: string; error?: string } | null)?.message ?? "Không đọc được giao dịch." },
        );
      });
    return () => {
      huy = true;
    };
  }, [hoi, quay]);

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
          <Button onClick={() => setHoi((h) => ({ tu, den, lan: h.lan + 1 }))}>Xem</Button>
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
            {ds.length} giao dịch {quay === "thuoc" ? "thuốc" : "dịch vụ"} · đã thu (không tính dòng huỷ):{" "}
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
                  {nhanPhan(g.phan) ||
                    (g.phuong_thuc ? tenHinhThuc(g.phuong_thuc) : g.legacy ? "không rõ (phiếu cũ)" : "—")}
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
                <DoiHinhThuc
                  paymentCycleId={g.id}
                  hinhThuc={g.phuong_thuc}
                  soTien={g.so_tien}
                  doi={g.doi_hinh_thuc}
                  onXong={() => setHoi((h) => ({ ...h, lan: h.lan + 1 }))}
                />
                {/* Ảnh chuyển khoản: xem lại / thêm cho lần thu có phần CK (01/10). */}
                {(g.anh_ck?.length ?? 0) > 0 ||
                ((g.trang_thai === "PAID" || g.trang_thai === "PENDING_VERIFICATION") &&
                  (g.phan ?? []).some((p) => p.hinh_thuc === "TRANSFER")) ? (
                  <AnhChuyenKhoan
                    cycleId={g.id}
                    ds={g.anh_ck}
                    choThem={g.trang_thai === "PAID" || g.trang_thai === "PENDING_VERIFICATION"}
                    onDoi={() => setHoi((h) => ({ ...h, lan: h.lan + 1 }))}
                  />
                ) : null}
                {g.hoan_tac?.duoc ? (
                  <div className="mt-1">
                    <NutHoanTac
                      cycleId={g.id}
                      soTien={g.so_tien}
                      quay={quay}
                      onXong={() => setHoi((h) => ({ ...h, lan: h.lan + 1 }))}
                    />
                  </div>
                ) : null}
                {g.hoan && g.visit_id ? (
                  <HoanTien
                    paymentCycleId={g.id}
                    visitId={g.visit_id}
                    kind={g.loai}
                    hoan={g.hoan}
                    coQuyenHoan={kq?.coQuyenHoan === true}
                    onXong={() => setHoi((h) => ({ ...h, lan: h.lan + 1 }))}
                  />
                ) : null}
                <div className="mt-1 flex flex-wrap items-center gap-3">
                  {g.visit_id ? (
                    <Button size="sm" variant="ghost" className="-ml-3" onClick={() => setXem(g.visit_id)}>
                      Xem chi tiết lượt
                    </Button>
                  ) : null}
                  {/* Phiếu thu kiểu HOÁ ĐƠN (khổ 80mm) — quầy thuốc in ở đây (28/09/2026). */}
                  {g.trang_thai === "PAID" ? (
                    <a
                      href={`/print/phieu-thu/${g.id}?loai=thu`}
                      target="_blank"
                      rel="noopener"
                      className="text-sm font-medium text-brand-700 hover:underline"
                    >
                      In phiếu thu
                    </a>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
      {xem ? <XemLuot visitId={xem} onDong={() => setXem(null)} /> : null}
    </section>
  );
}
