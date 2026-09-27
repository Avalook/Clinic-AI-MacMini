"use client";

// Mục C (cận lâm sàng) và mục F (thủ thuật) của phiếu v5 — DANH MỤC CÓ GIÁ.
//
// KIỂU PHIẾU GIẤY — Y HỆT bản giao diện mẫu (27/09/2026, mục 4; M/app.js
// `danhMuc`, M/style.css `.dm`): mọi nhóm của phiếu chỉ định giấy LUÔN MỞ, lưới
// 3/2/1 cột; mỗi dòng [ô tick | tên | giá + chip mẫu]. Dịch vụ có trong bảng giá
// mà phiếu giấy không có (nhóm "(danh mục phòng khám)") gom vào MỘT ngăn gập
// "Dịch vụ khác trong bảng giá". Tick nhiều mục rồi bấm MỘT lần → thành chỉ định
// thật (lệnh PlaceServiceOrders).
//
// Mã dịch vụ và giá do MÁY CHỦ gắn (bảng ghép viết tay `anh_xa_danh_muc.py`) —
// màn này không so tên. Mục chưa có mã (phòng khám chưa có dịch vụ ấy) khoá lại.
//
// CHỈ ĐỊNH THÊM (Tuyền 25/09/2026): trong CÙNG một lượt khám bác sĩ chỉ định
// được 2, 3 lần — mỗi lần vẫn đi thanh toán rồi làm như lần đầu. Lượt đã có chỉ
// định thì danh mục gập sau nút [+ Chỉ định thêm (lần N)]. Hộp tóm tắt "Đã chỉ
// định — Lần 1 · …" cũ đã BỎ (27/09): thẻ "Đã chỉ định & kết quả" ngay trên
// (`KetQuaChiDinh`) gom theo lần rồi — và ô "bắt buộc" của chỉ định ĐÃ đặt
// chuyển vào thẻ ấy (mỗi chỉ định một ô, đúng thẻ của nó).
//
// CHỈ ĐỊNH LẠI (26/09/2026 — lát 4): dịch vụ đã chỉ định ở lần trước vẫn tick
// được ở lần mới (vd siêu âm lại sau thủ thuật) — tên tô brand đậm + "đã chỉ
// định ở lần n" (bản mẫu `.da-truoc`). Số lần do máy chủ gán.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import {
  chipMauDanhMuc,
  tachDanhMucKhac,
  tienVn,
  type ChiDinhVaKetQua,
  type MucCls,
  type NhomCls,
} from "@/lib/phieu-kham";

export default function DanhMucChiDinh({
  nhom,
  daDat,
  daChiDinh = [],
  onDat,
  chiDoc,
  nhanNut = "Chỉ định",
}: {
  nhom: NhomCls[];
  /** service_code đã có chỉ định (chưa huỷ) trong lượt. */
  daDat: ReadonlySet<string>;
  /** Mọi chỉ định (chưa huỷ) của lượt — để biết "đã chỉ định ở lần n". */
  daChiDinh?: readonly ChiDinhVaKetQua[];
  onDat: (
    codes: string[],
    /** Mã tick "Bắt buộc" (25/09/2026) — quầy thu không bỏ được. */
    batBuoc: string[],
  ) => Promise<{ ok: true } | { ok: false; loi: string }>;
  chiDoc: boolean;
  nhanNut?: string;
}) {
  const [chon, setChon] = useState<string[]>([]);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [moThem, setMoThem] = useState(false);
  // DỊCH VỤ BẮT BUỘC (Tuyền 25/09/2026): mặc định KHÔNG tick.
  const [batBuoc, setBatBuoc] = useState<string[]>([]);

  const { chinh, khac } = tachDanhMucKhac(nhom);
  const moiMuc = [...chinh.flatMap((n) => n.muc), ...khac];

  // Một dịch vụ có thể đã chỉ định ở nhiều lần → nhớ lần GẦN nhất.
  const lanCua = new Map<string, number>();
  for (const c of daChiDinh) {
    if (c.lan != null) lanCua.set(c.service_code, Math.max(c.lan, lanCua.get(c.service_code) ?? 0));
  }
  const lanCuoi = Math.max(0, ...daChiDinh.map((c) => c.lan ?? 0));
  // Lượt đã có chỉ định → danh mục gập sau nút [+ Chỉ định thêm].
  const coTruoc = daChiDinh.length > 0;
  const hienDanhMuc = !coTruoc || moThem || chon.length > 0;

  const giaCua = new Map(moiMuc.flatMap((m) => (m.service_code ? [[m.service_code, m.gia]] : [])));
  const tong = chon.reduce((t, c) => t + (giaCua.get(c) ?? 0), 0);
  const chonTrongKhac = khac.filter((m) => m.service_code && chon.includes(m.service_code)).length;

  const bat = (ma: string, co: boolean) => {
    setChon((cu) => (co ? [...cu, ma] : cu.filter((x) => x !== ma)));
    if (!co) setBatBuoc((cu) => cu.filter((x) => x !== ma));
  };

  const dat = async () => {
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await onDat(
      chon,
      batBuoc.filter((c) => chon.includes(c)),
    );
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setBao(`Đã chỉ định ${chon.length} mục — khách vào hàng chờ phòng sau khi thu tiền.`);
    setChon([]);
    setBatBuoc([]);
    setMoThem(false);
  };

  /** Một dòng kiểu phiếu giấy: ô tick (20px) · tên · giá + chip mẫu. */
  const dong = (m: MucCls, phu?: string) => {
    const ma = m.service_code;
    const da = ma ? daDat.has(ma) : false;
    const dangChon = ma ? chon.includes(ma) : false;
    const lan = ma ? lanCua.get(ma) : undefined;
    const mau = chipMauDanhMuc(m);
    return (
      <li key={`${m.nhan}-${ma ?? ""}`} className="border-b border-hairline">
        <label
          className={`grid min-h-10 grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-1.5 py-1 sm:min-h-8 ${
            dangChon ? "bg-surface-selected" : ""
          } ${chiDoc || !ma ? "" : "cursor-pointer"}`}
        >
          <input
            type="checkbox"
            className="m-0 size-4 accent-brand-600"
            disabled={chiDoc || !ma}
            checked={dangChon}
            onChange={(e) => ma && bat(ma, e.target.checked)}
          />
          <span className="min-w-0">
            <span className={da ? "font-semibold text-brand-700" : "text-ink"}>{m.nhan}</span>
            {da ? (
              <span className="block text-label font-semibold text-brand-600">
                {lan ? `đã chỉ định ở lần ${lan}` : "đã chỉ định"}
              </span>
            ) : null}
            {phu ? <span className="block text-meta text-ink-faint">{phu}</span> : null}
          </span>
          <span className="flex flex-col items-end gap-0.5 whitespace-nowrap text-right text-meta text-ink-muted">
            {!ma ? (
              <span className="text-ink-faint">chưa có trong danh mục</span>
            ) : m.gia == null ? (
              <span className="text-ink-faint">chưa có giá</span>
            ) : (
              <span className="tabular-nums">{tienVn(m.gia)}</span>
            )}
            {ma ? <Chip tone={mau.tone}>{mau.nhan}</Chip> : null}
          </span>
        </label>
        {ma && !chiDoc && dangChon ? (
          <label className="ml-6.5 flex min-h-10 items-center gap-2 pb-1 text-meta text-ink sm:min-h-8">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={batBuoc.includes(ma)}
              onChange={(e) =>
                setBatBuoc((cu) => (e.target.checked ? [...cu, ma] : cu.filter((x) => x !== ma)))
              }
            />
            Bắt buộc — quầy thu không bỏ được
          </label>
        ) : null}
      </li>
    );
  };

  return (
    <div className="space-y-3">
      {coTruoc && !chiDoc && !hienDanhMuc ? (
        <Button type="button" variant="secondary" onClick={() => setMoThem(true)}>
          + Chỉ định thêm (lần {lanCuoi + 1})
        </Button>
      ) : null}
      {coTruoc && chiDoc ? (
        <p className="text-meta text-ink-muted">
          Phiếu chỉ xem — các chỉ định đã đặt nằm ở thẻ “Đã chỉ định &amp; kết quả”.
        </p>
      ) : null}
      {hienDanhMuc ? (
        <>
          <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
            {chinh.map((n) => (
              <div key={n.nhom} className="min-w-0">
                <h4 className="mb-1 text-label font-semibold uppercase tracking-wide text-ink-muted">
                  {n.nhom}
                </h4>
                <ul>{n.muc.map((m) => dong(m))}</ul>
              </div>
            ))}
          </div>
          {khac.length > 0 ? (
            <details className="group">
              <summary className="flex min-h-10 cursor-pointer list-none items-center gap-1.5 text-meta text-ink-muted sm:min-h-8 [&::-webkit-details-marker]:hidden">
                <span aria-hidden className="transition-transform group-open:rotate-90">
                  ▸
                </span>
                Dịch vụ khác trong bảng giá — không có trên phiếu giấy ({khac.length})
                {chonTrongKhac > 0 ? <Chip tone="brand">{chonTrongKhac} đang chọn</Chip> : null}
              </summary>
              <ul className="mt-2">
                {khac.map((m) => dong(m, [m.nhom_goc, m.ma_kiotviet].filter(Boolean).join(" · ")))}
              </ul>
            </details>
          ) : null}
        </>
      ) : null}
      {!chiDoc && hienDanhMuc ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="primary"
            disabled={dang || chon.length === 0}
            onClick={() => void dat()}
          >
            {dang
              ? "Đang ghi…"
              : chon.length > 0
                ? `${coTruoc ? "Chỉ định thêm" : nhanNut} ${chon.length} mục · ${tienVn(tong)}`
                : `Tick mục cần ${(coTruoc ? "chỉ định thêm" : nhanNut).toLowerCase()}`}
          </Button>
          {coTruoc && chon.length === 0 ? (
            <Button type="button" variant="ghost" onClick={() => setMoThem(false)}>
              Thu gọn
            </Button>
          ) : null}
          {loi ? (
            <p role="alert" className="text-meta text-danger">
              {loi}
            </p>
          ) : null}
          {bao ? <p className="text-meta text-success">{bao}</p> : null}
        </div>
      ) : bao ? (
        <p className="text-meta text-success">{bao}</p>
      ) : null}
    </div>
  );
}
