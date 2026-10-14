"use client";

// Danh sách hoá đơn (Tuyền duyệt bản mẫu v8, 13/10/2026): màn để NGƯỜI ĐỐI SOÁT
// XEM toàn cảnh — không có nút xử lý. Quầy / CSKH xử lý bằng nút có sẵn ở quầy
// thu thì "việc còn tồn" tự hết. Mọi con số do máy chủ tính; màn chỉ vẽ và cộng
// dòng TỔNG của chính các dòng đang hiện.

import { useEffect, useState, type ReactNode } from "react";
import { buttonClass } from "@/components/ui/Button";
import { ChonCoSoO, type CoSo } from "@/components/ui/ChonCoSo";
import LichKhoangNgay from "@/components/ui/LichKhoangNgay";
import ThanhTab from "@/components/ui/ThanhTab";
import { todayVn } from "@/lib/roster";
import { khoangNhanh, type Khoang } from "@/lib/thanh-ngay";
import Link from "next/link";
import { coQuyen } from "@/lib/quyen-client";
import { INPUT } from "../form-ui";
import { useQuyen } from "../QuyenContext";
import NgayTrucBaoCao, { type ReportCalendar } from "../reports/NgayTrucBaoCao";
import ChiTietHoaDon from "./ChiTietHoaDon";
import { NHOM_HOA_DON, TEN_LECH, TRANG_THAI, daTon, ngayGio, tien, type DanhSachData, type KhachHoaDon, type ViecTon } from "./types";

type Tab = "khach" | "ton";

function OLoc({ ten, children, className = "" }: { ten: string; children: ReactNode; className?: string }) {
  return (
    <label className={`min-w-0 space-y-1 text-meta text-ink-muted ${className}`}>
      <span className="block">{ten}</span>
      {children}
    </label>
  );
}

function SoTien({ ten, so }: { ten: string; so: ReactNode }) {
  return (
    <div>
      <dt className="text-meta text-ink-muted">{ten}</dt>
      <dd className="tabular-nums text-emph font-semibold text-ink">{so}</dd>
    </div>
  );
}

/** Đã thu: số tổng + hai dòng Dịch vụ / Thuốc cố định cột (nhãn trái, số phải). */
function DaThu({ k }: { k: KhachHoaDon }) {
  const hang = "grid grid-cols-[3.5rem_5.5rem] justify-end gap-x-1.5";
  return (
    <div className="tabular-nums">
      <div className={hang}><span className="col-start-2 text-right">{tien(k.da_thu)}</span></div>
      <div className={`${hang} text-meta text-ink-muted`}><span>Dịch vụ</span><span className="text-right">{(k.da_thu_dich_vu ?? 0).toLocaleString("vi-VN")}</span></div>
      <div className={`${hang} text-meta text-ink-muted`}><span>Thuốc</span><span className="text-right">{(k.da_thu_thuoc ?? 0).toLocaleString("vi-VN")}</span></div>
    </div>
  );
}

const CHIP = "inline-block rounded-chip px-2 py-0.5 text-meta font-medium";
/** Việc tồn là tiền phòng khám đang nợ khách → tô đỏ. */
/** Nút "Xử lý" của một việc tồn: đích do MÁY CHỦ quyết (`xu_ly`); màn chỉ vẽ.
 *  Thiếu lego của màn đích → chữ nhắc thay vì nút (máy chủ vẫn tự kiểm quyền). */
function NutXuLy({ v, quyen }: { v: ViecTon; quyen: readonly string[] | null }) {
  const x = v.xu_ly;
  if (!x) return null;
  if (!x.href) return <p className="max-w-xs text-meta text-ink-muted">{x.huong_dan}</p>;
  if (x.lego && !coQuyen(quyen, x.lego)) {
    return <span className="text-meta text-ink-muted">Nhờ người có quyền thu xử lý</span>;
  }
  return (
    <div className="space-y-1">
      <Link href={x.href} className={buttonClass("secondary", "sm")}>{x.nhan ?? "Xử lý"}</Link>
      {x.huong_dan ? <p className="max-w-xs text-meta text-ink-muted">{x.huong_dan}</p> : null}
    </div>
  );
}

function TrangThai({ k }: { k: KhachHoaDon }) {
  const ton = k.viec_ton ?? [];
  return (
    <div className="flex flex-col items-start gap-1">
      {ton.length ? (
        <span className={`${CHIP} bg-surface-muted text-ink-soft`}>
          {ton.length} việc tồn · {ton[0].ten_loai.toLowerCase()} {tien(ton[0].so_tien)}
        </span>
      ) : (
        <span className={`${CHIP} ${k.trang_thai === "DA_THU" ? "bg-success-bg text-success" : "bg-surface-muted text-ink-soft"}`}>
          {TRANG_THAI[k.trang_thai] ?? k.trang_thai}
        </span>
      )}
      {k.co_phieu_huy ? <span className={`${CHIP} bg-surface-muted text-ink-soft`}>có phiếu huỷ</span> : null}
      {[...new Set(k.phieu.flatMap(p => p.ten_lech ?? []))].filter(t => t !== "Huỷ phiếu").map(t => (
        <span key={t} className={`${CHIP} bg-surface-muted text-ink-soft`}>{t.toLowerCase()}</span>
      ))}
      {(k.canh_bao ?? []).filter(c => !c.startsWith("Phiếu huỷ")).map(c => (
        <span key={c} className={`${CHIP} bg-surface-muted text-ink-soft`}>{c}</span>
      ))}
    </div>
  );
}

/** Bộ lọc mở sẵn từ link (khối Dòng tiền của báo cáo cuối ngày). */
export interface LocBanDau {
  tu?: string; den?: string; ca?: string; co_so?: string;
  nhom?: string; hinh_thuc?: string; loai?: string;
  /** `viec-ton` = mở tab Việc tồn; `viec` = nhóm (`no_khach` / `no_phong_kham`) hoặc mã loại. */
  tab?: string; viec?: string;
}

export default function DanhSachHoaDon({ coSo, banDau = {} }: { coSo: CoSo[]; banDau?: LocBanDau }) {
  const homNay = todayVn();
  const [khoang, setKhoang] = useState<Khoang>({ tu: banDau.tu ?? homNay, den: banDau.den ?? banDau.tu ?? homNay });
  const [tim, setTim] = useState("");
  const [loai, setLoai] = useState(banDau.loai ?? "");
  const [trangThai, setTrangThai] = useState("");
  const [ca, setCa] = useState(banDau.ca || "FULL");
  const [coSoChon, setCoSoChon] = useState(banDau.co_so ?? "");
  const [nhom, setNhom] = useState(banDau.nhom && banDau.nhom in NHOM_HOA_DON ? banDau.nhom : "");
  const [hinhThuc, setHinhThuc] = useState(banDau.hinh_thuc ?? "");
  const [tab, setTab] = useState<Tab>(banDau.tab === "viec-ton" ? "ton" : "khach");
  const [viec, setViec] = useState(banDau.viec ?? "");
  const quyen = useQuyen();
  const [access, setAccess] = useState<ReportCalendar | null>(null);
  const [data, setData] = useState<DanhSachData | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(true);
  const [khach, setKhach] = useState<KhachHoaDon | null>(null);
  const restricted = !!access && !access.legacy && !access.quan_ly;
  const { tu, den } = khoang;
  // "Cần kiểm tra" là bộ lọc riêng của máy chủ, gửi bằng can_kiem_tra.
  const canKiemTra = trangThai === "CAN_KIEM_TRA";
  const query = new URLSearchParams({
    tu, den, tim, loai, ca, co_so: coSoChon,
    trang_thai: canKiemTra ? "" : trangThai,
    can_kiem_tra: String(canKiemTra),
    nhom, hinh_thuc: hinhThuc,
  });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/reports/access?ngay=${encodeURIComponent(tu)}`, { cache: "no-store", signal: controller.signal })
      .then(async r => { if (!r.ok) throw new Error("Không đọc được phạm vi xem báo cáo."); return r.json(); })
      .then((a: ReportCalendar) => { setAccess(a); })
      .catch(e => { if (!controller.signal.aborted) setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); });
    return () => controller.abort();
  }, [tu]);

  const chuoi = query.toString();
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setDangTai(true); setLoi(null);
      try {
        const r = await fetch(`/api/hoa-don?${chuoi}`, { cache: "no-store", signal: controller.signal });
        const d = await r.json();
        if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Không đọc được danh sách hoá đơn trong phạm vi đã chọn.");
        if (!controller.signal.aborted) setData(d);
      } catch (e) {
        if (!controller.signal.aborted) setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ.");
      } finally { if (!controller.signal.aborted) setDangTai(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [chuoi]);

  const ds = data?.khach ?? [];
  const tonDay = data?.viec_ton ?? [];
  // Lọc Ở MÀN chỉ để thu hẹp danh sách (không tính tiền): nhóm do máy chủ gắn.
  const ton = viec ? tonDay.filter(v => v.nhom_no === viec || v.loai === viec) : tonDay;
  const tk = data?.tong_khach;
  const moKhach = (patientId: string | null) => {
    const k = ds.find(x => x.id === patientId);
    if (k) setKhach(k);
  };

  return (
    <div className="min-w-0 space-y-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-[1.3fr_1fr_1fr_1fr]">
        {!restricted ? (
          <OLoc ten="Ngày">
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
        ) : null}
        <OLoc ten="Ca">
          <select aria-label="Ca" className={`${INPUT} w-full`} value={ca} onChange={e => setCa(e.target.value)}>
            <option value="FULL">Cả ngày</option>
            {["SANG", "CHIEU", "TOI"].map((v, i) => <option key={v} value={v}>{["Sáng", "Chiều", "Tối"][i]}</option>)}
          </select>
        </OLoc>
        <OLoc ten="Cơ sở">
          <ChonCoSoO coSo={restricted ? coSo.filter(c => access.co_so_ids.includes(c.id)) : coSo} dangChon={coSoChon} onChon={setCoSoChon} className="w-full" />
        </OLoc>
        <div className="flex items-end">
          <a href={`/api/hoa-don?${chuoi}&xuat=xlsx`} className={`${buttonClass("secondary", "md")} w-full justify-center`}>Xuất Excel (.xlsx)</a>
        </div>
        <OLoc ten="Tìm khách / mã phiếu" className="lg:col-span-2">
          <input aria-label="Tìm khách hoặc mã phiếu" className={`${INPUT} w-full`} value={tim} onChange={e => setTim(e.target.value)} placeholder="Tên, mã khách, SĐT, mã phiếu" />
        </OLoc>
        <OLoc ten="Loại hoá đơn">
          <select aria-label="Loại hoá đơn" className={`${INPUT} w-full`} value={loai} onChange={e => setLoai(e.target.value)}>
            <option value="">Dịch vụ và thuốc</option>
            <option value="dich_vu">Dịch vụ</option>
            <option value="thuoc">Thuốc</option>
          </select>
        </OLoc>
        <OLoc ten="Nhóm hoá đơn">
          <select aria-label="Nhóm hoá đơn" className={`${INPUT} w-full`} value={nhom} onChange={e => setNhom(e.target.value)}>
            <option value="">Mọi hoá đơn</option>
            {Object.entries(NHOM_HOA_DON).map(([ma, ten]) => <option key={ma} value={ma}>{ten}</option>)}
          </select>
        </OLoc>
        <OLoc ten="Hình thức">
          <select aria-label="Hình thức thu" className={`${INPUT} w-full`} value={hinhThuc} onChange={e => setHinhThuc(e.target.value)}>
            <option value="">Tiền mặt và chuyển khoản</option>
            <option value="CASH">Tiền mặt</option>
            <option value="TRANSFER">Chuyển khoản</option>
          </select>
        </OLoc>
        <OLoc ten="Trạng thái">
          <select aria-label="Trạng thái" className={`${INPUT} w-full`} value={trangThai} onChange={e => setTrangThai(e.target.value)}>
            <option value="">Tất cả trạng thái</option>
            {Object.entries(TRANG_THAI).filter(([ma]) => ma !== "HON_HOP").map(([ma, ten]) => <option key={ma} value={ma}>{ten}</option>)}
            <option value="CON_VIEC_TON">Còn việc tồn</option>
            <option value="CAN_KIEM_TRA">Cần kiểm tra</option>
          </select>
        </OLoc>
      </div>
      {restricted ? <NgayTrucBaoCao access={access} ngay={tu} onChon={v => setKhoang({ tu: v, den: v })} /> : null}
      {loi ? <p role="alert" className="rounded-control bg-danger-bg p-3 text-body text-danger">{loi}</p> : null}
      {dangTai && !data ? <p role="status" className="text-body text-ink-muted">Đang tải hoá đơn…</p> : null}

      {data ? (
        <>
          {data.tong.dung_khong_dung ? (
            <div className="flex flex-wrap items-center gap-2 text-body">
              <button type="button" onClick={() => setNhom("dung")} className={`${CHIP} bg-success-bg text-success`}>
                Đúng {data.tong.dung_khong_dung.dung} hoá đơn
              </button>
              <button type="button" onClick={() => setNhom("khong_dung")} className={`${CHIP} bg-surface-muted text-ink-soft`}>
                Không đúng {data.tong.dung_khong_dung.khong_dung} hoá đơn
              </button>
              {Object.entries(data.tong.dung_khong_dung.ly_do).filter(([, n]) => n > 0).map(([ma, n]) => (
                <span key={ma} className="text-meta text-ink-muted">{TEN_LECH[ma] ?? ma} {n}</span>
              ))}
              {nhom ? <button type="button" onClick={() => setNhom("")} className="text-meta text-brand-700 underline-offset-2 hover:underline">Bỏ lọc nhóm</button> : null}
            </div>
          ) : null}
          <dl className="grid grid-cols-2 gap-4 rounded-card bg-surface p-4 ring-1 ring-hairline md:grid-cols-4">
            <SoTien ten="Tổng tiền hàng" so={tien(data.tong.tong_truoc_giam)} />
            <SoTien ten="Giảm giá" so={tien(data.tong.giam_gia)} />
            <SoTien ten="Tiền đã thu" so={tien(data.tong.da_thu)} />
            <SoTien ten="Phiếu huỷ" so={tien(data.tong.gia_tri_huy ?? 0)} />
            <SoTien ten="Đã trả lại khách" so={tien(data.tong.da_hoan)} />
            <SoTien ten="Thực thu" so={tien(data.tong.thu_rong)} />
            <SoTien ten="Chưa trả lại khách" so={tien(data.tong.chua_tra_lai ?? 0)} />
            <SoTien ten="Việc còn tồn" so={`${data.tong.so_viec_ton ?? tonDay.length} việc`} />
          </dl>

          <div className="flex justify-end">
            <ThanhTab<Tab>
              nhan="Xem theo"
              chon={tab}
              onChon={setTab}
              muc={[{ ma: "khach", nhan: "Theo khách" }, { ma: "ton", nhan: "Việc còn tồn", dem: tonDay.length }]}
            />
          </div>

          {tab === "khach" ? (
            <>
              {!ds.length ? <p className="rounded-card bg-surface p-4 text-body text-ink-muted ring-1 ring-hairline">Không có hoá đơn trong phạm vi đã chọn.</p> : null}
              {ds.length ? (
                <div className="hidden overflow-x-auto rounded-card bg-surface ring-1 ring-hairline md:block">
                  <table className="w-full text-body">
                    <thead className="bg-surface-muted text-left text-meta text-ink-muted">
                      <tr>
                        {["Khách hàng", "Số phiếu", "Giảm giá", "Tiền đã thu", "Đã trả lại", "Chưa trả lại", "Thực thu", "Trạng thái"].map((t, i) => (
                          <th key={t} className={`px-3 py-2 font-semibold ${i > 0 && i < 7 ? "text-right" : ""}`}>{t}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {ds.map(k => (
                        <tr key={k.id} className="border-t border-hairline align-top hover:bg-surface-muted">
                          <td className="px-3 py-3">
                            <button type="button" onClick={() => setKhach(k)} className="text-left font-semibold text-brand-700 hover:underline focus-visible:underline">{k.ten}</button>
                            <span className="block text-meta text-ink-muted">{k.ma_bn || "—"} · {k.so_dien_thoai || "—"}</span>
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums">{k.so_phieu}</td>
                          <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(k.giam_gia)}</td>
                          <td className="whitespace-nowrap px-3 py-3 text-right"><DaThu k={k} /></td>
                          <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(k.da_hoan)}</td>
                          <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">
                            {tien(k.chua_tra_lai ?? 0)}
                            {k.cho_hoan > 0 ? <span className="block text-meta font-normal text-ink-muted">gồm hoàn đang chờ {tien(k.cho_hoan)}</span> : null}
                          </td>
                          <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(k.thu_rong)}</td>
                          <td className="px-3 py-3"><TrangThai k={k} /></td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="border-t-2 border-line bg-surface-muted font-semibold">
                      <tr>
                        <td className="px-3 py-3">TỔNG</td>
                        <td className="px-3 py-3 text-right tabular-nums">{tk?.so_phieu ?? 0}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(tk?.giam_gia ?? 0)}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(tk?.da_thu ?? 0)}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(tk?.da_hoan ?? 0)}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(tk?.chua_tra_lai ?? 0)}</td>
                        <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(tk?.thu_rong ?? 0)}</td>
                        <td className="px-3 py-3 text-meta font-normal text-ink-muted">{tk?.so_khach_con_ton ?? 0} khách còn việc tồn</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              ) : null}
              <div className="space-y-3 md:hidden">
                {ds.map(k => (
                  <button type="button" key={k.id} onClick={() => setKhach(k)} className="block w-full rounded-card bg-surface p-4 text-left ring-1 ring-hairline">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <span className="text-emph font-semibold text-brand-700">{k.ten}</span>
                      <TrangThai k={k} />
                    </div>
                    <p className="mt-1 text-meta text-ink-muted">{k.ma_bn || "—"} · {k.so_phieu} phiếu</p>
                    <dl className="mt-3 grid grid-cols-2 gap-3">
                      <SoTien ten="Tiền đã thu" so={tien(k.da_thu)} />
                      <SoTien ten="Thực thu" so={tien(k.thu_rong)} />
                      {(k.chua_tra_lai ?? 0) > 0 ? <SoTien ten="Chưa trả lại" so={tien(k.chua_tra_lai ?? 0)} /> : null}
                    </dl>
                  </button>
                ))}
                {ds.length ? (
                  <div className="grid grid-cols-2 gap-3 rounded-card bg-surface-muted p-4 font-semibold">
                    <span>TỔNG thực thu</span><span className="text-right tabular-nums">{tien(tk?.thu_rong ?? 0)}</span>
                    <span>Chưa trả lại khách</span><span className="text-right tabular-nums">{tien(tk?.chua_tra_lai ?? 0)}</span>
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <>
              {tonDay.length ? (
                <OLoc ten="Loại việc" className="max-w-xs">
                  <select aria-label="Loại việc tồn" className={`${INPUT} w-full`} value={viec} onChange={e => setViec(e.target.value)}>
                    <option value="">Mọi loại việc</option>
                    <option value="no_khach">Khách còn nợ phòng khám</option>
                    <option value="no_phong_kham">Phòng khám còn nợ khách</option>
                    {[...new Map(tonDay.map(v => [v.loai, v.ten_loai])).entries()].map(([ma, ten]) => <option key={ma} value={ma}>{ten}</option>)}
                  </select>
                </OLoc>
              ) : null}
              {!ton.length ? <p className="rounded-card bg-surface p-4 text-body text-ink-muted ring-1 ring-hairline">{tonDay.length ? "Không có việc tồn thuộc loại đã chọn." : "Không còn việc tồn."}</p> : null}
              {ton.length ? (
                <div className="hidden overflow-x-auto rounded-card bg-surface ring-1 ring-hairline md:block">
                  <table className="w-full text-body">
                    <thead className="bg-surface-muted text-left text-meta text-ink-muted">
                      <tr>{["Phát sinh", "Khách", "Việc", "Số tiền", "Đã tồn", "Xử lý"].map((t, i) => <th key={t} className={`px-3 py-2 font-semibold ${i === 3 ? "text-right" : ""}`}>{t}</th>)}</tr>
                    </thead>
                    <tbody>
                      {ton.map((v, i) => {
                        const coTrongDs = ds.some(k => k.id === v.patient_id);
                        return (
                          <tr key={`${v.loai}-${v.visit_id}-${v.ma}-${i}`} className="border-t border-hairline align-top">
                            <td className="px-3 py-3 whitespace-nowrap">{ngayGio(v.luc)}<span className="block text-meta text-ink-muted">{v.ma ?? ""}</span></td>
                            <td className="px-3 py-3">
                              {coTrongDs ? (
                                <button type="button" onClick={() => moKhach(v.patient_id)} className="text-left font-semibold text-brand-700 hover:underline">{v.ten ?? "—"}</button>
                              ) : <span className="font-semibold">{v.ten ?? "—"}</span>}
                              <span className="block text-meta text-ink-muted">{v.ma_bn ?? "—"}</span>
                            </td>
                            <td className="px-3 py-3">
                              <span className={`${CHIP} bg-surface-muted text-ink-soft`}>{v.ten_loai}</span>
                              {v.mo_ta || v.nguoi ? <span className="mt-1 block text-meta text-ink-muted">{[v.mo_ta, v.nguoi].filter(Boolean).join(" · ")}</span> : null}
                            </td>
                            <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums">{tien(v.so_tien)}</td>
                            <td className="px-3 py-3 whitespace-nowrap">{daTon(v.luc)}</td>
                            <td className="px-3 py-3"><NutXuLy v={v} quyen={quyen} /></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
              <div className="space-y-3 md:hidden">
                {ton.map((v, i) => (
                  <article key={`${v.loai}-${v.visit_id}-${v.ma}-${i}`} className="rounded-card bg-surface p-4 ring-1 ring-hairline">
                    <div className="flex items-start justify-between gap-2">
                      <span className={`${CHIP} bg-surface-muted text-ink-soft`}>{v.ten_loai}</span>
                      <b className="tabular-nums">{tien(v.so_tien)}</b>
                    </div>
                    <p className="mt-1 text-meta text-ink-muted">{v.ten ?? "—"} · {daTon(v.luc)}{v.mo_ta ? ` · ${v.mo_ta}` : ""}</p>
                    <div className="mt-2"><NutXuLy v={v} quyen={quyen} /></div>
                  </article>
                ))}
              </div>
            </>
          )}
        </>
      ) : null}
      {khach ? <ChiTietHoaDon khach={khach} onDong={() => setKhach(null)} /> : null}
    </div>
  );
}
