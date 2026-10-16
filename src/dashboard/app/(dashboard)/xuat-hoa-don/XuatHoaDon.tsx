"use client";

// Xuất hoá đơn (Tuyền 13/10/2026): kế toán tải file Excel ĐÚNG mẫu nhập hoá đơn
// GTGT (MISA) thay vì gõ tay từng phiếu thu. Máy chủ dựng hoá đơn và file từ
// chính tệp mẫu; màn chỉ chọn phạm vi, xem trước và tải.

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import Button, { buttonClass } from "@/components/ui/Button";
import { ChonCoSoO, type CoSo } from "@/components/ui/ChonCoSo";
import LichKhoangNgay from "@/components/ui/LichKhoangNgay";
import { todayVn } from "@/lib/roster";
import { khoangNhanh, type Khoang } from "@/lib/thanh-ngay";
import { INPUT } from "../form-ui";
import CongTac from "@/components/ui/CongTac";
import OChon from "@/components/ui/OChon";
import { MUC_THUE, tenThueSuat, TEN_NGUON_THUE } from "../ke-toan/thue-suat";
import LanXuatMisa from "./LanXuatMisa";
import { tien } from "../hoa-don/types";

type DongHang = {
  id: string; ten: string; dvt: string; so_luong: number; don_gia: number; thanh_tien: number;
  /** Thuế suất của dòng + tầng quyết định (sửa tay / mặt hàng / nhóm) — máy chủ tính. */
  thue_suat: string | null; thue_nguon: string | null;
};
type HoaDon = {
  stt: number; ma_phieu: string; kind: string; ngay: string; ten_khach: string; ma_bn: string | null;
  so_dien_thoai: string; hinh_thuc: string; dong: DongHang[]; tong: number; ghi_chu: string[];
  /** Hoá đơn công ty (G5c): tên + MST của công ty thay cho thông tin khách cá nhân. */
  la_hd_cong_ty: boolean; ten_cong_ty: string; ma_so_thue: string; nguoi_mua?: string;
  /** Thuế GTGT của hoá đơn (sau khi tách): mã chung, tiền hàng chưa thuế, tiền thuế. */
  thue_suat_ma: string; tien_hang: number | null; tien_thue: number | null;
  /** Đã đánh dấu xuất sang MISA chưa; có thay đổi sau khi xuất không + lý do (máy chủ so). */
  misa: { xuat_id: string; xuat_luc: string; xuat_boi: string | null; co_thay_doi: boolean; ly_do: string[] } | null;
};
type XuatData = {
  tu: string; den: string; hoa_don: HoaDon[]; so_hoa_don: number; so_dong: number; tong: number;
  so_da_xuat_misa: number; so_co_thay_doi_sau_xuat: number;
  dong_chua_thue: number; tien_thue: number;
};

function OLoc({ ten, children }: { ten: string; children: ReactNode }) {
  return (
    <label className="min-w-0 space-y-1 text-meta text-ink-muted">
      <span className="block">{ten}</span>
      {children}
    </label>
  );
}

function DongHangGon({ dong, ghiDe, onThue }: {
  dong: DongHang[]; ghiDe: Record<string, string>; onThue: (id: string, ma: string) => void;
}) {
  return (
    <ul className="space-y-1">
      {dong.map((d, i) => (
        <li key={i} className="text-body text-ink">
          {d.ten} <span className="text-meta text-ink-muted">· {d.so_luong} {d.dvt || ""} × {d.don_gia.toLocaleString("vi-VN")}</span>
          <span className="flex flex-wrap items-center gap-2 text-meta text-ink-muted">
            Thuế: {tenThueSuat(d.thue_suat) || "chưa đặt"}{d.thue_nguon ? ` (${TEN_NGUON_THUE[d.thue_nguon] ?? d.thue_nguon})` : ""}
            {d.thanh_tien >= 0 ? (
              <OChon aria-label={`Sửa thuế suất dòng ${d.ten}`} className="w-44" value={ghiDe[d.id] ?? ""}
                onChange={e => onThue(d.id, e.target.value)}>
                <option value="">Theo cài đặt</option>
                {MUC_THUE.map(([m, ten]) => <option key={m} value={m}>{ten}</option>)}
              </OChon>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Hoá đơn công ty chỉ hiện tên công ty + MST — không SĐT / mã khách cá nhân. */
function KhachHang({ h }: { h: HoaDon }) {
  if (h.la_hd_cong_ty) {
    return <>{h.ten_cong_ty}<span className="block text-meta text-ink-muted">Công ty · MST {h.ma_so_thue || "—"} · Người mua: {h.nguoi_mua || "—"}</span></>;
  }
  return <>{h.ten_khach || "—"}<span className="block text-meta text-ink-muted">{h.ma_bn || "—"} · {h.so_dien_thoai || "—"}</span></>;
}

/** "Đã xuất MISA" + "có thay đổi sau khi xuất" của một hoá đơn — máy chủ so dấu vân tay. */
function TrangThaiMisa({ h }: { h: HoaDon }) {
  if (!h.misa) return null;
  const luc = new Date(h.misa.xuat_luc).toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
  return (
    <div className="flex flex-col items-start gap-1">
      <span className="inline-block rounded-chip bg-success-bg px-2 py-0.5 text-meta font-medium text-success">Đã xuất MISA {luc}</span>
      {h.misa.co_thay_doi ? (
        <span className="inline-block rounded-chip bg-info-bg px-2 py-0.5 text-meta font-medium text-info">
          Có thay đổi sau khi xuất — {h.misa.ly_do.join(" · ")}
        </span>
      ) : null}
    </div>
  );
}

function GhiChu({ h }: { h: HoaDon }) {
  return h.ghi_chu.length ? (
    <div className="flex flex-col items-start gap-1">
      {h.ghi_chu.map(g => <span key={g} className="inline-block rounded-chip bg-warning-bg px-2 py-0.5 text-meta font-medium text-warning">{g}</span>)}
    </div>
  ) : null;
}

export default function XuatHoaDon({ coSo }: { coSo: CoSo[] }) {
  const homNay = todayVn();
  const [khoang, setKhoang] = useState<Khoang>({ tu: homNay, den: homNay });
  const [loai, setLoai] = useState("");
  const [coSoChon, setCoSoChon] = useState("");
  const [data, setData] = useState<XuatData | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(true);
  const [lamMoi, setLamMoi] = useState(0);
  const [cheDo, setCheDo] = useState<"tach" | "mot">("tach");
  const [ghiGiamGia, setGhiGiamGia] = useState(false);
  const [ghiDe, setGhiDe] = useState<Record<string, string>>({});
  const [coQuyenMisa, setCoQuyenMisa] = useState(true);
  const [dangDanhDau, setDangDanhDau] = useState(false);
  const [vuaDanhDau, setVuaDanhDau] = useState<{ id: string; so: number } | null>(null);
  const [loiMisa, setLoiMisa] = useState<string | null>(null);
  const thamSo = new URLSearchParams({ tu: khoang.tu, den: khoang.den, loai, co_so: coSoChon, che_do: cheDo });
  if (ghiGiamGia) thamSo.set("ghi_giam_gia", "true");
  if (Object.keys(ghiDe).length) thamSo.set("ghi_de", JSON.stringify(ghiDe));
  const chuoi = thamSo.toString();
  const datThueDong = (id: string, ma: string) => setGhiDe(cu => {
    const moi = { ...cu };
    if (ma) moi[id] = ma; else delete moi[id];
    return moi;
  });

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setDangTai(true); setLoi(null);
      try {
        const r = await fetch(`/api/xuat-hoa-don?${chuoi}`, { cache: "no-store", signal: controller.signal });
        const d = await r.json();
        if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Không đọc được hoá đơn trong phạm vi đã chọn.");
        if (!controller.signal.aborted) setData(d);
      } catch (e) {
        if (!controller.signal.aborted) { setData(null); setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); }
      } finally { if (!controller.signal.aborted) setDangTai(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [chuoi, lamMoi]);

  const danhDau = async () => {
    setDangDanhDau(true); setLoiMisa(null);
    try {
      const r = await fetch("/api/xuat-hoa-don/misa", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tu: khoang.tu, den: khoang.den, loai: loai || null, co_so: coSoChon || null }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Máy chủ chưa đánh dấu được — thử lại.");
      setVuaDanhDau({ id: d.id, so: d.so_hoa_don });
      setLamMoi(n => n + 1);
    } catch (e) { setLoiMisa(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); }
    finally { setDangDanhDau(false); }
  };
  const hoanTacDanhDau = async () => {
    if (!vuaDanhDau) return;
    setDangDanhDau(true); setLoiMisa(null);
    const r = await fetch(`/api/xuat-hoa-don/misa/${vuaDanhDau.id}`, { method: "DELETE" });
    if (r.ok) { setVuaDanhDau(null); setLamMoi(n => n + 1); } else setLoiMisa("Máy chủ chưa bỏ được đánh dấu — thử lại.");
    setDangDanhDau(false);
  };

  const ds = data?.hoa_don ?? [];
  const coHoaDon = ds.length > 0;

  return (
    <div className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-body">
        <span className="rounded-chip bg-info-bg px-3 py-1 text-meta font-semibold text-info">Theo từng hoá đơn</span>
        <Link href="/ke-toan" className="rounded-chip px-3 py-1 text-meta text-ink-muted ring-1 ring-hairline hover:text-ink">Theo hàng hoá →</Link>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[1.3fr_1fr_1fr_1fr]">
        <OLoc ten="Ngày thu">
          <div className="[&>div>button]:h-10 [&>div>button]:w-full">
            <LichKhoangNgay
              khoang={khoang}
              homNay={homNay}
              nhan="Khoảng ngày"
              dangTai={dangTai}
              onChon={k => setKhoang(k ?? khoangNhanh("30-ngay", homNay) ?? { tu: homNay, den: homNay })}
            />
          </div>
        </OLoc>
        <OLoc ten="Loại hoá đơn">
          <select aria-label="Loại hoá đơn" className={`${INPUT} w-full`} value={loai} onChange={e => setLoai(e.target.value)}>
            <option value="">Dịch vụ và thuốc</option>
            <option value="dich_vu">Dịch vụ</option>
            <option value="thuoc">Thuốc</option>
          </select>
        </OLoc>
        <OLoc ten="Cơ sở">
          <ChonCoSoO coSo={coSo} dangChon={coSoChon} onChon={setCoSoChon} className="w-full" />
        </OLoc>
        <div className="flex items-end">
          {coHoaDon ? (
            <a href={`/api/xuat-hoa-don?${chuoi}&xuat=xlsx`} className={`${buttonClass("primary", "md")} w-full justify-center`}>
              Tải file Excel ({data?.so_hoa_don} hoá đơn)
            </a>
          ) : (
            <button type="button" disabled className={`${buttonClass("primary", "md")} w-full justify-center`}>Tải file Excel</button>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <OLoc ten="Phiếu có nhiều thuế suất">
          <OChon aria-label="Phiếu có nhiều thuế suất" className="w-full sm:w-64" value={cheDo} onChange={e => setCheDo(e.target.value === "mot" ? "mot" : "tach")}>
            <option value="tach">Tách thành nhiều hoá đơn theo thuế suất</option>
            <option value="mot">Giữ một hoá đơn (tổng tiền thuế)</option>
          </OChon>
        </OLoc>
        <span className="flex items-center gap-2 text-body text-ink">
          <CongTac bat={ghiGiamGia} onDoi={setGhiGiamGia} nhan="Ghi giảm giá trên hoá đơn" />
          Ghi giảm giá trên hoá đơn
        </span>
        {Object.keys(ghiDe).length ? (
          <Button size="sm" variant="ghost" onClick={() => setGhiDe({})}>Bỏ {Object.keys(ghiDe).length} thuế sửa tay</Button>
        ) : null}
      </div>
      {coHoaDon && coQuyenMisa ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => void danhDau()} disabled={dangDanhDau}>{dangDanhDau ? "Đang đánh dấu…" : "Đánh dấu đã xuất MISA"}</Button>
          <span className="text-meta text-ink-muted">Bấm sau khi đã tải file và nhập vào MISA — để biết hoá đơn nào đã xuất và hoá đơn nào đổi sau đó.</span>
        </div>
      ) : null}
      {vuaDanhDau ? (
        <p role="status" className="flex flex-wrap items-center gap-2 rounded-control bg-info-bg p-3 text-body text-info">
          Đã đánh dấu {vuaDanhDau.so} hoá đơn là đã xuất sang MISA.
          <Button size="sm" variant="ghost" disabled={dangDanhDau} onClick={() => void hoanTacDanhDau()}>Hoàn tác</Button>
        </p>
      ) : null}
      {loiMisa ? <p role="alert" className="rounded-control bg-danger-bg p-3 text-body text-danger">{loiMisa}</p> : null}
      {loi ? <p role="alert" className="rounded-control bg-danger-bg p-3 text-body text-danger">{loi}</p> : null}
      {dangTai && !data ? <p role="status" className="text-body text-ink-muted">Đang tải hoá đơn…</p> : null}

      {data ? (
        <>
          <dl className="grid grid-cols-3 gap-4 rounded-card bg-surface p-4 ring-1 ring-hairline">
            <div><dt className="text-meta text-ink-muted">Số hoá đơn</dt><dd className="tabular-nums text-emph font-semibold text-ink">{data.so_hoa_don}</dd></div>
            <div><dt className="text-meta text-ink-muted">Số dòng hàng</dt><dd className="tabular-nums text-emph font-semibold text-ink">{data.so_dong}</dd></div>
            <div><dt className="text-meta text-ink-muted">Tổng thành tiền{data.tien_thue > 0 ? ` (gồm thuế ${tien(data.tien_thue)})` : ""}</dt><dd className="tabular-nums text-emph font-semibold text-ink">{tien(data.tong)}</dd></div>
          </dl>
          {data.dong_chua_thue > 0 ? (
            <p role="status" className="rounded-control bg-info-bg p-3 text-body text-info">
              {data.dong_chua_thue} dòng hàng chưa có thuế suất — cột thuế trong file để trống.{" "}
              <Link href="/ke-toan" className="font-semibold underline">Đặt thuế suất ở Kế toán</Link>
              {" "}hoặc chọn mức cho từng dòng bên dưới (chỉ áp cho lần xuất này).
            </p>
          ) : null}
          {data.so_da_xuat_misa > 0 ? (
            <p role="status" className="rounded-control bg-info-bg p-3 text-body text-info">
              Đã xuất MISA: {data.so_da_xuat_misa}/{data.so_hoa_don} hoá đơn
              {data.so_co_thay_doi_sau_xuat > 0 ? ` · ${data.so_co_thay_doi_sau_xuat} hoá đơn có thay đổi sau khi xuất — mở “Các lần đã xuất” bên dưới để xem` : ""}.
            </p>
          ) : null}
          <p className="text-meta text-ink-muted">Đây là Màn hình xem nhanh, tải file excel để xem chi tiết!</p>

          {!coHoaDon ? <p className="rounded-card bg-surface p-4 text-body text-ink-muted ring-1 ring-hairline">Không có phiếu thu trong phạm vi đã chọn.</p> : null}
          {coHoaDon ? (
            <div className="hidden overflow-x-auto rounded-card bg-surface ring-1 ring-hairline md:block">
              <table className="w-full text-body">
                <thead className="bg-surface-muted text-left text-meta text-ink-muted">
                  <tr>
                    {["STT", "Ngày", "Khách hàng", "Hình thức", "Hàng hoá / dịch vụ", "Thành tiền", "Ghi chú"].map((t, i) => (
                      <th key={t} className={`px-3 py-2 font-semibold ${i === 0 || i === 5 ? "text-right" : ""}`}>{t}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ds.map(h => (
                    <tr key={h.ma_phieu} className="border-t border-hairline align-top">
                      <td className="px-3 py-3 text-right tabular-nums">{h.stt}</td>
                      <td className="whitespace-nowrap px-3 py-3 tabular-nums">{h.ngay}<span className="block text-meta text-ink-muted">{h.ma_phieu}</span></td>
                      <td className="px-3 py-3"><KhachHang h={h} /></td>
                      <td className="whitespace-nowrap px-3 py-3">{h.hinh_thuc || "—"}</td>
                      <td className="px-3 py-3"><DongHangGon dong={h.dong} ghiDe={ghiDe} onThue={datThueDong} /></td>
                      <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(h.tong)}{h.tien_thue !== null ? <span className="block text-meta text-ink-muted">Thuế {tenThueSuat(h.thue_suat_ma) || "nhiều mức"}: {tien(h.tien_thue)}</span> : null}</td>
                      <td className="px-3 py-3"><TrangThaiMisa h={h} /><GhiChu h={h} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <div className="space-y-3 md:hidden">
            {ds.map(h => (
              <div key={h.ma_phieu} className="rounded-card bg-surface p-4 ring-1 ring-hairline">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <span className="text-emph font-semibold text-ink">{h.stt}. {h.la_hd_cong_ty ? h.ten_cong_ty : h.ten_khach || "—"}</span>
                  <span className="tabular-nums text-emph font-semibold text-ink">{tien(h.tong)}</span>
                </div>
                <p className="text-meta text-ink-muted">{h.ngay} · {h.ma_phieu} · {h.hinh_thuc || "—"}</p>
                <div className="mt-2"><DongHangGon dong={h.dong} ghiDe={ghiDe} onThue={datThueDong} /></div>
                <div className="mt-2 space-y-1"><TrangThaiMisa h={h} /><GhiChu h={h} /></div>
              </div>
            ))}
          </div>
        </>
      ) : null}
      <LanXuatMisa lamMoi={lamMoi} onDoi={() => setLamMoi(n => n + 1)} onQuyen={setCoQuyenMisa} />
    </div>
  );
}
