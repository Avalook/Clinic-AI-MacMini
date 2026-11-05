// (Client — chỉ `TheViec.tsx` dùng.) Bước "Thu hộ" của thẻ việc — hình theo bản mẫu
// 05/11 (Thu tiền → Tiền mặt / Chuyển khoản / cả hai). Giá chỉ là GỢI Ý: không tự tính
// phần còn lại, không ép thu đúng bằng giá (kế hoạch mục 3). Nút hiện theo cờ máy chủ.

import { useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";
import ONhap from "@/components/ui/ONhap";

import { tien, type Viec } from "./kieu";

export const O = ({ nhan, children }: { nhan: string; children: ReactNode }) => (
  <label className="flex flex-col gap-1 text-meta text-ink-soft">
    {nhan}
    {children}
  </label>
);

type Mo = null | "thu" | "hoan";

export default function BuocThuHo({
  v,
  dang,
  oLyDo,
  lyDo,
  onChay,
  onChoQua,
}: {
  v: Viec;
  dang: boolean;
  oLyDo: (nhan: string) => ReactNode;
  lyDo: string;
  onChay: (duong: string, body: unknown, bao: string) => Promise<boolean>;
  onChoQua: () => void;
}) {
  const [mo, setMo] = useState<Mo>(null);
  const [coTm, setCoTm] = useState(true);
  const [coCk, setCoCk] = useState(false);
  const [tm, setTm] = useState("");
  const [ck, setCk] = useState("");
  const [maGd, setMaGd] = useState("");
  const n = v.nut;

  async function chay(duong: string, body: unknown, bao: string) {
    if (await onChay(duong, body, bao)) setMo(null);
  }

  return (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="text-body font-semibold text-ink">Thu hộ</span>
        <span className="text-body tabular-nums text-ink-soft">
          {v.gia_goi_y !== null ? `Giá gợi ý ${tien(v.gia_goi_y)}` : "Chưa có giá gợi ý"}
        </span>
      </div>
      {v.da_thu !== null ? (
        <p className="text-meta text-ink-soft">
          Đã thu {tien(v.da_thu)} — tiền mặt {tien(v.tien_mat)}, chuyển khoản {tien(v.chuyen_khoan)}
          {v.ma_giao_dich ? ` · mã GD ${v.ma_giao_dich}` : ""} · không tính doanh thu
          {v.da_hoan ? ` · đã hoàn ${tien(v.da_hoan)}` : ""}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {n.ghi_thu && mo !== "thu" ? (
          <Button type="button" variant="primary" onClick={() => setMo("thu")}>
            Thu tiền
          </Button>
        ) : null}
        {n.hien_cho_qua ? (
          <Button type="button" variant="ghost" onClick={onChoQua}>
            Cho lấy mẫu trước (quản lý)
          </Button>
        ) : null}
        {n.hoan_tien ? (
          <Button type="button" variant="ghost" onClick={() => setMo("hoan")}>
            Hoàn tiền
          </Button>
        ) : null}
      </div>
      {mo === "thu" ? (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" variant={coTm ? "primary" : "secondary"} aria-pressed={coTm} onClick={() => setCoTm(!coTm)}>
              Tiền mặt
            </Button>
            <Button type="button" size="sm" variant={coCk ? "primary" : "secondary"} aria-pressed={coCk} onClick={() => setCoCk(!coCk)}>
              Chuyển khoản
            </Button>
            {coTm && coCk ? <span className="text-meta text-ink-muted">khách trả bằng cả hai</span> : null}
          </div>
          <div className="flex flex-wrap items-end gap-2">
            {coTm ? (
              <O nhan="Tiền mặt">
                <ONhap value={tm} inputMode="numeric" placeholder={tien(v.gia_goi_y)} onChange={(e) => setTm(e.target.value)} />
              </O>
            ) : null}
            {coCk ? (
              <>
                <O nhan="Chuyển khoản">
                  <ONhap value={ck} inputMode="numeric" placeholder={coTm ? "" : tien(v.gia_goi_y)} onChange={(e) => setCk(e.target.value)} />
                </O>
                <O nhan="Mã giao dịch">
                  <ONhap value={maGd} maxLength={100} onChange={(e) => setMaGd(e.target.value)} />
                </O>
              </>
            ) : null}
          </div>
          <p className="text-meta text-ink-muted">
            Ghi đúng số khách trả (giá gợi ý chỉ để tham khảo; miễn phí thì gõ 0). Tiền này của đối tác — không vào két.
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="primary"
              disabled={dang || (!coTm && !coCk)}
              onClick={() =>
                void chay(
                  "ghi-thu",
                  { order_id: v.order_id, tien_mat: coTm ? tm : "", chuyen_khoan: coCk ? ck : "", ma_giao_dich: coCk ? maGd : "" },
                  "Đã ghi nhận thu hộ.",
                )
              }
            >
              Ghi nhận thu hộ
            </Button>
            <Button type="button" variant="ghost" onClick={() => setMo(null)}>
              Thôi
            </Button>
          </div>
        </div>
      ) : null}
      {mo === "hoan" ? (
        <div className="flex flex-wrap items-end gap-2">
          <O nhan="Hoàn tiền mặt">
            <ONhap value={tm} inputMode="numeric" placeholder={tien(n.con_hoan_duoc)} onChange={(e) => setTm(e.target.value)} />
          </O>
          <O nhan="Hoàn chuyển khoản">
            <ONhap value={ck} inputMode="numeric" onChange={(e) => setCk(e.target.value)} />
          </O>
          {oLyDo("Lý do hoàn")}
          <Button
            type="button"
            variant="primary"
            disabled={dang}
            onClick={() => void chay("hoan-tien", { order_id: v.order_id, tien_mat: tm, chuyen_khoan: ck, ly_do: lyDo }, "Đã ghi hoàn tiền.")}
          >
            Hoàn
          </Button>
        </div>
      ) : null}
    </>
  );
}
