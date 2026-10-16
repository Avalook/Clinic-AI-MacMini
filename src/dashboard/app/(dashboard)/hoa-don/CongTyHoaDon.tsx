"use client";

// Hoá đơn công ty (G5c, Tuyền 14/10/2026): khách lấy hoá đơn về công ty thì ghi tên +
// địa chỉ + mã số thuế (+ email nhận hoá đơn) ngay trên phiếu thu. Lễ tân / CSKH /
// Thu ngân / Kế toán đều ghi được (máy chủ gác bằng quyền, không theo vai). Màn chỉ
// vẽ và gửi lệnh: lưu BẢN CHỤP theo hoá đơn, nhắc MST, lịch sử sửa, hoàn tác — mọi
// luật ở máy chủ.

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import FormCongTy, { CONG_TY_TRONG, sangForm, type CongTy } from "./FormCongTy";

type GoiY = CongTy & { id: string };
/** Bản chụp đang ghi / vừa bỏ — `khach_cong_ty_id` trỏ tới công ty trong hồ sơ khách. */
type BanChup = CongTy & { khach_cong_ty_id: string | null };
type Doc = { cong_ty: BanChup | null; cong_ty_da_bo: BanChup | null; da_bo: boolean; goi_y: GoiY[] };
type LichSu = {
  hanh_dong: string; sua_luc: string; sua_boi_ten: string | null;
  cu_ten: string; moi_ten: string; cu_ma_so_thue: string; moi_ma_so_thue: string;
};

const TEN_HANH_DONG: Record<string, string> = { ghi: "Ghi công ty", sua: "Sửa", bo: "Bỏ chọn", lai: "Chọn lại" };
export default function CongTyHoaDon({ paymentCycleId }: { paymentCycleId: string }) {
  const goc = `/api/hoa-don/cong-ty/phieu/${encodeURIComponent(paymentCycleId)}`;
  const [doc, setDoc] = useState<Doc | null>(null);
  const [khongQuyen, setKhongQuyen] = useState(false);
  const [mo, setMo] = useState(false);
  const [form, setForm] = useState<CongTy>(CONG_TY_TRONG);
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
    const ban = dangChon ?? doc?.cong_ty_da_bo ?? null;
    const goiY = doc?.goi_y[0] ?? null;
    setForm(ban ? sangForm(ban) : goiY ? sangForm(goiY) : CONG_TY_TRONG);
    setKhachCtId(ban ? ban.khach_cong_ty_id : (goiY?.id ?? null));
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
          <FormCongTy form={form} onDoi={setForm} />
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
