"use client";

// Theo dõi thuốc (Tuyền 31/10/2026): thuốc đang ở đâu, đã đi qua những đâu, ai làm,
// lúc nào. Chỉ đọc: `GET /api/pharmacy/theo-doi-thuoc` → `theo_doi_thuoc_service`.
// Máy chủ tính mọi số, đặt tên hành động, từ đâu → đến đâu; ở đây chỉ vẽ.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import OChon from "@/components/ui/OChon";
import ThanhSoTrang from "@/components/ui/ThanhSoTrang";
import { INPUT, LABEL, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import XemLuot from "../../_lam-viec/XemLuot";
import { soKho } from "./gui-kho";

export interface ChonThuoc {
  id: string;
  /** Chọn từ gợi ý số lô → mở sẵn lọc lô ấy. */
  lo?: string | null;
}

interface GoiY {
  id: string;
  ten: string;
  ma_hang: string | null;
  so_lo: string | null;
  dang_dung: boolean;
}

interface TongDonVi {
  don_vi: string | null;
  tong: number;
  /** Thuốc thật trên kệ = tồn trên máy − đã giao chờ gán lô (máy chủ tính). */
  tren_ke: number;
  o_kho: number;
  o_quay: number;
  cho_gan_lo: number;
  cho_kiem: number;
  da_huy: number;
}

interface DongLo {
  so_lo: string;
  han_dung: string | null;
  don_vi: string | null;
  o_kho: number;
  o_quay: number;
  cho_kiem: number;
  da_huy: number;
  het_han: boolean;
}

interface DongSuKien {
  id: string;
  luc: string;
  hanh_dong: string;
  tu: string;
  den: string | null;
  so_lo: string | null;
  han_dung: string | null;
  so_luong: number;
  don_vi: string | null;
  ton_truoc: number | null;
  ton_sau: number | null;
  /** Chuyển kho: một sự kiện, tồn trước → sau có đủ nơi đi và nơi đến. */
  la_chuyen: boolean;
  ton_den_truoc: number | null;
  ton_den_sau: number | null;
  nguoi_lam: string | null;
  khach: string | null;
  ma_bn: string | null;
  visit_id: string | null;
  ma_phieu: string | null;
  ly_do: string | null;
  chua_tru_kho: boolean;
}

interface KetQua {
  thuoc: { ten: string; ma_hang: string | null; don_vi_ban: string | null; dang_dung: boolean } | null;
  dang_o_dau: { tong: TongDonVi[]; lo: DongLo[] };
  dong: DongSuKien[];
  tong: number;
  so_dong_mot_trang: number;
  xuat_toi_da: number;
  loc: { hanh_dong: { ma: string; nhan: string }[]; nguoi: { id: string; ten: string }[] };
}

const LOC_TRONG = { tu: "", den: "", hanh_dong: "", noi: "", lo: "", nguoi: "" };

const gio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

const ngay = (s: string | null) =>
  s ? new Date(`${s}T00:00:00+07:00`).toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "—";

const so = (n: number, donVi: string | null) => `${soKho(n)} ${donVi ?? ""}`.trim();

function OSo({ nhan, gia, donVi }: { nhan: string; gia: number; donVi: string | null }) {
  return (
    <div>
      <dt className="text-meta text-ink-muted">{nhan}</dt>
      <dd className="font-semibold tabular-nums text-ink">{so(gia, donVi)}</dd>
    </div>
  );
}

function DangODau({
  ds,
  onChonLo,
}: {
  ds: KetQua["dang_o_dau"];
  onChonLo: (lo: string) => void;
}) {
  const coChoGan = ds.tong.some((t) => Number(t.cho_gan_lo) > 0);
  const coChoKiem = ds.tong.some((t) => Number(t.cho_kiem) > 0);
  const keAm = ds.tong.some((t) => Number(t.tren_ke) < 0);
  return (
    <section aria-label="Đang ở đâu" className="flex flex-col gap-2">
      <h2 className="text-title font-semibold text-ink">Đang ở đâu</h2>
      {ds.tong.length === 0 ? (
        <p className="text-body text-ink-muted">Cơ sở này chưa có lô nào của thuốc này.</p>
      ) : null}
      {ds.tong.map((t) => (
        <div key={t.don_vi ?? ""} className="rounded-card bg-surface p-3 ring-1 ring-inset ring-line">
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
            <OSo nhan="Tồn trên máy" gia={t.tong} donVi={t.don_vi} />
            <OSo nhan="Ở kho" gia={t.o_kho} donVi={t.don_vi} />
            <OSo nhan="Ở quầy" gia={t.o_quay} donVi={t.don_vi} />
            <OSo nhan="Đã giao, chờ gán lô" gia={t.cho_gan_lo} donVi={t.don_vi} />
            <OSo nhan="Trên kệ thật" gia={t.tren_ke} donVi={t.don_vi} />
            <OSo nhan="Khách trả, chờ kiểm" gia={t.cho_kiem} donVi={t.don_vi} />
            <OSo nhan="Đã huỷ từ trước tới nay" gia={t.da_huy} donVi={t.don_vi} />
          </dl>
        </div>
      ))}
      {coChoGan ? (
        <p className="text-meta text-ink-muted">
          Đã giao, chờ gán lô: thuốc đã tới tay khách nhưng máy chưa trừ. Trên kệ thật = tồn trên máy −
          số này.
        </p>
      ) : null}
      {keAm ? (
        <p className="text-meta text-ink-muted">
          Trên kệ thật là số âm: đã giao nhiều hơn số đã nhập vào máy, cần nhập lô rồi gán.
        </p>
      ) : null}
      {coChoKiem ? (
        <p className="text-meta text-ink-muted">
          Khách trả, chờ kiểm: đã nằm trong số ở quầy, nhưng chưa bán lại được.
        </p>
      ) : null}
      {ds.lo.length > 0 ? (
        <div className={`${TBL_WRAP} overflow-x-auto`}>
          <table className="w-full min-w-xl text-left text-body">
            <thead className={TBL_HEAD}>
              <tr>
                <th className="px-3 py-2">Lô</th>
                <th className="px-3 py-2">Hạn dùng</th>
                <th className="px-3 py-2 text-right">Ở kho</th>
                <th className="px-3 py-2 text-right">Ở quầy</th>
                <th className="px-3 py-2 text-right">Chờ kiểm</th>
                <th className="px-3 py-2 text-right">Đã huỷ</th>
              </tr>
            </thead>
            <tbody className={TBL_DIV}>
              {ds.lo.map((l) => (
                <tr key={`${l.so_lo}|${l.don_vi ?? ""}`}>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      title="Chỉ xem dòng thời gian của lô này"
                      onClick={() => onChonLo(l.so_lo)}
                      className="min-h-10 text-left font-medium text-brand-700 hover:underline sm:min-h-0"
                    >
                      {l.so_lo}
                    </button>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-ink-muted">
                    {ngay(l.han_dung)}
                    {l.het_han ? <span className="ml-2 text-danger">Hết hạn</span> : null}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-ink">{so(l.o_kho, l.don_vi)}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-ink">{so(l.o_quay, l.don_vi)}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-ink-muted">{so(l.cho_kiem, l.don_vi)}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums text-ink-muted">{so(l.da_huy, l.don_vi)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function SuKien({ d, onXemLuot }: { d: DongSuKien; onXemLuot: (id: string) => void }) {
  const sl = Number(d.so_luong);
  return (
    <li className="grid grid-cols-1 gap-1 px-3 py-2 text-body md:grid-cols-12 md:gap-3">
      <div className="md:col-span-2">
        <p className="tabular-nums text-ink">{gio(d.luc)}</p>
        <p className="text-meta text-ink-muted">{d.nguoi_lam ?? "Không rõ người làm"}</p>
      </div>
      <div className="md:col-span-3">
        <p className="font-semibold text-ink">{d.hanh_dong}</p>
        <p className="text-meta text-ink-muted">{d.den ? `${d.tu} → ${d.den}` : `Tại ${d.tu}`}</p>
      </div>
      <div className="md:col-span-2">
        <p className="text-ink">{d.so_lo ? `Lô ${d.so_lo}` : "Chưa có lô"}</p>
        {d.han_dung ? <p className="text-meta text-ink-muted">Hạn {ngay(d.han_dung)}</p> : null}
      </div>
      <div className="md:col-span-2 md:text-right">
        <p className="font-semibold tabular-nums text-ink">
          {sl > 0 && !d.la_chuyen ? "+" : ""}
          {so(sl, d.don_vi)}
        </p>
        {d.la_chuyen ? (
          <p className="text-meta tabular-nums text-ink-muted">
            {d.tu} {soKho(d.ton_truoc ?? 0)} → {soKho(d.ton_sau ?? 0)} · {d.den}{" "}
            {soKho(d.ton_den_truoc ?? 0)} → {soKho(d.ton_den_sau ?? 0)}
          </p>
        ) : d.ton_sau != null ? (
          <p className="text-meta tabular-nums text-ink-muted">
            Tồn lô {soKho(d.ton_truoc ?? 0)} → {soKho(d.ton_sau)}
          </p>
        ) : !d.chua_tru_kho ? (
          <p className="text-meta text-ink-muted">Không đổi tồn</p>
        ) : null}
      </div>
      <div className="min-w-0 md:col-span-3">
        {d.khach ? (
          <p>
            {d.visit_id ? (
              <button
                type="button"
                title="Xem lượt khám"
                onClick={() => d.visit_id && onXemLuot(d.visit_id)}
                className="min-h-10 text-left font-medium text-brand-700 hover:underline sm:min-h-0"
              >
                {d.khach}
              </button>
            ) : (
              <span className="text-ink">{d.khach}</span>
            )}
            {d.ma_bn ? <span className="ml-2 whitespace-nowrap text-meta text-ink-muted">{d.ma_bn}</span> : null}
          </p>
        ) : null}
        {d.ma_phieu ? <p className="text-meta text-ink-muted">{d.ma_phieu}</p> : null}
        {d.ly_do ? (
          <p className={`break-words text-meta ${d.chua_tru_kho ? "font-semibold text-warning" : "text-ink-muted"}`}>
            {d.ly_do}
          </p>
        ) : null}
      </div>
    </li>
  );
}

/** Mở theo `key` thuốc + lô: đổi thuốc thì bộ lọc và số trang tự về đầu. */
function ChiTietThuoc({ id, loDau }: { id: string; loDau?: string | null }) {
  const [loc, setLoc] = useState({ ...LOC_TRONG, lo: loDau ?? "" });
  const [trang, setTrang] = useState(1);
  const [xemLuot, setXemLuot] = useState<string | null>(null);
  const thamSo = new URLSearchParams({ thuoc: id, ...loc }).toString();
  const hoi = `${thamSo}&trang=${trang}`;
  // Kết quả gắn với câu đã hỏi — đang tải = kết quả chưa phải của `hoi`; giữ bản cũ
  // trên màn để đổi trang không nháy trắng (không setState đồng bộ trong effect).
  const [tra, setTra] = useState<{ hoi: string; kq: KetQua | null; loi: string | null } | null>(null);
  const dangTai = tra?.hoi !== hoi;
  const kq = tra?.kq ?? null;
  const loi = tra?.hoi === hoi ? tra.loi : null;

  useEffect(() => {
    let bo = false;
    fetch(`/api/pharmacy/theo-doi-thuoc?${hoi}`, { cache: "no-store" })
      .then(async (r) => {
        const d = (await r.json().catch(() => null)) as (KetQua & { error?: string; message?: string }) | null;
        if (bo) return;
        if (!r.ok || !d)
          setTra((cu) => ({ hoi, kq: cu?.kq ?? null, loi: d?.message ?? d?.error ?? "Không đọc được dữ liệu thuốc." }));
        else setTra({ hoi, kq: d, loi: null });
      })
      .catch(() => {
        if (!bo) setTra((cu) => ({ hoi, kq: cu?.kq ?? null, loi: "Mất kết nối — chưa đọc được dữ liệu thuốc." }));
      });
    return () => {
      bo = true;
    };
  }, [hoi]);

  const doiLoc = (moi: Partial<typeof LOC_TRONG>) => {
    setLoc((cu) => ({ ...cu, ...moi }));
    setTrang(1);
  };
  const dangLoc = Object.values(loc).some(Boolean);
  const soTrang = kq ? Math.ceil(kq.tong / kq.so_dong_mot_trang) : 0;
  const xuatExcel = () => {
    const a = document.createElement("a");
    a.href = `/api/pharmacy/theo-doi-thuoc-xlsx?${thamSo}`;
    a.click();
  };

  if (!kq) {
    return loi ? (
      <p role="alert" className="text-body text-danger">{loi}</p>
    ) : (
      <p className="text-body text-ink-muted">Đang đọc dữ liệu thuốc…</p>
    );
  }
  if (!kq.thuoc) {
    return <p className="text-body text-ink-muted">Không tìm thấy thuốc này ở phòng khám.</p>;
  }
  return (
    <div className="flex flex-col gap-4">
      <p className="text-body text-ink">
        <span className="font-semibold">{kq.thuoc.ten}</span>
        {kq.thuoc.ma_hang ? <span className="text-ink-muted"> · {kq.thuoc.ma_hang}</span> : null}
        {kq.thuoc.dang_dung ? null : <span className="text-ink-muted"> · Đã tắt trong danh mục</span>}
      </p>
      <DangODau ds={kq.dang_o_dau} onChonLo={(lo) => doiLoc({ lo })} />

      <section aria-label="Dòng thời gian" className="flex flex-col gap-2">
        <h2 className="text-title font-semibold text-ink">Dòng thời gian</h2>
        <div className="grid grid-cols-2 items-end gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <label className="block">
            <span className={LABEL}>Từ ngày</span>
            <input type="date" value={loc.tu} onChange={(e) => doiLoc({ tu: e.target.value })} className={INPUT} />
          </label>
          <label className="block">
            <span className={LABEL}>Đến ngày</span>
            <input type="date" value={loc.den} onChange={(e) => doiLoc({ den: e.target.value })} className={INPUT} />
          </label>
          <label className="block">
            <span className={LABEL}>Hành động</span>
            <OChon value={loc.hanh_dong} onChange={(e) => doiLoc({ hanh_dong: e.target.value })} className="w-full">
              <option value="">Tất cả</option>
              {kq.loc.hanh_dong.map((h) => (
                <option key={h.ma} value={h.ma}>{h.nhan}</option>
              ))}
            </OChon>
          </label>
          <label className="block">
            <span className={LABEL}>Nơi</span>
            <OChon value={loc.noi} onChange={(e) => doiLoc({ noi: e.target.value })} className="w-full">
              <option value="">Tất cả</option>
              <option value="KHO">Kho</option>
              <option value="QUAY">Quầy</option>
            </OChon>
          </label>
          <label className="block">
            <span className={LABEL}>Lô</span>
            <OChon value={loc.lo} onChange={(e) => doiLoc({ lo: e.target.value })} className="w-full">
              <option value="">Tất cả</option>
              {kq.dang_o_dau.lo.map((l) => (
                <option key={`${l.so_lo}|${l.don_vi ?? ""}`} value={l.so_lo}>{l.so_lo}</option>
              ))}
            </OChon>
          </label>
          <label className="block">
            <span className={LABEL}>Người làm</span>
            <OChon value={loc.nguoi} onChange={(e) => doiLoc({ nguoi: e.target.value })} className="w-full">
              <option value="">Tất cả</option>
              {kq.loc.nguoi.map((n) => (
                <option key={n.id} value={n.id}>{n.ten}</option>
              ))}
            </OChon>
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-body text-ink-muted">
            {kq.tong} dòng{dangTai ? " · đang tải…" : ""}
            {kq.tong > kq.xuat_toi_da ? ` · Excel lấy ${kq.xuat_toi_da} dòng mới nhất` : ""}
          </p>
          <div className="flex items-center gap-2 sm:ml-auto">
            {dangLoc ? (
              <Button type="button" size="sm" variant="ghost" onClick={() => doiLoc(LOC_TRONG)}>
                Bỏ lọc
              </Button>
            ) : null}
            <Button type="button" size="sm" variant="secondary" disabled={kq.dong.length === 0} onClick={xuatExcel}>
              Xuất Excel
            </Button>
          </div>
        </div>
        {loi ? <p role="alert" className="text-body text-danger">{loi}</p> : null}
        <div className={TBL_WRAP}>
          <div className={`${TBL_HEAD} hidden px-3 py-2 md:grid md:grid-cols-12 md:gap-3`}>
            <span className="md:col-span-2">Lúc · ai làm</span>
            <span className="md:col-span-3">Hành động · từ đâu đến đâu</span>
            <span className="md:col-span-2">Lô</span>
            <span className="md:col-span-2 md:text-right">Số lượng · tồn lô</span>
            <span className="md:col-span-3">Khách · phiếu · lý do</span>
          </div>
          {kq.dong.length === 0 ? (
            <p className="px-3 py-6 text-center text-body text-ink-muted">
              {dangLoc ? "Không có dòng nào khớp bộ lọc." : "Thuốc này chưa có biến động nào ở cơ sở này."}
            </p>
          ) : (
            <ul className={TBL_DIV}>
              {kq.dong.map((d) => (
                <SuKien key={d.id} d={d} onXemLuot={setXemLuot} />
              ))}
            </ul>
          )}
        </div>
        <ThanhSoTrang trang={trang} soTrang={soTrang} onChon={setTrang} dangTai={dangTai} nhan="Trang dòng thời gian" />
      </section>
      {xemLuot ? <XemLuot visitId={xemLuot} onDong={() => setXemLuot(null)} /> : null}
    </div>
  );
}

export default function TheoDoiThuoc({
  chon,
  onChon,
}: {
  chon: ChonThuoc | null;
  onChon: (c: ChonThuoc) => void;
}) {
  const [go, setGo] = useState("");
  const q = go.trim();
  const [tim, setTim] = useState<{ q: string; ds: GoiY[]; loi: boolean } | null>(null);

  useEffect(() => {
    if (!q) return;
    let bo = false;
    const hen = setTimeout(() => {
      fetch(`/api/pharmacy/tim-theo-doi?${new URLSearchParams({ q })}`, { cache: "no-store" })
        .then(async (r) => {
          const d = (await r.json().catch(() => null)) as { items?: GoiY[] } | null;
          if (!bo) setTim({ q, ds: d?.items ?? [], loi: !r.ok });
        })
        .catch(() => {
          if (!bo) setTim({ q, ds: [], loi: true });
        });
    }, 250);
    return () => {
      bo = true;
      clearTimeout(hen);
    };
  }, [q]);

  const ketQua = q && tim?.q === q ? tim : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2 sm:w-96">
        <label className="block">
          <span className={LABEL}>Tìm thuốc</span>
          <input
            value={go}
            placeholder="Gõ tên thuốc, số lô hoặc mã tem…"
            onChange={(e) => setGo(e.target.value)}
            className={INPUT}
          />
        </label>
        {ketQua ? (
          ketQua.ds.length > 0 ? (
            <ul className={`${TBL_WRAP} ${TBL_DIV}`}>
              {ketQua.ds.map((g) => (
                <li key={`${g.id}|${g.so_lo ?? ""}`}>
                  <button
                    type="button"
                    onClick={() => {
                      setGo("");
                      onChon({ id: g.id, lo: g.so_lo });
                    }}
                    className="min-h-10 w-full px-3 py-2 text-left text-body hover:bg-brand-50"
                  >
                    <span className="font-medium text-ink">{g.ten}</span>
                    {g.so_lo ? <span className="ml-2 text-ink-muted">Lô {g.so_lo}</span> : null}
                    {g.ma_hang ? <span className="ml-2 text-meta text-ink-muted">{g.ma_hang}</span> : null}
                    {g.dang_dung ? null : <span className="ml-2 text-meta text-ink-muted">Đã tắt</span>}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-body text-ink-muted">
              {ketQua.loi ? "Chưa tìm được, thử lại." : "Không thấy thuốc hay số lô nào khớp."}
            </p>
          )
        ) : null}
      </div>
      {chon ? (
        <ChiTietThuoc key={`${chon.id}|${chon.lo ?? ""}`} id={chon.id} loDau={chon.lo} />
      ) : (
        <p className="text-body text-ink-muted">
          Tìm một thuốc, hoặc bấm tên thuốc ở Thuốc trong kho, Danh mục, Báo cáo kho, để xem thuốc đang ở
          đâu và mọi lần nhập, chuyển, giao, trả, huỷ, kiểm kê: ai làm, lúc nào.
        </p>
      )}
    </div>
  );
}
