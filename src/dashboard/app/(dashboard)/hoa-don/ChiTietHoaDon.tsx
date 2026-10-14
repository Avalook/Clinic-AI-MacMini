"use client";

import HopChiTiet from "@/components/ui/HopChiTiet";
import { tenHinhThuc } from "@/lib/hinh-thuc-thu";
import { buttonClass } from "@/components/ui/Button";
import CongTyHoaDon from "./CongTyHoaDon";
import {
  TEN_SU_KIEN, TRANG_THAI, daTon, gio, ngayGio, tien,
  type DongHoaDon, type KhachHoaDon, type PhieuThu, type SuKien,
} from "./types";

function DongChiTiet({ dong }: { dong: DongHoaDon[] }) {
  return <ul className="divide-y divide-hairline">
    {dong.map(d => <li key={d.id} className="flex flex-wrap justify-between gap-2 py-2">
      <span className="min-w-0 break-words">{d.ten} <span className="text-ink-muted">× {d.so_luong}</span>
        {d.da_bo ? <span className="ml-2 rounded-chip bg-surface-muted px-2 py-0.5 text-meta text-ink-soft">đã bỏ sau thu</span> : null}</span>
      <span className="text-right tabular-nums">{tien(d.thanh_tien)}
        {(d.giam_gia ?? 0) > 0 ? <span className="block text-meta text-ink-muted">Trước giảm: {tien(d.thanh_tien_truoc_giam ?? d.thanh_tien)} · Giảm: {tien(d.giam_gia ?? 0)}</span> : null}</span>
    </li>)}
    {!dong.length ? <li className="py-2 text-ink-muted">Không có dữ liệu chi tiết dòng.</li> : null}
  </ul>;
}

const MAU_SU_KIEN: Record<SuKien["loai"], string> = {
  DOI_HINH_THUC: "bg-info-bg text-info",
  BO_DICH_VU: "bg-warning-bg text-warning",
  HOAN_TIEN: "bg-success-bg text-success",
  HUY_PHIEU: "bg-danger-bg text-danger",
  HUY_CHO_CK: "bg-warning-bg text-warning",
};
const TEN_HOAN: Record<string, string> = {
  PENDING: "chờ trả", COMPLETED: "đã trả", FAILED: "thất bại", CANCELLED: "đã huỷ yêu cầu",
};

/** "Sau khi thu": mọi việc làm tiền của phiếu thay đổi sau lúc bấm thu, theo giờ. */
function SauKhiThu({ su }: { su: SuKien[] }) {
  if (!su.length) return <p className="mt-3 flex flex-wrap justify-between gap-2 border-t border-dashed border-line pt-3">
    <b>Sau khi thu</b><span className="text-meta text-ink-muted">Không có thay đổi tiền nào sau khi thu.</span>
  </p>;
  return <div className="mt-3 border-t border-dashed border-line pt-3">
    <b>Sau khi thu</b>
    <ul className="mt-1 divide-y divide-hairline">
      {su.map((e, i) => <li key={i} className="grid grid-cols-[4.5rem_1fr_auto] gap-2 py-2">
        <span className="text-meta tabular-nums text-ink-muted">{gio(e.luc)}</span>
        <span className="min-w-0">
          <span className={`mr-1 inline-block rounded-chip px-2 py-0.5 text-meta font-medium ${MAU_SU_KIEN[e.loai]}`}>
            {TEN_SU_KIEN[e.loai]}{e.loai === "HOAN_TIEN" && e.trang_thai ? ` · ${TEN_HOAN[e.trang_thai] ?? e.trang_thai}` : ""}
          </span>
          {[e.mo_ta, e.nguoi].filter(Boolean).join(" · ")}
          {e.ly_do ? <span className="block text-meta text-ink-muted">Lý do: {e.ly_do}</span> : null}
          {e.loai === "HUY_PHIEU" && e.sau_giay != null ? <span className="block text-meta text-ink-muted">huỷ sau {e.sau_giay < 120 ? `${e.sau_giay} giây` : `${Math.round(e.sau_giay / 60)} phút`} kể từ lúc thu</span> : null}
        </span>
        <span className={`text-right font-semibold tabular-nums ${e.so_tien < 0 ? "text-danger" : ""}`}>
          {e.loai === "DOI_HINH_THUC" ? tien(e.so_tien) : e.so_tien < 0 ? `−${tien(-e.so_tien)}` : tien(e.so_tien)}
        </span>
      </li>)}
    </ul>
  </div>;
}

function Phieu({ phieu: p, so }: { phieu: PhieuThu; so: number }) {
  return <section className="rounded-card bg-surface p-4 ring-1 ring-hairline">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="text-emph font-semibold">
        <span className="mr-2 rounded-control bg-ink px-2 py-0.5 text-meta text-white">Phiếu {so}</span>
        {p.trang_thai === "CK_DA_HUY" ? "Chờ CK, huỷ lúc" : "Thu lúc"}{" "}
        <span className="tabular-nums">{gio(p.trang_thai === "CK_DA_HUY" ? p.huy_luc : p.thu_luc)}</span> · {p.ma} · {p.kind === "thuoc" ? "Thuốc" : "Dịch vụ"}
      </h3>
      <span className="text-body font-semibold">{TRANG_THAI[p.trang_thai] ?? p.trang_thai}</span>
      <a className={buttonClass("secondary", "md")} href={`/print/phieu-thu/${encodeURIComponent(p.id)}`} target="_blank" rel="noopener noreferrer">Xem / in phiếu</a>
    </div>
    {p.can_doi_soat ? <p className="mt-2 rounded-control bg-warning-bg p-2 text-warning">Phiếu cần đối soát: chuyển khoản về nhưng hoá đơn đã đổi, thuốc chưa ghi bán được, hoặc ngân hàng báo nhận khác số chuyển khoản.</p> : null}
    {p.so_tien_thuc_nhan != null ? <p className="mt-2 text-meta text-ink">Ngân hàng báo nhận <span className="tabular-nums">{tien(p.so_tien_thuc_nhan)}</span>{p.doi_soat_ly_do?.includes("SO_TIEN_LECH") ? " — khác số chuyển khoản của phiếu" : ""}.</p> : null}
    {p.trang_thai === "CK_DA_HUY" ? <p className="mt-2 rounded-control bg-warning-bg p-2 text-warning">Lần chờ chuyển khoản {tien(p.so_tien)} đã huỷ{p.nguoi_huy ? ` bởi ${p.nguoi_huy}` : ""}{p.ly_do_huy ? ` — “${p.ly_do_huy}”` : ""}. Chưa ghi là đã thu. Đối chiếu sao kê: nếu tiền đã về thì thu lại ở quầy bằng chuyển khoản rồi bấm “Đã nhận tiền”.</p> : null}
    {p.thu_trong_ky === false ? <p className="mt-2 text-meta text-ink-muted">Phiếu thu ngoài kỳ đang xem, có xử lý sau thanh toán trong kỳ.</p> : null}
    <dl className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-4">
      <div><dt className="text-meta text-ink-muted">{p.trang_thai === "CK_DA_HUY" ? "Số tiền lần chờ" : "Tiền đã thu"}</dt><dd className="tabular-nums">{tien(p.so_tien)}</dd></div>
      <div><dt className="text-meta text-ink-muted">Thực thu</dt><dd className="tabular-nums">{tien(p.thu_rong)}</dd></div>
      <div><dt className="text-meta text-ink-muted">Hình thức</dt><dd>{p.hinh_thuc ? tenHinhThuc(p.hinh_thuc) : "Không có dữ liệu"}</dd></div>
      <div><dt className="text-meta text-ink-muted">Người thu</dt><dd>{p.nguoi_thu || "Không có dữ liệu"}</dd></div>
    </dl>
    {p.giam_gia > 0 ? <p className="mt-3 rounded-control bg-surface-muted p-3">
      <b>Giảm giá {tien(p.giam_gia)}{p.kieu_giam === "PERCENT" ? ` (${p.gia_tri_giam}%)` : ""}</b> · trước giảm {tien(p.tong_truoc_giam)}
      <span className="block text-meta text-ink-muted">Lý do: {p.ly_do_giam || "Không có dữ liệu"} · {p.nguoi_giam || "—"} · {ngayGio(p.giam_luc)}</span>
    </p> : null}
    <SauKhiThu su={p.su_kien ?? []} />
    {p.trang_thai !== "DA_HUY" && p.trang_thai !== "CK_DA_HUY" ? <CongTyHoaDon paymentCycleId={p.id} /> : null}
    <h4 className="mt-4 text-meta font-semibold text-ink-muted">Dòng trên phiếu gốc</h4>
    <DongChiTiet dong={p.dong} />
    {p.hoan.length ? <div className="mt-2 flex flex-wrap gap-2">
      {p.hoan.map(h => <a key={h.id} className={buttonClass("secondary", "sm")} href={`/print/phieu-thu/${encodeURIComponent(h.id)}?loai=hoan`} target="_blank" rel="noopener noreferrer">In phiếu hoàn {h.ma}</a>)}
    </div> : null}
  </section>;
}

export default function ChiTietHoaDon({ khach, onDong }: { khach: KhachHoaDon; onDong: () => void }) {
  // Phiếu 1, 2, 3… theo giờ BẤM THU (cũ trước) — người đối soát lần theo thứ tự.
  const moc = (p: PhieuThu) => p.thu_luc ?? p.huy_luc ?? "";
  const phieu = [...khach.phieu].sort((a, b) => moc(a).localeCompare(moc(b)));
  const ton = khach.viec_ton ?? [];
  return <HopChiTiet tieuDe={`Hoá đơn · ${khach.ten}`} onDong={onDong}>
    <p className="mb-4 text-meta text-ink-muted">{khach.ma_bn || "—"} · {khach.so_dien_thoai || "—"} · {khach.so_phieu} phiếu</p>
    <dl className="mb-4 grid grid-cols-2 gap-3 rounded-control bg-surface-muted p-3 sm:grid-cols-4">
      {([["Tổng tiền hàng", khach.tong_truoc_giam], ["Giảm giá", khach.giam_gia], ["Tiền đã thu", khach.da_thu], ["Thực thu", khach.thu_rong]] as const).map(([ten, so]) => <div key={ten}><dt className="text-meta text-ink-muted">{ten}</dt><dd className="tabular-nums font-semibold">{tien(so)}</dd></div>)}
      {(khach.chua_tra_lai ?? 0) > 0 ? <div><dt className="text-meta text-ink-muted">Chưa trả lại khách</dt><dd className="tabular-nums font-semibold text-danger">{tien(khach.chua_tra_lai ?? 0)}</dd></div> : null}
    </dl>
    {ton.length ? <div className="mb-4 rounded-control bg-surface-muted p-3">
      <b>Việc còn tồn</b>
      <ul className="mt-1">{ton.map((v, i) => <li key={i} className="flex flex-wrap justify-between gap-2 py-1 text-body">
        <span>{v.ten_loai}{v.mo_ta ? ` · ${v.mo_ta}` : ""}</span>
        <span className="tabular-nums">{tien(v.so_tien)} <span className="text-meta text-ink-muted">· {daTon(v.luc)}</span></span>
      </li>)}</ul>
    </div> : null}
    <div className="space-y-4">{phieu.map((p, i) => <Phieu key={p.id} phieu={p} so={i + 1} />)}</div>
  </HopChiTiet>;
}
