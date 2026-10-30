"use client";

// KIỂM KÊ TIỀN MẶT KÉT ĐẦU CA – CUỐI CA (31/10/2026).
//
// Gắn ngay dưới "Chốt ca" khi đang xem ĐÚNG một ca (một ngày, một ca, một cơ sở):
//   · Quỹ đầu ca — gõ tổng hoặc đếm theo mệnh giá; gợi ý = tiền đếm cuối ca trước.
//   · Tiền mặt trong ca (thu / huỷ / trả lại) + Dự kiến trong két — MÁY CHỦ tính
//     từ đúng dòng Tiền mặt của báo cáo ca này.
//   · Đếm cuối ca — cùng cách nhập; lệch ≠ 0 phải ghi lý do; người nhận bàn giao
//     tuỳ chọn. Đã đếm → [Mở lại] (ghi lý do) để đếm lại; vết ở "Lịch sử két".
// Xem cả ngày / nhiều ngày: `KetTienMatNgay` liệt kê các ca (số chụp lúc đếm).
//
// Màn chỉ cộng bảng đếm và trừ "đếm − dự kiến" để HIỂN THỊ lúc gõ; máy chủ cộng
// lại, tính dự kiến / lệch và Postgres ép công thức.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import ChipChon from "@/components/ui/ChipChon";
import ONhap from "@/components/ui/ONhap";
import { docSoTien } from "@/lib/hinh-thuc-thu";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { useNgheBang } from "../dung-nghe-bang";

export interface KetCa {
  id: string;
  ngay: string;
  ca: string;
  ten_ca: string;
  ten_co_so: string | null;
  quy_dau: number;
  quy_dau_dem: Record<string, number> | null;
  quy_dau_boi_ten: string | null;
  quy_dau_luc: string | null;
  dem_cuoi: number | null;
  dem_cuoi_dem: Record<string, number> | null;
  thu_tien_mat: number | null;
  du_kien: number | null;
  lech: number | null;
  ly_do_lech: string | null;
  nguoi_nhan: string | null;
  dem_boi_ten: string | null;
  dem_luc: string | null;
  da_dem: boolean;
}

interface XemKet {
  ten_ca: string;
  menh_gia: number[];
  ket: KetCa | null;
  tien_mat: { thu: number; huy: number; hoan: number; thuc_thu: number };
  du_kien_song: number | null;
  goi_y_quy_dau: { so_tien: number; ngay: string; ten_ca: string } | null;
  lich_su: { hanh_dong: string; ly_do: string | null; luc: string; boi: string | null; ban_chup: Partial<KetCa> }[];
}

const tien = (n: number | null | undefined) => (n == null ? "—" : `${n.toLocaleString("vi-VN")}đ`);
const tienLech = (n: number) => (n > 0 ? `+${tien(n)} (thừa)` : n < 0 ? `−${tien(-n)} (thiếu)` : "0đ (khớp)");
const gio = (v: string | null) =>
  v ? new Date(v).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour12: false }) : "";
const TEN_VIEC: Record<string, string> = {
  QUY_DAU: "Nhập quỹ đầu",
  SUA_QUY_DAU: "Sửa quỹ đầu",
  DEM_CUOI: "Kiểm kê cuối ca",
  MO_LAI: "Mở lại",
};

/** Một lần nhập tiền: tổng gõ tay, hoặc bảng đếm theo mệnh giá. */
interface Nhap {
  theoTo: boolean;
  tongChu: string;
  to: Record<string, string>;
}
const NHAP_TRONG: Nhap = { theoTo: false, tongChu: "", to: {} };

function giaTri(n: Nhap, menhGia: number[]): { tong: number | null; dem: Record<string, number> | null } {
  if (!n.theoTo) return { tong: docSoTien(n.tongChu), dem: null };
  const dem: Record<string, number> = {};
  let tong = 0;
  for (const mg of menhGia) {
    const so = Number((n.to[String(mg)] ?? "").replace(/[^\d]/g, "") || 0);
    if (so > 0) {
      dem[String(mg)] = so;
      tong += so * mg;
    }
  }
  return { tong, dem };
}

function BangNhapTien({ nhan, menhGia, gt, onDoi }: {
  nhan: string; menhGia: number[]; gt: Nhap; onDoi: (n: Nhap) => void;
}) {
  const { tong } = giaTri(gt, menhGia);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <ChipChon kieu="mot" ten={`${nhan}-cach`} chon={!gt.theoTo} onDoi={() => onDoi({ ...gt, theoTo: false })}>
          Gõ tổng
        </ChipChon>
        <ChipChon kieu="mot" ten={`${nhan}-cach`} chon={gt.theoTo} onDoi={() => onDoi({ ...gt, theoTo: true })}>
          Đếm theo mệnh giá
        </ChipChon>
      </div>
      {gt.theoTo ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {menhGia.map((mg) => (
            <label key={mg} className="flex items-center justify-between gap-2 text-meta text-ink-soft">
              <span className="tabular-nums">{mg.toLocaleString("vi-VN")}đ ×</span>
              <ONhap
                inputMode="numeric"
                value={gt.to[String(mg)] ?? ""}
                onChange={(e) => onDoi({ ...gt, to: { ...gt.to, [String(mg)]: e.target.value } })}
                placeholder="số tờ"
                aria-label={`Số tờ ${mg.toLocaleString("vi-VN")}đ`}
                className="w-20 text-right tabular-nums"
              />
            </label>
          ))}
        </div>
      ) : (
        <ONhap
          inputMode="numeric"
          value={gt.tongChu}
          onChange={(e) => onDoi({ ...gt, tongChu: e.target.value })}
          placeholder="vd 2000000 hoặc 2000k"
          aria-label={nhan}
          className="w-48 text-right tabular-nums"
        />
      )}
      <p className="text-meta text-ink-muted">
        {nhan}: <span className="font-semibold tabular-nums text-ink">{tien(tong)}</span>
      </p>
    </div>
  );
}

async function docKet(q: string): Promise<{ xem: XemKet | null; loi: string | null }> {
  try {
    const r = await fetch(`/api/reports/ket-tien-mat?${q}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as XemKet | null;
    if (!r.ok || !d) return { xem: null, loi: loiDocDuoc(d, "Không đọc được két tiền mặt.") };
    return { xem: d, loi: null };
  } catch {
    return { xem: null, loi: "Mất kết nối — không đọc được két tiền mặt." };
  }
}

function Dong({ nhan, so, noiBat = false }: { nhan: string; so: string; noiBat?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1">
      <dt className="text-body text-ink-soft">{nhan}</dt>
      <dd className={`tabular-nums ${noiBat ? "text-emph font-semibold text-ink" : "text-body text-ink"}`}>{so}</dd>
    </div>
  );
}

export default function KhoiKetTienMat({ ngay, ca, coSo }: { ngay: string; ca: string; coSo: string }) {
  const [xem, setXem] = useState<XemKet | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [mo, setMo] = useState<"quy_dau" | "dem_cuoi" | "mo_lai" | null>(null);
  const [nhap, setNhap] = useState<Nhap>(NHAP_TRONG);
  const [lyDo, setLyDo] = useState("");
  const [nguoiNhan, setNguoiNhan] = useState("");
  const [xemVet, setXemVet] = useState(false);

  const q = new URLSearchParams({ ngay, ca, co_so: coSo }).toString();
  const tai = useCallback(async () => {
    const kq = await docKet(q);
    if (kq.xem) setXem(kq.xem);
    setLoi(kq.loi);
  }, [q]);
  useEffect(() => {
    let huy = false;
    void docKet(q).then((kq) => {
      if (huy) return;
      if (kq.xem) setXem(kq.xem);
      setLoi(kq.loi);
    });
    return () => {
      huy = true;
    };
  }, [q]);
  // Có lần thu / hoàn tiền mặt mới, người khác nhập két → số tự mới.
  useNgheBang(["ket_tien_mat_ca", "payment_cycle", "payment_refund", "chot_so_ca"], tai);

  async function gui(than: Record<string, unknown>) {
    setDang(true);
    setLoi(null);
    try {
      const r = await fetch("/api/reports/ket-tien-mat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ngay, ca, co_so: coSo, ...than }),
      });
      const d = (await r.json().catch(() => null)) as { ok?: boolean } | null;
      if (!r.ok || !d?.ok) {
        setLoi(loiDocDuoc(d, `Chưa lưu được (HTTP ${r.status}).`));
        return;
      }
      setMo(null);
      setNhap(NHAP_TRONG);
      setLyDo("");
      setNguoiNhan("");
      await tai();
    } catch {
      setLoi("Mất kết nối — chưa lưu.");
    } finally {
      setDang(false);
    }
  }

  if (!xem) {
    return loi ? <p role="alert" className="text-meta text-danger print:hidden">{loi}</p> : null;
  }
  const ket = xem.ket;
  const mg = xem.menh_gia;
  const { tong, dem } = giaTri(nhap, mg);
  const lechTam = mo === "dem_cuoi" && tong != null && xem.du_kien_song != null ? tong - xem.du_kien_song : null;
  const canLyDo = mo === "quy_dau" ? !!ket : mo === "dem_cuoi" ? lechTam != null && lechTam !== 0 : mo === "mo_lai";
  const duLyDo = !canLyDo || lyDo.trim().length >= 3;

  return (
    <section aria-label="Tiền mặt két" className="space-y-3 rounded-control border border-line bg-surface px-3 py-3">
      <h3 className="text-emph font-semibold text-ink">Tiền mặt két — Ca {xem.ten_ca}</h3>

      <dl className="max-w-md">
        <Dong nhan="Quỹ đầu ca" so={ket ? tien(ket.quy_dau) : "Chưa nhập"} />
        <Dong nhan="Thu tiền mặt trong ca" so={tien(xem.tien_mat.thu)} />
        <Dong nhan="Huỷ phiếu tiền mặt" so={xem.tien_mat.huy ? `−${tien(xem.tien_mat.huy)}` : "0đ"} />
        <Dong nhan="Trả lại tiền mặt" so={xem.tien_mat.hoan ? `−${tien(xem.tien_mat.hoan)}` : "0đ"} />
        <Dong nhan="Dự kiến trong két (quỹ đầu + thực thu tiền mặt)" so={tien(ket?.da_dem ? ket.du_kien : xem.du_kien_song)} noiBat />
        {ket?.da_dem ? (
          <>
            <Dong nhan="Đếm thực tế cuối ca" so={tien(ket.dem_cuoi)} noiBat />
            <Dong nhan="Lệch" so={tienLech(ket.lech ?? 0)} noiBat />
          </>
        ) : null}
      </dl>
      {ket?.da_dem ? (
        <p className="text-meta text-ink-muted">
          Đếm lúc {gio(ket.dem_luc)}{ket.dem_boi_ten ? ` · ${ket.dem_boi_ten}` : ""}
          {ket.ly_do_lech ? ` · lý do lệch: “${ket.ly_do_lech}”` : ""}
          {ket.nguoi_nhan ? ` · bàn giao cho ${ket.nguoi_nhan}` : ""}.
          {xem.du_kien_song != null && ket.du_kien !== xem.du_kien_song
            ? ` Sau khi đếm có thêm thu / huỷ tiền mặt: dự kiến hiện tại ${tien(xem.du_kien_song)} — mở lại để đếm lại nếu cần.`
            : ""}
        </p>
      ) : null}

      {mo ? (
        <div className="space-y-2 border-t border-line pt-3 print:hidden">
          {mo === "quy_dau" && xem.goi_y_quy_dau && !ket ? (
            <p className="flex flex-wrap items-center gap-2 text-meta text-ink-muted">
              Cuối ca {xem.goi_y_quy_dau.ten_ca} ngày {xem.goi_y_quy_dau.ngay.split("-").reverse().join("/")} đếm được{" "}
              {tien(xem.goi_y_quy_dau.so_tien)}
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => setNhap({ theoTo: false, tongChu: String(xem.goi_y_quy_dau?.so_tien ?? ""), to: {} })}
              >
                Dùng số này
              </Button>
            </p>
          ) : null}
          {mo !== "mo_lai" ? (
            <BangNhapTien nhan={mo === "quy_dau" ? "Quỹ đầu ca" : "Tiền mặt đếm được"} menhGia={mg} gt={nhap} onDoi={setNhap} />
          ) : null}
          {lechTam != null ? (
            <p className={`text-body font-semibold ${lechTam === 0 ? "text-success" : "text-warning"}`}>Lệch: {tienLech(lechTam)}</p>
          ) : null}
          {canLyDo ? (
            <ONhap
              value={lyDo}
              onChange={(e) => setLyDo(e.target.value)}
              maxLength={500}
              placeholder={mo === "dem_cuoi" ? "Lý do lệch (bắt buộc) — vd: trả lại khách 50k chưa ghi" : "Lý do (bắt buộc)"}
              aria-label="Lý do"
              className="w-full"
            />
          ) : null}
          {mo === "dem_cuoi" ? (
            <ONhap
              value={nguoiNhan}
              onChange={(e) => setNguoiNhan(e.target.value)}
              maxLength={120}
              placeholder="Người nhận bàn giao (không bắt buộc)"
              aria-label="Người nhận bàn giao"
              className="w-full sm:w-80"
            />
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="primary"
              disabled={dang || !duLyDo || (mo !== "mo_lai" && tong == null)}
              onClick={() =>
                void gui(
                  mo === "mo_lai"
                    ? { hanh_dong: "mo_lai", ly_do: lyDo }
                    : mo === "quy_dau"
                      ? { hanh_dong: "quy_dau", tong, dem, ly_do: lyDo || null }
                      : { hanh_dong: "dem_cuoi", tong, dem, ly_do_lech: lyDo || null, nguoi_nhan: nguoiNhan || null },
                )
              }
            >
              {dang ? "Đang lưu…" : mo === "mo_lai" ? "Mở lại két" : mo === "quy_dau" ? "Lưu quỹ đầu" : "Lưu kiểm kê cuối ca"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setMo(null)}>
              Thôi
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2 print:hidden">
          {!ket?.da_dem ? (
            <Button type="button" size="sm" variant={ket ? "ghost" : "primary"} onClick={() => setMo("quy_dau")}>
              {ket ? "Sửa quỹ đầu" : "Nhập quỹ đầu ca"}
            </Button>
          ) : null}
          {ket && !ket.da_dem ? (
            <Button type="button" size="sm" variant="primary" onClick={() => setMo("dem_cuoi")}>
              Kiểm kê cuối ca
            </Button>
          ) : null}
          {ket?.da_dem ? (
            <Button type="button" size="sm" variant="secondary" onClick={() => setMo("mo_lai")}>
              Mở lại để đếm lại
            </Button>
          ) : null}
          {xem.lich_su.length ? (
            <Button type="button" size="sm" variant="ghost" onClick={() => setXemVet((v) => !v)}>
              {xemVet ? "Ẩn lịch sử két" : `Lịch sử két (${xem.lich_su.length})`}
            </Button>
          ) : null}
        </div>
      )}
      {xemVet ? (
        <ul className="space-y-1 border-t border-line pt-2 text-meta text-ink-muted">
          {xem.lich_su.map((h, i) => (
            <li key={i}>
              {gio(h.luc)} · {TEN_VIEC[h.hanh_dong] ?? h.hanh_dong}
              {h.boi ? ` · ${h.boi}` : ""} · quỹ đầu {tien(h.ban_chup.quy_dau)}
              {h.ban_chup.dem_cuoi != null ? ` · đếm ${tien(h.ban_chup.dem_cuoi)} · lệch ${tienLech(h.ban_chup.lech ?? 0)}` : ""}
              {h.ly_do ? ` · “${h.ly_do}”` : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}

/** Báo cáo cả ngày / nhiều ngày: két từng ca (số chụp lúc đếm cuối). */
export function KetTienMatNgay({ ds }: { ds: KetCa[] }) {
  if (!ds.length) return null;
  return (
    <section aria-label="Tiền mặt két theo ca" className="space-y-2">
      <h3 className="bg-surface-muted px-3 py-3 text-body font-medium text-ink-muted">Tiền mặt két</h3>
      <ul className="divide-y divide-hairline">
        {ds.map((k) => (
          <li key={k.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-3 py-2 text-body">
            <span className="min-w-0 text-ink">
              {k.ngay.split("-").reverse().join("/")} · Ca {k.ten_ca}
              {k.ten_co_so ? ` · ${k.ten_co_so}` : ""}
            </span>
            <span className="tabular-nums text-ink-soft">
              Quỹ đầu {tien(k.quy_dau)}
              {k.da_dem ? ` · Dự kiến ${tien(k.du_kien)} · Đếm ${tien(k.dem_cuoi)} · Lệch ${tienLech(k.lech ?? 0)}` : " · chưa kiểm kê cuối ca"}
            </span>
            {k.ly_do_lech ? <span className="basis-full text-meta text-ink-muted">Lý do lệch: {k.ly_do_lech}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
