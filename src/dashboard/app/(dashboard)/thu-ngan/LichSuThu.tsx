"use client";

// LỊCH SỬ THU — GOM THEO KHÁCH (27/09/2026, đợt 3 — bản mẫu quầy thu).
//
// Mỗi khách MỘT dòng (mọi lần thu / hoàn / huỷ của khách gộp lại, bấm ▸ để xem
// từng phiếu); 5 ô tổng; lọc ngày · tên/mã/SĐT/mã phiếu · hình thức · người
// thu; Xuất Excel (CSV). Gom, cộng và lọc đều ở máy chủ
// (`GET /api/v1/cashier/lich-su` → `quay_thu_service.lich_su`) — màn chỉ vẽ.
// Hoàn tiền / huỷ phiếu vẫn ở tab "Đã thanh toán hôm nay" (GiaoDich).
// [Đổi hình thức] (V7, 30/09): ở từng lần thu khi mở ▸ — hình thức hiện ra và
// 5 ô tổng là hình thức HIỆU LỰC (sau mọi lần đổi).

import { useCallback, useEffect, useState } from "react";

import SoLuot from "@/components/ui/SoLuot";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import Chip from "@/components/ui/Chip";
import { todayVn } from "@/lib/roster";
import { tenHinhThuc, type PhanThu } from "@/lib/hinh-thuc-thu";

import { useNgheBang } from "../dung-nghe-bang";
import AnhChuyenKhoan, { type AnhCk } from "./AnhChuyenKhoan";
import DoiHinhThuc, { type HinhThuc, type TrangThaiDoi } from "./DoiHinhThuc";
import NutHoanTac from "./NutHoanTac";

/** Hoàn tác / đổi hình thức / ảnh CK ở nơi khác → lịch sử tự mới (01/10/2026). */
const BANG_LICH_SU = [
  "payment_cycle",
  "payment_cycle_doi_hinh_thuc",
  "anh_chuyen_khoan",
  "payment",
] as const;

interface SuKien {
  loai: "thu" | "hoan" | "huy";
  id: string;
  luc: string | null;
  ma: string;
  so_tien: number;
  hinh_thuc: string | null;
  nguoi: string | null;
  dich_vu: string[];
  ly_do: string | null;
  cho: boolean;
  /** V7 — chỉ sự kiện "thu": cờ đổi hình thức (máy chủ quyết) + lịch sử đổi. */
  doi_hinh_thuc?: TrangThaiDoi | null;
  /** Chia TM + CK (01/10/2026) + nhãn máy chủ dựng sẵn. */
  phan?: PhanThu[];
  nhan_hinh_thuc?: string;
  anh_ck?: AnhCk[];
  hoan_tac?: { duoc: boolean; ly_do_khong: string | null } | null;
}

interface KhachLichSu {
  visit_id: string;
  ten: string | null;
  ma_bn: string | null;
  so_booking: number | null;
  so_tiep_don: number | null;
  su_kien: SuKien[];
  tong_goc: number;
  tong_hoan: number;
  con_lai: number;
  dau: string | null;
  cuoi: string | null;
  so_phieu: number;
  ma_phieu_dau: string | null;
  hinh_thuc: string[];
  nguoi_thu: string[];
  co_hoan: boolean;
}

interface GoiLichSu {
  tong: { tong_thu: number; tien_mat: number; chuyen_khoan: number; hoan: number };
  nguoi_thu: string[];
  khach: KhachLichSu[];
}

const TEN_LOAI: Record<SuKien["loai"], string> = { thu: "Thu", hoan: "Hoàn", huy: "Huỷ" };

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

function gio(iso: string | null, coNgay: boolean): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    ...(coNgay ? { day: "2-digit", month: "2-digit" } : {}),
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

const O_NHAP = "h-8 rounded-control border border-line bg-surface px-2 text-meta text-ink";

export default function LichSuThu({ ngay }: { ngay?: string }) {
  // Thanh ngày của quầy (02/10/2026) quyết ngày xem; ô "Từ – Đến" dưới đây chỉ
  // để MỞ RỘNG khoảng sau đó (đối soát cả tuần). Đổi ngày → TabThuNgan dựng lại (`key`), về đúng ngày ấy.
  const ngayXem = ngay ?? todayVn();
  const [tu, setTu] = useState(ngayXem);
  const [den, setDen] = useState(ngayXem);
  const [tim, setTim] = useState("");
  const [hinhThuc, setHinhThuc] = useState("");
  const [nguoiThu, setNguoiThu] = useState("");
  const [goi, setGoi] = useState<GoiLichSu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [mo, setMo] = useState<string | null>(null);

  const q = new URLSearchParams({ tu, den });
  if (tim.trim()) q.set("tim", tim.trim());
  if (hinhThuc) q.set("hinh_thuc", hinhThuc);
  if (nguoiThu) q.set("nguoi_thu", nguoiThu);
  const chuoi = q.toString();

  const tai = useCallback(async () => {
    setLoi(null);
    const r = await fetch(`/api/cashier?xem=lich-su&${chuoi}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as (GoiLichSu & { message?: string; error?: string }) | null;
    if (!r.ok || !d) setLoi(d?.message ?? d?.error ?? "Không đọc được lịch sử thu.");
    else setGoi(d);
  }, [chuoi]);

  useEffect(() => {
    const t = setTimeout(() => void tai(), 250);
    return () => clearTimeout(t);
  }, [tai]);
  useNgheBang(BANG_LICH_SU, () => void tai());

  const nhieuNgay = tu !== den;

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input type="date" aria-label="Từ ngày" value={tu} onChange={(e) => setTu(e.target.value)} className={O_NHAP} />
        <span className="text-meta text-ink-muted">→</span>
        <input type="date" aria-label="Đến ngày" value={den} onChange={(e) => setDen(e.target.value)} className={O_NHAP} />
        <input
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          placeholder="Tên, mã khách, SĐT, mã phiếu"
          aria-label="Tìm"
          className={`${O_NHAP} min-w-48 flex-1`}
        />
        <select aria-label="Hình thức" value={hinhThuc} onChange={(e) => setHinhThuc(e.target.value)} className={O_NHAP}>
          <option value="">Mọi hình thức</option>
          <option value="CASH">Tiền mặt</option>
          <option value="TRANSFER">Chuyển khoản</option>
        </select>
        <select aria-label="Người thu" value={nguoiThu} onChange={(e) => setNguoiThu(e.target.value)} className={O_NHAP}>
          <option value="">Mọi người thu</option>
          {(goi?.nguoi_thu ?? []).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        <a
          href={`/api/cashier?xem=lich-su-csv&${chuoi}`}
          className="inline-flex h-8 items-center rounded-control px-3 text-meta font-medium text-ink ring-1 ring-inset ring-line-strong hover:bg-surface-muted"
        >
          Xuất Excel
        </a>
      </div>

      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}

      {goi ? (
        <>
          <StatRow>
            <StatCard label="Tổng thu" value={tien(goi.tong.tong_thu)} tone="brand" />
            <StatCard label="Tiền mặt" value={tien(goi.tong.tien_mat)} />
            <StatCard label="Chuyển khoản" value={tien(goi.tong.chuyen_khoan)} />
            <StatCard label="Hoàn / huỷ" value={goi.tong.hoan ? `−${tien(goi.tong.hoan)}` : tien(0)} tone="warning" />
          </StatRow>

          {goi.khach.length === 0 ? (
            <p className="rounded-card border border-line bg-surface p-6 text-center text-body text-ink-muted shadow-card">
              Không có lần thu nào trong khoảng này.
            </p>
          ) : (
            <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
              {goi.khach.map((k) => {
                const dangMo = mo === k.visit_id;
                return (
                  <li key={k.visit_id} className="border-b border-line last:border-b-0">
                    <button
                      type="button"
                      aria-expanded={dangMo}
                      onClick={() => setMo(dangMo ? null : k.visit_id)}
                      className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5 text-left hover:bg-surface-sunken"
                    >
                      <SoLuot dang="tron" checkin={k.so_tiep_don} booking={k.so_booking} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-emph font-semibold text-ink">{k.ten ?? "—"}</span>
                        <span className="block truncate text-meta text-ink-muted">
                          {gio(k.dau, nhieuNgay)}
                          {k.cuoi && k.cuoi !== k.dau ? ` → ${gio(k.cuoi, nhieuNgay)}` : ""} · {k.so_phieu} phiếu{" "}
                          {k.ma_phieu_dau ?? ""}
                          {k.so_phieu > 1 ? ` +${k.so_phieu - 1}` : ""} ·{" "}
                          {k.hinh_thuc.map((h) => tenHinhThuc(h)).join(" + ")} · {k.nguoi_thu.join(", ")}
                        </span>
                      </span>
                      <span className="text-right">
                        <span className="block text-body font-semibold tabular-nums text-ink">{tien(k.con_lai)}</span>
                        {k.co_hoan ? (
                          <span className="block text-meta tabular-nums text-ink-faint line-through">
                            {tien(k.tong_goc)}
                          </span>
                        ) : null}
                      </span>
                      <Chip tone={k.co_hoan ? "warning" : "success"}>{k.co_hoan ? "Có hoàn" : "Đã thu"}</Chip>
                      <span aria-hidden="true" className="text-ink-muted">
                        {dangMo ? "▾" : "▸"}
                      </span>
                    </button>
                    {dangMo ? (
                      <ul className="space-y-1 bg-surface-muted px-4 py-2">
                        {k.su_kien.map((s) => (
                          <li key={`${s.loai}:${s.id}`} className="flex flex-wrap items-center gap-x-3 text-meta">
                            <span className="tabular-nums text-ink-muted">{gio(s.luc, nhieuNgay)}</span>
                            <span className="font-medium text-ink">
                              {TEN_LOAI[s.loai]} · {s.ma}
                            </span>
                            <span className={`tabular-nums ${s.so_tien < 0 ? "text-warning" : "text-ink"}`}>
                              {s.so_tien < 0 ? `−${tien(-s.so_tien)}` : tien(s.so_tien)}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-ink-muted">
                              {[s.nhan_hinh_thuc || tenHinhThuc(s.hinh_thuc) || null, s.nguoi, s.dich_vu.join(", ")]
                                .filter(Boolean)
                                .join(" · ")}
                              {s.ly_do ? ` · lý do: ${s.ly_do}` : ""}
                              {s.cho ? " · chờ hoàn" : ""}
                            </span>
                            {s.loai !== "huy" ? (
                              <a
                                href={`/print/phieu-thu/${s.id}?loai=${s.loai === "hoan" ? "hoan" : "thu"}`}
                                target="_blank"
                                rel="noopener"
                                className="font-medium text-brand-700 hover:underline"
                              >
                                In
                              </a>
                            ) : null}
                            {s.loai === "thu" && s.doi_hinh_thuc ? (
                              <div className="basis-full">
                                <DoiHinhThuc
                                  paymentCycleId={s.id}
                                  hinhThuc={(s.hinh_thuc as HinhThuc | null) ?? null}
                                  soTien={s.so_tien}
                                  doi={s.doi_hinh_thuc}
                                  onXong={() => void tai()}
                                />
                              </div>
                            ) : null}
                            {s.loai === "thu" &&
                            ((s.anh_ck?.length ?? 0) > 0 ||
                              (s.hoan_tac?.duoc && (s.phan ?? []).some((p) => p.hinh_thuc === "TRANSFER"))) ? (
                              <div className="basis-full">
                                <AnhChuyenKhoan
                                  cycleId={s.id}
                                  ds={s.anh_ck}
                                  choThem={Boolean(s.hoan_tac?.duoc)}
                                  onDoi={() => void tai()}
                                />
                              </div>
                            ) : null}
                            {s.loai === "thu" && s.hoan_tac?.duoc ? (
                              <div className="basis-full">
                                <NutHoanTac cycleId={s.id} soTien={s.so_tien} quay="dich_vu" onXong={() => void tai()} />
                              </div>
                            ) : null}
                          </li>
                        ))}
                        {k.co_hoan ? (
                          <li className="text-meta font-semibold text-ink">Còn lại {tien(k.con_lai)}</li>
                        ) : null}
                      </ul>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </>
      ) : loi ? null : (
        <p className="text-body text-ink-muted">Đang tải…</p>
      )}
    </section>
  );
}
