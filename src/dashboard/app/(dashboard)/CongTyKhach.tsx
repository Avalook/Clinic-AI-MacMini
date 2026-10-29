"use client";

// Công ty của khách trong HỒ SƠ (G5c, Tuyền 14/10/2026; 16/10 chỉ Kế toán + Quản lý ghi):
// tên + địa chỉ + MST công ty để điền sẵn vào hoá đơn. Một khách nhiều
// công ty được. Sửa ở đây KHÔNG đổi công ty đã ghi trên hoá đơn cũ (bản chụp). Gỡ = ẩn,
// khôi phục được. Máy chủ gác quyền; không có quyền thì khối ẩn.

import { useCallback, useEffect, useState } from "react";
import Button from "@/components/ui/Button";
import FormCongTy, { CONG_TY_TRONG, sangForm, type CongTy } from "./hoa-don/FormCongTy";

type Dong = CongTy & { id: string; an_luc: string | null };

export default function CongTyKhach({ clinicPatientId }: { clinicPatientId: string }) {
  const goc = `/api/hoa-don/cong-ty/khach/${encodeURIComponent(clinicPatientId)}`;
  const [ds, setDs] = useState<Dong[] | null>(null);
  const [khongQuyen, setKhongQuyen] = useState(false);
  const [sua, setSua] = useState<{ id: string | null; form: CongTy } | null>(null);
  const [hienAn, setHienAn] = useState(false);
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [nhac, setNhac] = useState<string | null>(null);

  const tai = useCallback(async () => {
    try {
      const r = await fetch(`${goc}?ca_da_an=true`, { cache: "no-store" });
      if (r.status === 403) { setKhongQuyen(true); return; }
      const d = await r.json();
      if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Không đọc được công ty của khách.");
      // Máy chủ trả "không được xem" thay vì 403 (khỏi một dòng lỗi mỗi lần mở hồ sơ).
      if (d.duoc_xem === false) { setKhongQuyen(true); return; }
      setDs(d.cong_ty);
    } catch (e) { setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); }
  }, [goc]);
  useEffect(() => {
    const t = setTimeout(() => { void tai(); }, 0);
    return () => clearTimeout(t);
  }, [tai]);

  if (khongQuyen) return null;

  const luu = async () => {
    if (!sua) return;
    setDangLuu(true); setLoi(null); setNhac(null);
    try {
      const r = await fetch(goc, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...sua.form, id: sua.id }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d.error === "string" ? d.error : "Máy chủ chưa lưu được — thử lại.");
      if (typeof d.canh_bao_mst === "string") setNhac(d.canh_bao_mst);
      setSua(null); await tai();
    } catch (e) { setLoi(e instanceof Error ? e.message : "Mất kết nối tới máy chủ."); }
    finally { setDangLuu(false); }
  };
  const an = async (id: string, go: boolean) => {
    setLoi(null);
    const r = await fetch(`/api/hoa-don/cong-ty/an/${encodeURIComponent(id)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ an: go }),
    });
    if (r.ok) await tai(); else setLoi("Máy chủ chưa lưu được — thử lại.");
  };

  const dangDung = (ds ?? []).filter(c => !c.an_luc);
  const daAn = (ds ?? []).filter(c => c.an_luc);
  return (
    <div className="space-y-2 rounded-control bg-surface-muted p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <b className="text-body text-ink">Công ty xuất hoá đơn</b>
        {!sua ? <Button size="sm" onClick={() => { setSua({ id: null, form: CONG_TY_TRONG }); setNhac(null); }}>Thêm công ty</Button> : null}
      </div>
      {loi ? <p role="alert" className="rounded-control bg-danger-bg p-2 text-danger">{loi}</p> : null}
      {nhac ? <p role="status" className="text-meta text-ink-muted">{nhac}</p> : null}
      {ds && !dangDung.length && !sua ? <p className="text-meta text-ink-muted">Chưa ghi công ty nào. Khách cần hoá đơn công ty thì thêm ở đây — lúc thu sẽ được điền sẵn.</p> : null}
      {dangDung.length ? (
        <ul className="divide-y divide-hairline">
          {dangDung.map(c => (
            <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-body">
              <span className="min-w-0 break-words">{c.ten_cong_ty}
                <span className="block text-meta text-ink-muted">{[c.ma_so_thue && `MST ${c.ma_so_thue}`, c.dia_chi_cong_ty].filter(Boolean).join(" · ") || "—"}</span>
              </span>
              <span className="flex gap-2">
                <Button size="sm" onClick={() => { setSua({ id: c.id, form: sangForm(c) }); setNhac(null); }}>Sửa</Button>
                <Button size="sm" variant="ghost" onClick={() => void an(c.id, true)}>Gỡ</Button>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {sua ? (
        <div className="space-y-3">
          <FormCongTy form={sua.form} onDoi={f => setSua({ ...sua, form: f })} />
          <p className="text-meta text-ink-muted">Sửa ở đây không đổi công ty đã ghi trên các hoá đơn cũ.</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" disabled={dangLuu || !sua.form.ten_cong_ty.trim()} onClick={() => void luu()}>{dangLuu ? "Đang lưu…" : "Lưu công ty"}</Button>
            <Button variant="ghost" disabled={dangLuu} onClick={() => setSua(null)}>Đóng</Button>
          </div>
        </div>
      ) : null}
      {daAn.length ? (
        <div>
          <Button size="sm" variant="ghost" onClick={() => setHienAn(!hienAn)}>{hienAn ? "Ẩn" : "Hiện"} {daAn.length} công ty đã gỡ</Button>
          {hienAn ? (
            <ul className="divide-y divide-hairline">
              {daAn.map(c => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-body text-ink-muted">
                  <span className="min-w-0 break-words">{c.ten_cong_ty}</span>
                  <Button size="sm" onClick={() => void an(c.id, false)}>Khôi phục</Button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
