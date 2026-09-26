"use client";

// Mục C (cận lâm sàng) và mục F (thủ thuật) của phiếu v5 — DANH MỤC CÓ GIÁ.
//
// Thiết kế v5: "Mở đúng hạng mục cần dùng. Danh mục đóng mặc định để bác sĩ
// không phải nhìn toàn bộ cùng lúc." Mỗi nhóm là một ngăn gập; tick nhiều mục
// rồi bấm MỘT lần → thành chỉ định thật (lệnh PlaceServiceOrders, như ô chỉ
// định cũ ở Bàn khám). Mục đã chỉ định trong lượt hiện "Đã chỉ định".
//
// Mã dịch vụ và giá do MÁY CHỦ gắn (bảng ghép viết tay `anh_xa_danh_muc.py`) —
// màn này không so tên. Mục chưa có mã (phòng khám chưa có dịch vụ ấy) khoá lại.
//
// CHỈ ĐỊNH THÊM (Tuyền 25/09/2026): trong CÙNG một lượt khám bác sĩ chỉ định
// được 2, 3 lần — mỗi lần vẫn đi thanh toán rồi làm như lần đầu. Lượt đã có chỉ
// định thì trên cùng là ghi chú "Lần 1 · 09:40 — …" (khỏi mở lại danh mục cũ để
// nhớ), danh mục gập sau nút [+ Chỉ định thêm (lần N)].
//
// CHỈ ĐỊNH LẠI (26/09/2026 — lát 4): dịch vụ đã chỉ định ở lần trước vẫn tick
// được ở lần mới (vd siêu âm lại sau thủ thuật) — dòng tô xanh, ghi "đã chỉ định ·
// lần n" để bác sĩ biết mình đang chỉ định lần hai. Số lần do máy chủ gán.

import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { fmtTime } from "@/lib/datetime";
import { tienVn, type ChiDinhVaKetQua, type NhomCls } from "@/lib/phieu-kham";

export default function DanhMucChiDinh({
  nhom,
  daDat,
  daChiDinh = [],
  onDat,
  onDoiBatBuoc,
  chiDoc,
  nhanNut = "Chỉ định",
}: {
  nhom: NhomCls[];
  /** service_code đã có chỉ định (chưa huỷ) trong lượt. */
  daDat: ReadonlySet<string>;
  /** Mọi chỉ định (chưa huỷ) của lượt — để ghi chú "lần trước đã chỉ định gì". */
  daChiDinh?: readonly ChiDinhVaKetQua[];
  onDat: (
    codes: string[],
    /** Mã tick "Bắt buộc" (25/09/2026) — quầy thu không bỏ được. */
    batBuoc: string[],
  ) => Promise<{ ok: true } | { ok: false; loi: string }>;
  /** Bật / tắt "Bắt buộc" của chỉ định đã đặt (chưa thu tiền). Không truyền =
   *  chỉ xem. */
  onDoiBatBuoc?: (
    orderId: string,
    batBuoc: boolean,
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

  // Chỉ định CỦA MỤC NÀY (C: cận lâm sàng · F: thủ thuật), gom theo lần.
  const maMuc = new Set(nhom.flatMap((n) => n.muc).flatMap((m) => (m.service_code ? [m.service_code] : [])));
  const cuaMuc = daChiDinh.filter((c) => maMuc.has(c.service_code));
  // Một dịch vụ có thể đã chỉ định ở nhiều lần → nhớ lần GẦN nhất.
  const lanCua = new Map<string, number>();
  for (const c of cuaMuc) {
    if (c.lan != null) lanCua.set(c.service_code, Math.max(c.lan, lanCua.get(c.service_code) ?? 0));
  }
  const theoLan = new Map<string, ChiDinhVaKetQua[]>();
  for (const c of cuaMuc) {
    const khoa = c.mang_sang || c.lan == null ? "Mang sang từ lượt trước" : `Lần ${c.lan}`;
    theoLan.set(khoa, [...(theoLan.get(khoa) ?? []), c]);
  }
  const lanCuoi = Math.max(0, ...daChiDinh.map((c) => c.lan ?? 0));
  // Lượt đã có chỉ định → danh mục gập sau nút [+ Chỉ định thêm].
  const coTruoc = daChiDinh.length > 0;
  const hienDanhMuc = !coTruoc || moThem || chon.length > 0;

  const giaCua = new Map(
    nhom.flatMap((n) => n.muc).flatMap((m) => (m.service_code ? [[m.service_code, m.gia]] : [])),
  );
  const tong = chon.reduce((t, c) => t + (giaCua.get(c) ?? 0), 0);

  const bat = (ma: string, co: boolean) => {
    setChon((cu) => (co ? [...cu, ma] : cu.filter((x) => x !== ma)));
    if (!co) setBatBuoc((cu) => cu.filter((x) => x !== ma));
  };

  const doiBatBuocDaDat = async (c: ChiDinhVaKetQua, co: boolean) => {
    if (!onDoiBatBuoc) return;
    setLoi(null);
    const kq = await onDoiBatBuoc(c.service_order_id, co);
    if (!kq.ok) setLoi(kq.loi);
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

  return (
    <div className="space-y-2">
      {theoLan.size > 0 ? (
        <div className="rounded-control border border-hairline bg-surface-muted px-3 py-2">
          <p className="text-meta font-semibold text-ink">Đã chỉ định</p>
          <ul className="mt-1 space-y-1">
            {[...theoLan.entries()].map(([lan, ds]) => (
              <li key={lan} className="text-meta text-ink-muted">
                <span className="font-semibold text-ink">{lan}</span>
                {ds[0]?.chi_dinh_luc ? ` · ${fmtTime(ds[0].chi_dinh_luc)}` : ""}
                {" — "}
                {ds.map((c, i) => (
                  <span key={c.service_order_id}>
                    {i > 0 ? ", " : ""}
                    {c.ten_hien_thi}
                    {onDoiBatBuoc ? (
                      <label className="ml-1 inline-flex items-center gap-1 align-middle">
                        <input
                          type="checkbox"
                          className="size-3.5 accent-brand-600"
                          checked={Boolean(c.bat_buoc)}
                          onChange={(e) => void doiBatBuocDaDat(c, e.target.checked)}
                        />
                        bắt buộc
                      </label>
                    ) : c.bat_buoc ? (
                      <span className="ml-1">
                        <Chip tone="warning">bắt buộc</Chip>
                      </span>
                    ) : null}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {coTruoc && !chiDoc && !hienDanhMuc ? (
        <Button type="button" variant="secondary" onClick={() => setMoThem(true)}>
          + Chỉ định thêm (lần {lanCuoi + 1})
        </Button>
      ) : null}
      {hienDanhMuc ? nhom.map((n) => {
        const coChon = n.muc.filter((m) => m.service_code && chon.includes(m.service_code)).length;
        const coDat = n.muc.filter((m) => m.service_code && daDat.has(m.service_code)).length;
        return (
          <details key={n.nhom} className="rounded-control border border-hairline bg-surface">
            <summary className="flex min-h-10 cursor-pointer items-center gap-2 px-3 text-body font-medium text-ink">
              <span className="min-w-0 flex-1">{n.nhom}</span>
              {coDat > 0 ? <Chip tone="success">{coDat} đã chỉ định</Chip> : null}
              {coChon > 0 ? <Chip tone="brand">{coChon} đang chọn</Chip> : null}
              <span className="text-meta text-ink-faint">{n.muc.length}</span>
            </summary>
            <ul className="divide-y divide-hairline border-t border-hairline">
              {n.muc.map((m) => {
                const ma = m.service_code;
                const da = ma ? daDat.has(ma) : false;
                const khoa = chiDoc || !ma;
                const lan = ma ? lanCua.get(ma) : undefined;
                return (
                  <li key={m.nhan} className={da ? "bg-success-bg" : undefined}>
                    <label className="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-1 px-3 py-1.5">
                      <input
                        type="checkbox"
                        className="size-4 accent-brand-600"
                        disabled={khoa}
                        checked={ma ? chon.includes(ma) : false}
                        onChange={(e) => ma && bat(ma, e.target.checked)}
                      />
                      <span className="min-w-0 flex-1 text-body text-ink">{m.nhan}</span>
                      <span className="text-meta text-ink-muted">{m.cach_tra_ket_qua}</span>
                      <span className="text-meta tabular-nums text-ink">
                        {ma ? tienVn(m.gia) : ""}
                      </span>
                      {da ? (
                        <Chip tone="success">
                          {lan ? `Đã chỉ định · lần ${lan}` : "Đã chỉ định"}
                        </Chip>
                      ) : null}
                      {!ma ? <Chip tone="warning">Chưa có trong danh mục</Chip> : null}
                    </label>
                    {ma && !chiDoc && chon.includes(ma) ? (
                      <label className="ml-10 flex min-h-10 items-center gap-2 pb-1.5 text-meta text-ink">
                        <input
                          type="checkbox"
                          className="size-4 accent-brand-600"
                          checked={batBuoc.includes(ma)}
                          onChange={(e) =>
                            setBatBuoc((cu) =>
                              e.target.checked ? [...cu, ma] : cu.filter((x) => x !== ma),
                            )
                          }
                        />
                        Bắt buộc — quầy thu không bỏ được
                      </label>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </details>
        );
      }) : null}
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
      ) : null}
    </div>
  );
}
