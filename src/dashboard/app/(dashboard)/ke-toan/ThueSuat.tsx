"use client";

// Thuế GTGT cho kế toán (G5b backend → màn này, Tuyền 14/10/2026): kế toán đặt thuế suất
// theo NHÓM hàng (Dịch vụ / Thuốc / Vật tư) và theo TỪNG mặt hàng; giá trong bảng giá đã
// gồm thuế, khi xuất hoá đơn máy chủ tách ngược. Thứ tự ưu tiên: sửa tay dòng khi xuất >
// mặt hàng > nhóm > chưa đặt. Màn chỉ chọn và gửi; máy chủ chuẩn hoá, kiểm quyền, ghi sự
// kiện. Thuế KHÔNG chạm quầy thu / hoá đơn / báo cáo ngày.

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { MUC_THUE, TEN_NHOM_HANG, tenThueSuat } from "./thue-suat";

type MatHang = { loai: string; id: string; ma: string; ten: string; thue_suat_ma: string | null };
type Data = { nhom: Record<string, string | null>; mat_hang: MatHang[]; duoc_dat: boolean };
const NHOM = ["DICH_VU", "THUOC", "VAT_TU"] as const;
const TEN_LOAI: Record<string, string> = { dich_vu: "Dịch vụ", thuoc: "Thuốc", vat_tu: "Vật tư" };
const KHAC = "__khac";

function ONhomThue({ gia, theoNhom, khoa, onDat, nhan }: {
  gia: string | null; theoNhom?: boolean; khoa: boolean; onDat: (v: string) => void; nhan: string;
}) {
  const laMucSan = gia !== null && MUC_THUE.some(([m]) => m === gia);
  const [khac, setKhac] = useState(gia !== null && !laMucSan);
  const [nhapKhac, setNhapKhac] = useState(gia !== null && !laMucSan ? gia : "");
  const chon = khac ? KHAC : (gia ?? "");
  return (
    <span className="flex flex-wrap items-center gap-2">
      <OChon aria-label={nhan} disabled={khoa} className="min-w-44" value={chon}
        onChange={e => {
          const v = e.target.value;
          if (v === KHAC) { setKhac(true); return; }
          setKhac(false); onDat(v);
        }}>
        <option value="">{theoNhom ? "Theo nhóm hàng" : "Chưa đặt"}</option>
        {MUC_THUE.map(([m, ten]) => <option key={m} value={m}>{ten}</option>)}
        <option value={KHAC}>Khác (nhập %)…</option>
      </OChon>
      {khac ? (
        <>
          <ONhap aria-label={`${nhan} — phần trăm khác`} inputMode="decimal" className="w-24" disabled={khoa}
            value={nhapKhac} onChange={e => setNhapKhac(e.target.value)} placeholder="vd 8,5" />
          <Button size="sm" disabled={khoa || !nhapKhac.trim()} onClick={() => onDat(nhapKhac)}>Đặt</Button>
        </>
      ) : null}
    </span>
  );
}

export default function ThueSuat() {
  const [data, setData] = useState<Data | null>(null);
  const [tim, setTim] = useState("");
  const [loi, setLoi] = useState<string | null>(null);
  const [vua, setVua] = useState<{ nhan: string; hoanTac: () => void } | null>(null);

  const tai = useCallback(async (chuoi: string) => {
    try {
      const r = await fetch(`/api/ke-toan/thue-suat?tim=${encodeURIComponent(chuoi)}`, { cache: "no-store" });
      const d = await r.json();
      if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Không đọc được thuế suất.");
      setData(d); setLoi(null);
    } catch (e) { setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); }
  }, []);
  useEffect(() => {
    const t = setTimeout(() => void tai(tim.trim()), 250);
    return () => clearTimeout(t);
  }, [tai, tim]);

  const gui = async (url: string, body: unknown): Promise<boolean> => {
    setLoi(null);
    const r = await fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { setLoi(typeof d.error === "string" ? d.error : "Máy chủ chưa lưu được — thử lại."); return false; }
    await tai(tim.trim());
    return true;
  };
  const datNhom = async (nhom: string, moi: string, cu: string | null) => {
    if (!(await gui(`/api/ke-toan/thue-suat/nhom/${nhom}`, { thue_suat: moi }))) return;
    setVua({ nhan: `${TEN_NHOM_HANG[nhom]}: ${tenThueSuat(moi) || "bỏ đặt"}`, hoanTac: () => { void gui(`/api/ke-toan/thue-suat/nhom/${nhom}`, { thue_suat: cu ?? "" }).then(() => setVua(null)); } });
  };
  const datMatHang = async (h: MatHang, moi: string) => {
    const cu = h.thue_suat_ma;
    if (!(await gui("/api/ke-toan/thue-suat/mat-hang", { loai: h.loai, id: h.id, thue_suat: moi }))) return;
    setVua({ nhan: `${h.ten}: ${tenThueSuat(moi) || "theo nhóm"}`, hoanTac: () => { void gui("/api/ke-toan/thue-suat/mat-hang", { loai: h.loai, id: h.id, thue_suat: cu ?? "" }).then(() => setVua(null)); } });
  };

  const khoa = !data?.duoc_dat;
  return (
    <div className="min-w-0 space-y-4">
      {loi ? <p role="alert" className="rounded-control bg-danger-bg p-3 text-body text-danger">{loi}</p> : null}
      {data && khoa ? <p role="status" className="rounded-control bg-surface-muted p-3 text-body text-ink-muted">Bạn chỉ xem thuế suất — muốn đặt cần quyền “Đặt thuế suất GTGT” (Quản lý cấp trong Phân quyền).</p> : null}
      {vua ? (
        <p role="status" className="flex flex-wrap items-center gap-2 rounded-control bg-info-bg p-3 text-body text-info">
          Đã lưu — {vua.nhan}
          <Button size="sm" variant="ghost" onClick={vua.hoanTac}>Hoàn tác</Button>
        </p>
      ) : null}

      <section className="space-y-3 rounded-card bg-surface p-4 ring-1 ring-hairline">
        <div>
          <h2 className="text-emph font-semibold text-ink">Thuế suất theo nhóm hàng</h2>
          <p className="text-meta text-ink-muted">Áp cho mọi mặt hàng của nhóm chưa có thuế riêng. Giá trong bảng giá đã gồm thuế.</p>
        </div>
        {!data ? <p role="status" className="text-body text-ink-muted">Đang tải…</p> : (
          <ul className="divide-y divide-hairline">
            {NHOM.map(n => (
              <li key={`${n}-${data.nhom[n] ?? ""}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="text-body text-ink">{TEN_NHOM_HANG[n]}</span>
                <ONhomThue gia={data.nhom[n]} khoa={khoa} nhan={`Thuế suất nhóm ${TEN_NHOM_HANG[n]}`} onDat={v => void datNhom(n, v, data.nhom[n])} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3 rounded-card bg-surface p-4 ring-1 ring-hairline">
        <div>
          <h2 className="text-emph font-semibold text-ink">Thuế suất theo từng mặt hàng</h2>
          <p className="text-meta text-ink-muted">Gõ tên hoặc mã để tìm (tối đa 50 mặt hàng). Mặt hàng có thuế riêng thì lấy mức riêng, không theo nhóm.</p>
        </div>
        <ONhap aria-label="Tìm mặt hàng" className="w-full sm:w-80" placeholder="Tên hoặc mã mặt hàng" value={tim} onChange={e => setTim(e.target.value)} />
        {data && tim.trim() && data.mat_hang.length === 0 ? <p className="text-body text-ink-muted">Không có mặt hàng nào khớp.</p> : null}
        {data && data.mat_hang.length ? (
          <ul className="divide-y divide-hairline">
            {data.mat_hang.map(h => (
              <li key={`${h.loai}-${h.id}-${h.thue_suat_ma ?? ""}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="min-w-0 text-body text-ink">{h.ten}
                  <span className="block text-meta text-ink-muted">{TEN_LOAI[h.loai] ?? h.loai}{h.ma ? ` · ${h.ma}` : ""}</span>
                </span>
                <ONhomThue gia={h.thue_suat_ma} theoNhom khoa={khoa} nhan={`Thuế suất ${h.ten}`} onDat={v => void datMatHang(h, v)} />
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}
