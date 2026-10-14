"use client";

// Hoá đơn công ty (G5c, Tuyền 14/10/2026): khách lấy hoá đơn về công ty thì ghi tên +
// địa chỉ + mã số thuế (+ email nhận hoá đơn) ngay trên phiếu thu. Lễ tân / CSKH /
// Thu ngân / Kế toán đều ghi được (máy chủ gác bằng quyền, không theo vai). Màn chỉ
// vẽ và gửi lệnh: lưu BẢN CHỤP theo hoá đơn, nhắc MST, lịch sử sửa, hoàn tác — mọi
// luật ở máy chủ.

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import ONhap from "@/components/ui/ONhap";

type CongTy = {
  id?: string;
  ten_cong_ty: string; dia_chi_cong_ty: string; ma_so_thue: string;
  email_nhan_hd: string; nguoi_mua: string;
};
type GoiY = CongTy & { id: string };
type Doc = { cong_ty: CongTy | null; cong_ty_da_bo: CongTy | null; da_bo: boolean; goi_y: GoiY[] };
type LichSu = {
  hanh_dong: string; sua_luc: string; sua_boi_ten: string | null;
  cu_ten: string; moi_ten: string; cu_ma_so_thue: string; moi_ma_so_thue: string;
};

const TRONG: CongTy = { ten_cong_ty: "", dia_chi_cong_ty: "", ma_so_thue: "", email_nhan_hd: "", nguoi_mua: "" };
const TEN_HANH_DONG: Record<string, string> = { ghi: "Ghi công ty", sua: "Sửa", bo: "Bỏ chọn", lai: "Chọn lại" };
const O: { k: keyof CongTy; ten: string; goiY?: string }[] = [
  { k: "ten_cong_ty", ten: "Tên công ty" },
  { k: "ma_so_thue", ten: "Mã số thuế", goiY: "10 số, hoặc 10 số-001" },
  { k: "dia_chi_cong_ty", ten: "Địa chỉ công ty" },
  { k: "email_nhan_hd", ten: "Email nhận hoá đơn" },
  { k: "nguoi_mua", ten: "Người mua (không bắt buộc)", goiY: "Để trống thì ô người mua trong file cũng để trống" },
];

function sangForm(c: CongTy): CongTy {
  return {
    ten_cong_ty: c.ten_cong_ty, dia_chi_cong_ty: c.dia_chi_cong_ty, ma_so_thue: c.ma_so_thue,
    email_nhan_hd: c.email_nhan_hd, nguoi_mua: c.nguoi_mua,
  };
}

export default function CongTyHoaDon({ paymentCycleId }: { paymentCycleId: string }) {
  const goc = `/api/hoa-don/cong-ty/phieu/${encodeURIComponent(paymentCycleId)}`;
  const [doc, setDoc] = useState<Doc | null>(null);
  const [khongQuyen, setKhongQuyen] = useState(false);
  const [mo, setMo] = useState(false);
  const [form, setForm] = useState<CongTy>(TRONG);
  const [khachCtId, setKhachCtId] = useState<string | null>(null);
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [nhac, setNhac] = useState<string | null>(null);
  const [lichSu, setLichSu] = useState<LichSu[] | null>(null);

  const tai = useCallback(async () => {
    try {
      const r = await fetch(goc, { cache: "no-store" });
      if (r.status === 403) { setKhongQuyen(true); return; }
      const d = await r.json();
      if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Không đọc được thông tin công ty.");
      setDoc(d);
    } catch (e) {
      setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ.");
    }
  }, [goc]);

  useEffect(() => {
    const t = setTimeout(() => { void tai(); }, 0);
    return () => clearTimeout(t);
  }, [tai]);

  if (khongQuyen) return null;

  const dangChon = doc?.cong_ty ?? null;
  const moForm = () => {
    // Điền sẵn: công ty đang ghi → công ty vừa bỏ → công ty khách dùng lần trước.
    const nguon = dangChon ?? doc?.cong_ty_da_bo ?? doc?.goi_y[0] ?? null;
    setForm(nguon ? sangForm(nguon) : TRONG);
    setKhachCtId(nguon && "id" in nguon && !dangChon ? (nguon.id ?? null) : null);
    setLoi(null); setNhac(null); setMo(true);
  };
  const chonGoiY = (g: GoiY) => { setForm(sangForm(g)); setKhachCtId(g.id); };

  const goi = async (method: "PUT" | "DELETE", body?: unknown) => {
    setDangLuu(true); setLoi(null); setNhac(null);
    try {
      const r = await fetch(goc, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Máy chủ chưa lưu được — thử lại.");
      if (typeof d.canh_bao_mst === "string") setNhac(d.canh_bao_mst);
      setMo(false); setLichSu(null);
      await tai();
    } catch (e) {
      setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ.");
    } finally { setDangLuu(false); }
  };

  const xemLichSu = async () => {
    const r = await fetch(`${goc}/lich-su`, { cache: "no-store" });
    const d = await r.json().catch(() => ({}));
    setLichSu(r.ok && Array.isArray(d.lich_su) ? d.lich_su : []);
  };

  return (
    <div className="mt-3 rounded-control bg-surface-muted p-3 text-body">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <b>Hoá đơn công ty</b>
        {!doc ? <span className="text-meta text-ink-muted">Đang tải…</span> : null}
        {doc && !mo ? (
          <span className="flex flex-wrap items-center gap-2">
            {dangChon ? <Button size="sm" onClick={moForm}>Sửa thông tin công ty</Button>
              : <Button size="sm" onClick={moForm}>{doc.da_bo ? "Chọn lại hoá đơn công ty" : "Xuất hoá đơn công ty"}</Button>}
            {dangChon ? <Button size="sm" variant="ghost" disabled={dangLuu} onClick={() => void goi("DELETE")}>Bỏ chọn</Button> : null}
            <Button size="sm" variant="ghost" onClick={() => void xemLichSu()}>Lịch sử</Button>
          </span>
        ) : null}
      </div>

      {doc && !mo ? (
        <p className="mt-1 text-meta text-ink-muted">
          {dangChon
            ? <>{dangChon.ten_cong_ty}{dangChon.ma_so_thue ? ` · MST ${dangChon.ma_so_thue}` : ""}{dangChon.dia_chi_cong_ty ? ` · ${dangChon.dia_chi_cong_ty}` : ""}</>
            : doc.da_bo ? "Đã bỏ chọn — hoá đơn xuất theo khách cá nhân. Chọn lại để quay về công ty vừa bỏ."
              : "Chưa chọn — hoá đơn xuất theo khách cá nhân."}
        </p>
      ) : null}
      {nhac ? <p role="status" className="mt-1 text-meta text-ink-muted">{nhac}</p> : null}
      {loi ? <p role="alert" className="mt-2 rounded-control bg-danger-bg p-2 text-danger">{loi}</p> : null}

      {mo && doc ? (
        <div className="mt-3 space-y-3">
          {doc.goi_y.length ? (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-meta text-ink-muted">Công ty của khách:</span>
              {doc.goi_y.map(g => (
                <Button key={g.id} size="sm" variant={khachCtId === g.id ? "soft" : "secondary"} onClick={() => chonGoiY(g)}>{g.ten_cong_ty}</Button>
              ))}
            </div>
          ) : null}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {O.map(o => (
              <label key={o.k} className="min-w-0 space-y-1 text-meta text-ink-muted">
                <span className="block">{o.ten}</span>
                <ONhap
                  className="w-full"
                  aria-label={o.ten}
                  value={form[o.k] ?? ""}
                  onChange={e => setForm({ ...form, [o.k]: e.target.value })}
                />
                {o.goiY ? <span className="block text-meta text-ink-faint">{o.goiY}</span> : null}
              </label>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" disabled={dangLuu || !form.ten_cong_ty.trim()}
              onClick={() => void goi("PUT", { ...form, khach_cong_ty_id: khachCtId })}>
              {dangLuu ? "Đang lưu…" : "Lưu công ty"}
            </Button>
            <Button variant="ghost" disabled={dangLuu} onClick={() => setMo(false)}>Đóng</Button>
          </div>
        </div>
      ) : null}

      {lichSu ? (
        <div className="mt-3 border-t border-dashed border-line pt-2">
          <b className="text-meta text-ink-muted">Lịch sử công ty trên hoá đơn này</b>
          {lichSu.length === 0 ? <p className="text-meta text-ink-muted">Chưa có thay đổi nào.</p> : (
            <ul className="divide-y divide-hairline">
              {lichSu.map((l, i) => (
                <li key={i} className="py-1 text-meta">
                  <span className="text-ink-muted">{new Date(l.sua_luc).toLocaleString("vi-VN")} · {l.sua_boi_ten ?? "—"} · </span>
                  {TEN_HANH_DONG[l.hanh_dong] ?? l.hanh_dong}: {l.cu_ten || "—"} → {l.moi_ten || "—"}
                  {l.cu_ma_so_thue !== l.moi_ma_so_thue ? ` (MST ${l.cu_ma_so_thue || "—"} → ${l.moi_ma_so_thue || "—"})` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}
