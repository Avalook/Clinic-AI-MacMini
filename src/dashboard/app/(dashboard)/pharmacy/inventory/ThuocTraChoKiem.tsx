"use client";

// Thuốc KHÁCH ĐÃ TRẢ mà chưa quyết xử lý (17/10/2026, việc B). Phần này đã nằm trong
// tồn nhưng bị trừ khỏi lượng bán được cho tới khi có người quyết MỘT lần:
//   · Nhập lại bán được — lượng bán được tăng lại, tồn không đổi.
//   · Huỷ               — tồn giảm đúng số trả, ghi hao hụt (bắt lý do).
// Máy chủ quyết quyền và luật (`POST /api/v1/pharmacy/xu-ly-thuoc-tra`); quyết rồi
// không sửa lại. Xác nhận ngay tại chỗ (không hộp thoại của trình duyệt).

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { INPUT, LABEL } from "../../form-ui";
import { guiKho, soKho, tienVnd } from "./gui-kho";

export interface DongTraChoKiem {
  id: string;
  thuoc: string | null;
  batch_code: string;
  unit: string | null;
  so_luong: number;
  gia_von: number | null;
  ly_do_tra: string;
  tra_luc: string;
  nguoi_tra: string | null;
  khach: string | null;
  ma_bn: string | null;
}

const fmtGio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

type Buoc = null | "BAN_LAI" | "HUY";

function Dong({ d, ghiDuoc }: { d: DongTraChoKiem; ghiDuoc: boolean }) {
  const router = useRouter();
  const [buoc, setBuoc] = useState<Buoc>(null);
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const donVi = d.unit ?? "";

  async function quyet(quyetDinh: "BAN_LAI" | "HUY") {
    setDang(true);
    setLoi(null);
    const kq = await guiKho("xu-ly-thuoc-tra", {
      drug_return_id: d.id,
      quyet_dinh: quyetDinh,
      ly_do: lyDo.trim() || null,
    });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    router.refresh();
  }

  return (
    <li
      aria-label={`${d.thuoc ?? "Thuốc"} khách trả`}
      className="space-y-2 rounded-card border border-line bg-surface p-4 shadow-card"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-emph font-semibold text-ink">
          {d.thuoc ?? "—"}{" "}
          <span className="text-body font-normal text-ink-muted">· lô {d.batch_code}</span>
        </p>
        <p className="text-emph font-semibold tabular-nums text-ink">
          {soKho(d.so_luong)} {donVi}
        </p>
      </div>
      <p className="text-meta text-ink-muted">
        {d.khach ?? "—"}
        {d.ma_bn ? ` · ${d.ma_bn}` : ""} · trả lúc {fmtGio(d.tra_luc)}
        {d.nguoi_tra ? ` · ${d.nguoi_tra} nhận` : ""}
      </p>
      <p className="text-body text-ink-soft">Lý do trả: {d.ly_do_tra}</p>

      {!ghiDuoc ? (
        <p className="text-meta text-ink-muted">Bạn chỉ xem — người có quyền kho sẽ quyết.</p>
      ) : buoc === null ? (
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="soft" onClick={() => setBuoc("BAN_LAI")}>
            Nhập lại bán được
          </Button>
          <Button type="button" variant="danger" onClick={() => setBuoc("HUY")}>
            Huỷ…
          </Button>
        </div>
      ) : buoc === "BAN_LAI" ? (
        <div className="space-y-2 rounded-control bg-surface-muted p-3">
          <p className="text-body text-ink">
            Nhập lại {soKho(d.so_luong)} {donVi} vào lượng bán được? Không sửa lại được sau khi xác
            nhận.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="primary" disabled={dang} onClick={() => void quyet("BAN_LAI")}>
              {dang ? "Đang lưu…" : "Xác nhận nhập lại"}
            </Button>
            <Button type="button" variant="ghost" disabled={dang} onClick={() => setBuoc(null)}>
              Thôi
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-2 rounded-control bg-surface-muted p-3">
          <label className="block">
            <span className={LABEL}>
              Lý do huỷ (bắt buộc) — tồn giảm {soKho(d.so_luong)} {donVi}
              {d.gia_von != null ? `, hao hụt khoảng ${tienVnd(d.gia_von * d.so_luong)}` : ""}
            </span>
            <input
              value={lyDo}
              onChange={(e) => setLyDo(e.target.value)}
              placeholder="vd Hộp đã mở, hết hạn, hỏng…"
              className={INPUT}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="danger"
              disabled={dang || lyDo.trim().length < 3}
              onClick={() => void quyet("HUY")}
            >
              {dang ? "Đang lưu…" : "Xác nhận huỷ"}
            </Button>
            <Button type="button" variant="ghost" disabled={dang} onClick={() => setBuoc(null)}>
              Thôi
            </Button>
          </div>
        </div>
      )}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </li>
  );
}

export default function ThuocTraChoKiem({
  dong,
  ghiDuoc,
}: {
  dong: DongTraChoKiem[];
  ghiDuoc: boolean;
}) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-meta text-ink-muted">
        Thuốc khách đã mang trả. Phần này nằm trong tồn nhưng chưa bán lại được cho tới khi bạn
        quyết: nhập lại bán được, hoặc huỷ nếu hỏng / hết hạn. Để đó cũng không sao — không chặn việc
        khác.
      </p>
      {dong.length === 0 ? (
        <p className="rounded-card border border-line bg-surface px-3 py-6 text-center text-ink-muted">
          Không có thuốc khách trả nào đang chờ kiểm.
        </p>
      ) : (
        <ul className="space-y-3">
          {dong.map((d) => (
            <Dong key={d.id} d={d} ghiDuoc={ghiDuoc} />
          ))}
        </ul>
      )}
    </div>
  );
}
