"use client";

// Khối "Đơn vị con và tính số ngày dùng hết thuốc" của Danh mục & giá (Tuyền 26/11).
// Chỉ ba câu: đơn vị con của [mẹ] là [viên ▼] · 1 [mẹ] có bao nhiêu [con] · giá 1 [con]
// (trống = máy chia giá mẹ). KHÔNG có nút lưu riêng (Tuyền: "bấm Lưu thuốc thôi"): form
// Danh mục gọi hàm lưu đã đăng ký qua `dangKy` trước khi lưu thuốc. Cách dùng gõ chữ ở
// ô "Cách dùng" phía trên — dòng "máy hiểu" đọc từ máy chủ.

import { useEffect, useRef, useState } from "react";

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

/** Hàm lưu khối đơn vị con: null = ổn (hoặc không đổi gì), chuỗi = câu lỗi. */
export type LuuDonViCon = () => Promise<string | null>;

export default function DonViCon({
  thuocId,
  ghiDuoc,
  dangKy,
}: {
  thuocId: string;
  ghiDuoc: boolean;
  dangKy: (luu: LuuDonViCon | null) => void;
}) {
  const [d, setD] = useState<DonViConMayChu | null>(null);
  const [f, setF] = useState<Form>({ con: "", so: "", gia: "" });
  const [loi, setLoi] = useState<string | null>(null);
  // Bản mới nhất cho hàm lưu (form cha gọi lúc bấm "Lưu thuốc").
  const hienTai = useRef<{ d: DonViConMayChu | null; f: Form }>({ d: null, f });
  useEffect(() => {
    hienTai.current = { d, f };
  }, [d, f]);

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

  useEffect(() => {
    if (!ghiDuoc) return dangKy(null);
    dangKy(async () => {
      const { d: goc, f: moi } = hienTai.current;
      if (!goc) return null;
      const cu = tuMayChu(goc);
      if (cu.con === moi.con.trim() && cu.so === moi.so.trim() && cu.gia === moi.gia.trim()) return null;
      const r = await goiThuoc<DonViConMayChu>("luu-don-vi-con", {
        body: {
          id: thuocId,
          don_vi_con: moi.con.trim() || null,
          so_con: moi.so.trim() === "" ? null : moi.so.trim().replace(",", "."),
          gia_con: moi.gia.trim() === "" ? null : moi.gia.replace(/\D/g, ""),
        },
      });
      if (!r.ok) {
        setLoi(r.loi);
        return `Đơn vị con: ${r.loi}`;
      }
      return null;
    });
    return () => dangKy(null);
  }, [thuocId, ghiDuoc, dangKy]);

  if (!d || d.id !== thuocId) return loi ? <p className="text-meta text-danger">{loi}</p> : null;

  const me = d.don_vi_me || "đơn vị tính";
  const con = f.con.trim() || "viên";
  const soCon = Number(f.so.replace(",", "."));
  const giaTuChia = d.gia_me != null && soCon > 0 ? Math.round(d.gia_me / soCon) : null;

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
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </section>
  );
}
