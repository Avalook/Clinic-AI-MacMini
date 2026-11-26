"use client";

// Cách dùng MẶC ĐỊNH có cấu trúc của một thuốc (PR E, kế hoạch đơn vị mẹ/con mục 2, 4)
// + "1 [đơn vị kho] có bao nhiêu [viên]" để màn kê đơn tính ngày dùng. Nằm trong form
// Sửa thuốc, có nút Lưu riêng (không đụng chữ "Cách dùng" cũ — thuốc "chỉ ghi chữ" vẫn
// in chữ đó). Câu máy sinh do máy chủ trả. Đề xuất hàng loạt từ câu chữ cũ: script
// chỉ đọc `scripts/de-xuat-cach-dung.py` để duyệt trước, không tự ghi.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { NHAN_KIEU, so, type CachDungCT, type KieuDung } from "@/lib/cach-dung";
import { goiThuoc } from "@/lib/goi-thuoc";
import { LABEL } from "../../form-ui";

interface MacDinh {
  id: string;
  don_vi_goc: string;
  ct: CachDungCT | null;
  so_lieu_moi_don_vi_goc: string | number | null;
  cau: string | null;
}

type Form = Record<"kieu" | "lan" | "lanDen" | "soLan" | "soLanDen" | "tu" | "den" | "trong" | "dvLieu" | "thoiDiem" | "soLieu", string>;

const chu = (x: unknown) => (x == null ? "" : String(so(x as string) ?? x));

function tuMacDinh(m: MacDinh): Form {
  const c = m.ct;
  return {
    kieu: c?.kieu ?? "chu",
    lan: chu(c?.khoang_lan ? c.khoang_lan[0] : c?.moi_lan),
    lanDen: chu(c?.khoang_lan?.[1]),
    soLan: chu(c?.khoang_so_lan ? c.khoang_so_lan[0] : c?.so_lan),
    soLanDen: chu(c?.khoang_so_lan?.[1]),
    tu: chu(c?.tu_ngay),
    den: chu(c?.den_ngay),
    trong: chu(c?.trong_ngay),
    dvLieu: c?.don_vi_lieu ?? "viên",
    thoiDiem: c?.thoi_diem ?? "",
    soLieu: chu(m.so_lieu_moi_don_vi_goc),
  };
}

/** Ô form → hình gửi máy chủ ("đến" có số = khoảng, bác sĩ chọn khi kê). Máy chủ kiểm. */
function sangCt(f: Form): CachDungCT | null {
  if (f.kieu === "chu") return { kieu: "chu" };
  const n = (s: string) => (s.trim() === "" ? null : so(s));
  return {
    kieu: f.kieu as KieuDung,
    moi_lan: f.lanDen.trim() ? null : n(f.lan),
    khoang_lan: f.lanDen.trim() ? [n(f.lan) ?? 0, n(f.lanDen) ?? 0] : null,
    so_lan: f.soLanDen.trim() ? null : n(f.soLan),
    khoang_so_lan: f.soLanDen.trim() ? [n(f.soLan) ?? 0, n(f.soLanDen) ?? 0] : null,
    tu_ngay: f.kieu === "chu_ky" ? n(f.tu) : null,
    den_ngay: f.kieu === "chu_ky" ? n(f.den) : null,
    trong_ngay: f.kieu === "chu_ky" ? null : n(f.trong),
    don_vi_lieu: f.dvLieu.trim() || "viên",
    thoi_diem: f.thoiDiem,
  };
}

export default function CachDungDanhMuc({ thuocId, ghiDuoc }: { thuocId: string; ghiDuoc: boolean }) {
  const [md, setMd] = useState<MacDinh | null>(null);
  const [f, setF] = useState<Form | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [dang, setDang] = useState(false);

  useEffect(() => {
    let bo = false;
    void goiThuoc<MacDinh>("cach-dung", { query: { id: thuocId } }).then((r) => {
      if (bo) return;
      if (r.ok) {
        setMd(r.data);
        setF(tuMacDinh(r.data));
      } else setLoi(r.loi);
    });
    return () => {
      bo = true;
    };
  }, [thuocId]);

  if (!md || !f || md.id !== thuocId) return loi ? <p className="text-meta text-danger">{loi}</p> : null;

  const luu = async () => {
    setDang(true);
    setLoi(null);
    setBao(null);
    const r = await goiThuoc<MacDinh>("luu-cach-dung", {
      body: { id: thuocId, ct: sangCt(f), so_lieu_moi_don_vi_goc: f.soLieu.trim() === "" ? null : f.soLieu.trim() },
    });
    setDang(false);
    if (!r.ok) return setLoi(r.loi);
    setMd(r.data);
    setF(tuMacDinh(r.data));
    setBao("Đã lưu cách dùng mặc định.");
  };

  const o = (ma: keyof Form, nhan: string, rong = "") => (
    <label className={`block ${rong}`}>
      <span className={LABEL}>{nhan}</span>
      <ONhap className="w-full" value={f[ma]} disabled={!ghiDuoc} onChange={(e) => setF({ ...f, [ma]: e.target.value })} />
    </label>
  );
  const coSo = f.kieu !== "chu";

  return (
    <section aria-label="Cách dùng có cấu trúc" className="space-y-2 rounded-card border border-hairline p-3">
      <h4 className="text-body font-semibold text-ink">Cách dùng có cấu trúc (để màn kê đơn tính số ngày)</h4>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <label className="col-span-2 block">
          <span className={LABEL}>Kiểu dùng</span>
          <OChon className="w-full" value={f.kieu} disabled={!ghiDuoc} onChange={(e) => setF({ ...f, kieu: e.target.value })}>
            {NHAN_KIEU.map(([v, t]) => (
              <option key={v} value={v}>
                {t}
              </option>
            ))}
          </OChon>
        </label>
        {o("soLieu", `1 ${md.don_vi_goc || "đơn vị kho"} có bao nhiêu ${f.dvLieu || "viên"}?`, "col-span-2")}
        {coSo ? (
          <>
            {o("lan", "Mỗi lần (số, cho 0,5)")}
            {o("lanDen", "…đến (nếu là khoảng)")}
            {f.kieu !== "cach_ngay" ? o("soLan", `Số lần/${f.kieu === "tuan" ? "tuần" : "ngày"}`) : null}
            {f.kieu !== "cach_ngay" ? o("soLanDen", "…đến (nếu là khoảng)") : null}
            {f.kieu === "chu_ky" ? o("tu", "Từ ngày chu kỳ") : o("trong", "Trong (ngày, tuỳ chọn)")}
            {f.kieu === "chu_ky" ? o("den", "Đến ngày chu kỳ") : null}
            {o("dvLieu", "Đơn vị liều (viên, gói…)")}
            {o("thoiDiem", "Thời điểm / ghi thêm", "col-span-2 sm:col-span-4")}
          </>
        ) : null}
      </div>
      {md.cau ? (
        <p className="text-meta text-ink-muted">
          Câu máy sinh (đã lưu): <span className="text-ink">{md.cau}</span>
        </p>
      ) : null}
      {ghiDuoc ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" variant="secondary" disabled={dang} onClick={() => void luu()}>
            {dang ? "Đang lưu…" : "Lưu cách dùng"}
          </Button>
          {bao ? <span className="text-meta text-success">{bao}</span> : null}
          {loi ? (
            <span role="alert" className="text-meta text-danger">
              {loi}
            </span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
