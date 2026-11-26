"use client";

// Đổi TÊN đơn vị gốc (26/11/2026, PR C): thuốc mang tên gốc kiểu "hộp 60 viên" mà
// kho thực chất đang đếm viên → đổi chữ thành "viên" + khai "1 hộp có 60 viên".
// Số tồn giữ nguyên; giá cũ thành giá hộp; giá viên nhập hoặc để trống (chia từ giá
// hộp). Máy chủ kiểm mọi luật và soạn câu báo (`POST /api/pharmacy/doi-ten-goc`);
// hoàn tác là lệnh bù có lý do (`hoan-tac-doi-ten-goc`). Ở đây chỉ gom ô và vẽ.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { INPUT, LABEL } from "../../form-ui";
import { guiKho } from "./gui-kho";

const TRONG = { ten_moi: "", don_vi_me: "", he_so_me: "", gia_goc_moi: "", ly_do: "" };

export default function DoiTenGoc({ idThuoc, goc }: { idThuoc: string; goc: string }) {
  const router = useRouter();
  const [mo, setMo] = useState(false);
  const [f, setF] = useState(TRONG);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<{ su_kien_id: string; cau: string } | null>(null);
  const [lyDoHoan, setLyDoHoan] = useState("");
  const [bao, setBao] = useState<string | null>(null);
  // Đổi tên KHÔNG nhân số tồn: bắt người đổi xác nhận số đang là đơn vị nhỏ (26/11).
  const [daKiem, setDaKiem] = useState(false);

  const doi = async () => {
    setDang(true);
    setLoi(null);
    const kq = await guiKho("doi-ten-goc", { drug_catalog_id: idThuoc, ...f });
    setDang(false);
    if (!kq.ok) return setLoi(kq.loi);
    setXong(kq.data as { su_kien_id: string; cau: string });
    router.refresh();
  };

  const hoanTac = async () => {
    if (!xong) return;
    setDang(true);
    setLoi(null);
    const kq = await guiKho("hoan-tac-doi-ten-goc", {
      su_kien_id: xong.su_kien_id,
      ly_do: lyDoHoan,
    });
    setDang(false);
    if (!kq.ok) return setLoi(kq.loi);
    setXong(null);
    setBao((kq.data as { cau: string }).cau);
    router.refresh();
  };

  const o = (ma: keyof typeof TRONG, nhan: string, goiY: string) => (
    <label className="block min-w-0">
      <span className={LABEL}>{nhan}</span>
      <input
        value={f[ma]}
        placeholder={goiY}
        inputMode={ma === "he_so_me" || ma === "gia_goc_moi" ? "decimal" : undefined}
        onChange={(e) => setF({ ...f, [ma]: e.target.value })}
        className={INPUT}
      />
    </label>
  );

  if (!goc.trim()) return null;
  if (!mo) {
    return (
      <Button type="button" size="sm" variant="ghost" onClick={() => setMo(true)}>
        Đổi tên đơn vị gốc…
      </Button>
    );
  }
  const vien = f.ten_moi.trim() || "viên";
  const hop = f.don_vi_me.trim() || "hộp";
  return (
    <section aria-label="Đổi tên đơn vị gốc" className="space-y-2 rounded-control border border-line p-3">
      <h4 className="text-body font-semibold text-ink">Đổi tên đơn vị gốc “{goc}”</h4>
      <p className="text-meta text-ink-muted">
        Dùng khi kho thực chất đang đếm đơn vị nhỏ (vd viên). Số tồn giữ nguyên, chỉ đổi tên; giá
        đang có thành giá 1 {hop}.
      </p>
      {xong ? (
        <div className="space-y-2">
          <p role="status" className="text-body text-ink">
            {xong.cau} Đóng form rồi mở lại thuốc này để sửa tiếp.
          </p>
          <div className="flex flex-wrap items-end gap-2">
            <label className="block min-w-0 flex-1">
              <span className={LABEL}>Lý do hoàn tác</span>
              <input value={lyDoHoan} onChange={(e) => setLyDoHoan(e.target.value)} className={INPUT} />
            </label>
            <Button type="button" size="sm" variant="secondary" disabled={dang || !lyDoHoan.trim()} onClick={() => void hoanTac()}>
              Hoàn tác
            </Button>
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {o("ten_moi", "Tên mới — kho đếm theo", "vd viên")}
            {o("don_vi_me", "Đơn vị lớn (mặc định khi kê)", "vd hộp")}
            {o("he_so_me", `1 ${hop} có bao nhiêu ${vien}?`, "vd 60")}
            {o("gia_goc_moi", `Giá 1 ${vien} (đ)`, `Trống = chia từ giá ${hop}`)}
            {o("ly_do", "Lý do (không bắt buộc)", "")}
          </div>
          <label className="flex items-start gap-2 rounded-control bg-warning-bg p-2 text-meta text-ink">
            <input type="checkbox" checked={daKiem} onChange={(e) => setDaKiem(e.target.checked)} />
            <span>
              Tôi đã đếm lại: số tồn đang ghi là số <b>{vien}</b>, không phải số {goc}. (Đổi tên
              không nhân số — kho đang đếm theo {goc} thật thì <b>không</b> dùng nút này.)
            </span>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="primary" disabled={dang || !daKiem} onClick={() => void doi()}>
              {dang ? "Đang đổi…" : "Đổi tên"}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setMo(false)}>
              Thôi
            </Button>
          </div>
        </>
      )}
      {bao ? (
        <p role="status" className="text-meta text-ink">
          {bao} Đóng form rồi mở lại thuốc này để sửa tiếp.
        </p>
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}
