// (Client — chỉ `TheViec.tsx` dùng.) Bước "Thu hộ" của thẻ việc — hình theo bản mẫu
// 05/11 (Thu tiền → Tiền mặt / Chuyển khoản / cả hai). Giá chỉ là GỢI Ý: không tự tính
// phần còn lại, không ép thu đúng bằng giá (kế hoạch mục 3). Nút hiện theo cờ máy chủ.

import { useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";
import ONhap from "@/components/ui/ONhap";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";
import { thuNho } from "@/lib/thu-nho-anh";

import AnhChuyenKhoan, { type DichAnhCk } from "../thu-ngan/AnhChuyenKhoan";
import { tien, type Viec } from "./kieu";

/** "300.000" / "300000đ" → 300000; rỗng/rác → null. CHỈ để hiện "Trả lại khách"
 *  (phép trừ, không lưu) — số ghi sổ vẫn do máy chủ đọc (`o_nhap.doc_so_tien`). */
const soChu = (s: string): number | null => {
  const d = s.replace(/\D/g, "");
  return d ? Number(d) : null;
};

/** Đường ảnh CK của MỘT khoản thu hộ (bảng riêng — không dùng đường của quầy). */
function dichThuHo(thanhToanId: string): DichAnhCk {
  return {
    tai: async (tep) => {
      const fd = new FormData();
      fd.set("thanh_toan_id", thanhToanId);
      fd.set("file", await thuNho(tep), "chuyen-khoan.jpg");
      try {
        const r = await fetch("/api/xet-nghiem/anh-ck", { method: "POST", body: fd });
        return r.ok ? null : loiDocDuoc(await r.json().catch(() => null), "Không lưu được ảnh chuyển khoản.");
      } catch {
        return "Mất kết nối — ảnh chuyển khoản CHƯA được lưu.";
      }
    },
    xem: (id) => `/api/xet-nghiem/anh-ck?id=${encodeURIComponent(id)}`,
    go: async (id) => {
      try {
        const r = await fetch(`/api/xet-nghiem/ban/anh-ck/${encodeURIComponent(id)}/go`, { method: "POST" });
        return r.ok ? null : loiDocDuoc(await r.json().catch(() => null), "Không gỡ được ảnh.");
      } catch {
        return "Mất kết nối — chưa gỡ được ảnh.";
      }
    },
  };
}

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
  onAnh,
}: {
  v: Viec;
  dang: boolean;
  oLyDo: (nhan: string) => ReactNode;
  lyDo: string;
  onChay: (duong: string, body: unknown, bao: string) => Promise<boolean>;
  /** Ảnh CK vừa thêm / gỡ ⇒ tải lại bàn. */
  onAnh: () => void;
}) {
  const [mo, setMo] = useState<Mo>(null);
  const [coTm, setCoTm] = useState(true);
  const [coCk, setCoCk] = useState(false);
  const [tm, setTm] = useState("");
  const [ck, setCk] = useState("");
  const [maGd, setMaGd] = useState("");
  const [dua, setDua] = useState("");
  const n = v.nut;
  const giaChu = v.gia_goi_y !== null ? v.gia_goi_y.toLocaleString("vi-VN") : "";
  // Đổi hình thức trả: chỉ MỘT hình thức ⇒ ô của nó điền sẵn giá gợi ý (nếu ô đang
  // trống); cả hai ⇒ để người dùng tự chia, không tự tính phần còn lại.
  function doiHinhThuc(tmMoi: boolean, ckMoi: boolean) {
    setCoTm(tmMoi);
    setCoCk(ckMoi);
    if (tmMoi && !ckMoi && !tm) setTm(giaChu);
    if (ckMoi && !tmMoi && !ck) setCk(giaChu);
  }
  // Phép trừ hiển thị (bản mẫu): khách đưa − tiền mặt ghi. Không lưu, không chặn.
  const traLai = (() => {
    const a = soChu(dua);
    const b = soChu(tm) ?? v.gia_goi_y;
    return a !== null && b !== null && a > b ? a - b : null;
  })();

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
      {v.thu_id && v.chuyen_khoan ? (
        <AnhChuyenKhoan cycleId={v.thu_id} ds={v.anh_ck} onDoi={onAnh} dich={dichThuHo(v.thu_id)} />
      ) : null}
      <div className="flex flex-wrap gap-2">
        {n.ghi_thu && mo !== "thu" ? (
          <Button
            type="button"
            variant="primary"
            onClick={() => {
              // Điền SẴN giá gợi ý vào ô tiền mặt (Tuyền 05/11: bớt một thao tác) —
              // vẫn sửa được; máy chủ ghi đúng số còn trong ô, không ép bằng giá.
              setCoTm(true);
              setCoCk(false);
              setTm(giaChu);
              setCk("");
              setMo("thu");
            }}
          >
            Thu tiền
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
            <Button type="button" size="sm" variant={coTm ? "primary" : "secondary"} aria-pressed={coTm} onClick={() => doiHinhThuc(!coTm, coCk)}>
              Tiền mặt
            </Button>
            <Button type="button" size="sm" variant={coCk ? "primary" : "secondary"} aria-pressed={coCk} onClick={() => doiHinhThuc(coTm, !coCk)}>
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
          {coTm ? (
            <div className="flex flex-wrap items-end gap-2">
              <O nhan="Khách đưa (tiền mặt)">
                <ONhap value={dua} inputMode="numeric" placeholder="không bắt buộc" onChange={(e) => setDua(e.target.value)} />
              </O>
              {traLai !== null ? <span className="pb-2 text-body font-semibold text-success">Trả lại khách {tien(traLai)}</span> : null}
            </div>
          ) : null}
          {coCk ? (
            <p className="text-meta text-ink-soft">
              <span className="text-ink-muted">Chuyển khoản vào:</span>{" "}
              <b>{v.tai_khoan_nhan_ck ?? "chưa đặt tài khoản nhận (Cài đặt → Đối tác)"}</b>
            </p>
          ) : null}
          {coCk ? <p className="text-meta text-ink-muted">Ảnh chuyển khoản (không bắt buộc): thêm ngay sau khi ghi nhận.</p> : null}
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
