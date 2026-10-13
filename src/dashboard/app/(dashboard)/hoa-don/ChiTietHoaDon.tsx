"use client";

import HopChiTiet from "@/components/ui/HopChiTiet";
import { tenHinhThuc } from "@/lib/hinh-thuc-thu";
import { buttonClass } from "@/components/ui/Button";
import { TRANG_THAI, ngayGio, tien, type DongHoaDon, type KhachHoaDon, type PhieuThu } from "./types";

function DongChiTiet({ dong }: { dong: DongHoaDon[] }) {
  return <ul className="divide-y divide-hairline">
    {dong.map(d => <li key={d.id} className="flex flex-wrap justify-between gap-2 py-2">
      <span className="min-w-0 break-words">{d.ten} <span className="text-ink-muted">× {d.so_luong}</span>
        {d.da_bo ? <span className="ml-2 text-warning">Đã bỏ sau thanh toán</span> : null}</span>
      <span className="text-right tabular-nums">{tien(d.thanh_tien)}
        {(d.giam_gia ?? 0) > 0 ? <span className="block text-meta text-ink-muted">Trước giảm: {tien(d.thanh_tien_truoc_giam ?? d.thanh_tien)} · Giảm: {tien(d.giam_gia ?? 0)}</span> : null}</span>
    </li>)}
    {!dong.length ? <li className="py-2 text-ink-muted">Không có dữ liệu chi tiết dòng.</li> : null}
  </ul>;
}

function Moc({ ten, nguoi, luc }: { ten: string; nguoi: string | null; luc: string | null }) {
  return <div><dt className="text-meta text-ink-muted">{ten}</dt>
    <dd>{nguoi || "Không có dữ liệu người thực hiện"}<span className="block text-meta text-ink-muted">{ngayGio(luc)}</span></dd></div>;
}

function Phieu({ phieu: p }: { phieu: PhieuThu }) {
  return <section className="rounded-card bg-surface p-4 ring-1 ring-hairline">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-emph font-semibold">{p.ma} · {p.kind === "thuoc" ? "Thuốc" : "Dịch vụ"}</h3>
      <span className="text-body font-semibold">{TRANG_THAI[p.trang_thai] ?? p.trang_thai}</span>
      <a className={buttonClass("secondary", "md")} href={`/print/phieu-thu/${encodeURIComponent(p.id)}`} target="_blank" rel="noopener noreferrer">Xem / in phiếu</a>
    </div>
    {p.can_doi_soat ? <p className="mt-2 rounded-control bg-warning-bg p-2 text-warning">Phiếu cần đối soát: kiểm tra chứng từ thu, hoàn và số tiền thực tế. Hủy phiếu không chứng minh đã trả tiền lại.</p> : null}
    {p.thu_trong_ky === false ? <p className="mt-2 text-meta text-ink-muted">Phiếu thu ngoài kỳ đang xem, có xử lý sau thanh toán trong kỳ.</p> : null}
    <dl className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
      <div><dt className="text-meta text-ink-muted">Trước giảm giá</dt><dd className="tabular-nums">{tien(p.tong_truoc_giam)}</dd></div>
      <div><dt className="text-meta text-ink-muted">Giảm giá</dt><dd className="tabular-nums">{tien(p.giam_gia)}</dd></div>
      <div><dt className="text-meta text-ink-muted">Tiền sau giảm</dt><dd className="tabular-nums">{tien(p.so_tien)}</dd></div>
      <div><dt className="text-meta text-ink-muted">Đã hoàn</dt><dd className="tabular-nums">{tien(p.da_hoan)}</dd></div>
      <div><dt className="text-meta text-ink-muted">Chờ hoàn</dt><dd className="tabular-nums">{tien(p.cho_hoan)}</dd></div>
      <div><dt className="text-meta text-ink-muted">Thu ròng</dt><dd className="tabular-nums">{tien(p.thu_rong)}</dd></div>
    </dl>
    <p className="mt-2 text-meta text-ink-muted">Hình thức: {p.hinh_thuc ? tenHinhThuc(p.hinh_thuc) : "Không có dữ liệu"}</p>
    <dl className="mt-3 grid gap-3 sm:grid-cols-3">
      <Moc ten="Lập phiếu" nguoi={p.nguoi_lap} luc={p.lap_luc} />
      <Moc ten="Thu tiền" nguoi={p.nguoi_thu} luc={p.thu_luc} />
      {p.huy_luc ? <Moc ten="Hủy phiếu" nguoi={p.nguoi_huy} luc={p.huy_luc} /> : null}
    </dl>
    {p.huy_luc ? <p className="mt-2 text-warning">Lý do hủy: {p.ly_do_huy || "Không có dữ liệu"}</p> : null}
    {p.giam_gia > 0 ? <section className="mt-3 rounded-control bg-surface-muted p-3">
      <h4 className="font-semibold">Giảm giá trên phiếu{p.kieu_giam === "PERCENT" ? ` · ${p.gia_tri_giam}%` : ""}</h4>
      <p className="mt-1">Lý do: {p.ly_do_giam || "Không có dữ liệu"}</p>
      <dl className="mt-2"><Moc ten="Người giảm giá" nguoi={p.nguoi_giam} luc={p.giam_luc} /></dl>
    </section> : null}
    <h4 className="mt-4 text-meta font-semibold text-ink-muted">Dòng trên phiếu gốc</h4>
    <DongChiTiet dong={p.dong} />
    {p.hoan.map(h => <div key={h.id} className="mt-3 rounded-control bg-surface-muted p-3">
      <h4 className="font-semibold">Phiếu hoàn {h.ma} · {({ PENDING: "Chờ trả lại", COMPLETED: "Đã trả lại", FAILED: "Hoàn thất bại", CANCELLED: "Đã hủy yêu cầu hoàn" } as Record<string, string>)[h.trang_thai] ?? h.trang_thai} · {tien(h.so_tien)}</h4>
      <a className={buttonClass("secondary", "md")} href={`/print/phieu-thu/${encodeURIComponent(h.id)}?loai=hoan`} target="_blank" rel="noopener noreferrer">Xem / in phiếu hoàn</a>
      <p className="mt-1">Lý do: {h.ly_do || "Không có dữ liệu"}</p>
      <p className="mt-1 text-meta text-ink-muted">Hình thức hoàn: {h.hinh_thuc ? tenHinhThuc(h.hinh_thuc) : "Không có dữ liệu"}</p>
      <dl className="mt-2 grid gap-3 sm:grid-cols-2">
        <Moc ten="Yêu cầu hoàn" nguoi={h.nguoi_lap} luc={h.lap_luc} />
        <Moc ten="Trả tiền lại" nguoi={h.nguoi_hoan} luc={h.hoan_luc} />
      </dl>
      {h.huy_luc ? <><Moc ten="Hủy / đóng yêu cầu hoàn" nguoi={h.nguoi_huy ?? null} luc={h.huy_luc} /><p className="mt-2">Lý do đóng: {h.ly_do_huy || "Không có dữ liệu"}</p></> : null}
      <DongChiTiet dong={h.dong} />
    </div>)}
  </section>;
}

export default function ChiTietHoaDon({ khach, onDong }: { khach: KhachHoaDon; onDong: () => void }) {
  return <HopChiTiet tieuDe={`Hoá đơn · ${khach.ten}`} onDong={onDong}>
    <p className="mb-4 text-meta text-ink-muted">{khach.ma_bn || "—"} · {khach.so_dien_thoai || "—"} · {khach.so_phieu} phiếu</p>
    <dl className="mb-4 grid grid-cols-2 gap-3 rounded-control bg-surface-muted p-3 sm:grid-cols-4">
      {([["Trước giảm giá", khach.tong_truoc_giam], ["Giảm giá", khach.giam_gia], ["Đã thu", khach.da_thu], ["Đã hoàn", khach.da_hoan], ["Chờ hoàn", khach.cho_hoan], ["Thu ròng", khach.thu_rong]] as const).map(([ten, so]) => <div key={ten}><dt className="text-meta text-ink-muted">{ten}</dt><dd className="tabular-nums font-semibold">{tien(so)}</dd></div>)}
    </dl>
    <div className="space-y-4">{khach.phieu.map(p => <Phieu key={p.id} phieu={p} />)}</div>
  </HopChiTiet>;
}
