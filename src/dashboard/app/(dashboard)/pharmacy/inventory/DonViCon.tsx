"use client";

// Khối "Đơn vị con và tính số ngày dùng hết thuốc" của Danh mục & giá (Tuyền 26/11).
// Chỉ ba câu: đơn vị con của [mẹ] là [viên ▼] · 1 [mẹ] có bao nhiêu [con] · giá 1 [con]
// (trống = máy chia giá mẹ). Cách dùng gõ chữ ở ô "Cách dùng" phía trên — dòng "máy hiểu"
// dưới đây đọc từ máy chủ để kho thấy câu gõ đã được hiểu đúng chưa.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import ONhap from "@/components/ui/ONhap";
import { goiThuoc } from "@/lib/goi-thuoc";
import { LABEL } from "../../form-ui";

type DonViConMayChu = {
  id: string;
  don_vi_me: string;
  don_vi_con: string | null;
  so_con: string | number | null;
  gia_me: number | null;
  gia_con: number | null;
  gia_con_tu_tinh: number | null;
  xem_truoc: string;
  goi_y: string[];
};

type Form = { con: string; so: string; gia: string };

const tuMayChu = (d: DonViConMayChu): Form => ({
  con: d.don_vi_con ?? "",
  so: d.so_con == null ? "" : String(Number(d.so_con)),
  gia: d.gia_con == null ? "" : String(d.gia_con),
});

const tienVn = (n: number) => `${n.toLocaleString("vi-VN")} đ`;

export default function DonViCon({ thuocId, ghiDuoc }: { thuocId: string; ghiDuoc: boolean }) {
  const [d, setD] = useState<DonViConMayChu | null>(null);
  const [f, setF] = useState<Form>({ con: "", so: "", gia: "" });
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [dang, setDang] = useState(false);

  useEffect(() => {
    let bo = false;
    void goiThuoc<DonViConMayChu>("don-vi-con", { query: { id: thuocId } }).then((r) => {
      if (bo) return;
      if (r.ok) {
        setD(r.data);
        setF(tuMayChu(r.data));
      } else setLoi(r.loi);
    });
    return () => {
      bo = true;
    };
  }, [thuocId]);

  if (!d || d.id !== thuocId) return loi ? <p className="text-meta text-danger">{loi}</p> : null;

  const me = d.don_vi_me || "đơn vị tính";
  const con = f.con.trim() || "viên";
  const soCon = Number(f.so.replace(",", "."));
  const giaTuChia = d.gia_me != null && soCon > 0 ? Math.round(d.gia_me / soCon) : null;

  const luu = async () => {
    setDang(true);
    setLoi(null);
    setBao(null);
    const r = await goiThuoc<DonViConMayChu>("luu-don-vi-con", {
      body: {
        id: thuocId,
        don_vi_con: f.con.trim() || null,
        so_con: f.so.trim() === "" ? null : f.so.trim().replace(",", "."),
        gia_con: f.gia.trim() === "" ? null : f.gia.replace(/\D/g, ""),
      },
    });
    setDang(false);
    if (!r.ok) return setLoi(r.loi);
    setD(r.data);
    setF(tuMayChu(r.data));
    setBao("Đã lưu đơn vị con.");
  };

  return (
    <section aria-label="Đơn vị con" className="space-y-2 rounded-card border border-hairline p-3">
      <h4 className="text-body font-semibold text-ink">Đơn vị con và tính số ngày dùng hết thuốc</h4>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <label className="block">
          <span className={LABEL}>Đơn vị con của {me} là</span>
          <ONhap
            className="w-full"
            list="don-vi-con-goi-y"
            value={f.con}
            placeholder="vd viên"
            disabled={!ghiDuoc}
            onChange={(e) => setF({ ...f, con: e.target.value })}
          />
          <datalist id="don-vi-con-goi-y">
            {d.goi_y.map((x) => (
              <option key={x} value={x} />
            ))}
          </datalist>
        </label>
        <label className="block">
          <span className={LABEL}>
            1 {me} có bao nhiêu {con}?
          </span>
          <ONhap
            className="w-full"
            inputMode="decimal"
            value={f.so}
            placeholder="vd 30"
            disabled={!ghiDuoc}
            onChange={(e) => setF({ ...f, so: e.target.value })}
          />
        </label>
        <label className="block">
          <span className={LABEL}>Giá 1 {con} (đ)</span>
          <ONhap
            className="w-full"
            inputMode="numeric"
            value={f.gia}
            placeholder={giaTuChia != null ? `Tự tính: ${tienVn(giaTuChia)}` : "Trống = giá mẹ ÷ số con"}
            disabled={!ghiDuoc}
            onChange={(e) => setF({ ...f, gia: e.target.value })}
          />
        </label>
      </div>
      <p className="text-meta text-ink-muted" role="status">
        Máy hiểu cách dùng: {d.xem_truoc}
      </p>
      {ghiDuoc ? (
        <Button type="button" size="sm" variant="secondary" disabled={dang} onClick={() => void luu()}>
          {dang ? "Đang lưu…" : "Lưu đơn vị con"}
        </Button>
      ) : null}
      {bao ? <p className="text-meta text-success">{bao}</p> : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}
