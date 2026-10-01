"use client";

// ĐỔI HÌNH THỨC THU sau khi đã thu (V7 — Tuyền chốt 30/09/2026; 01/10/2026: bỏ
// QR — gộp vào Chuyển khoản — và thêm CHIA Tiền mặt + Chuyển khoản).
//
// Thu nhầm Tiền mặt mà khách chuyển khoản (hay ngược lại, hay khách trả bằng cả
// hai): ai đứng quầy thu cũng đổi được, không phải huỷ phiếu rồi thu lại. Máy
// chủ quyết ĐỔI ĐƯỢC HAY KHÔNG (`doi.duoc` — phiếu đã huỷ / đã có khoản hoàn
// thì không), kiểm tổng khi chia, và giữ lịch sử đổi; màn chỉ vẽ.
// Lệnh: POST /api/payment { action: "doi-hinh-thuc" } → /api/v1/payments/doi-hinh-thuc.

import { useState } from "react";

import Button from "@/components/ui/Button";
import ChipChon from "@/components/ui/ChipChon";
import { docSoTien, tenHinhThuc, tien } from "@/lib/hinh-thuc-thu";

/** Hình thức như máy chủ trả (QR = phiếu cũ, đọc là Chuyển khoản). */
export type HinhThuc = "CASH" | "TRANSFER" | "QR";

export interface LanDoiHinhThuc {
  tu: HinhThuc | null;
  sang: HinhThuc;
  /** Đổi sang CHIA (01/10/2026): hai số; null = một hình thức. */
  tien_mat?: number | null;
  chuyen_khoan?: number | null;
  ma_gd: string | null;
  ly_do: string | null;
  boi: string | null;
  luc: string | null;
}

/** Do máy chủ trả kèm từng phiếu đã thu (`doi_hinh_thuc`). */
export interface TrangThaiDoi {
  duoc: boolean;
  ly_do_khong: string | null;
  hinh_thuc_goc: HinhThuc | null;
  lan_doi: LanDoiHinhThuc[];
}

type LuaChon = "CASH" | "TRANSFER" | "CHIA";
const TEN_LUA_CHON: Record<LuaChon, string> = {
  CASH: "Tiền mặt",
  TRANSFER: "Chuyển khoản",
  CHIA: "Chia tiền mặt + chuyển khoản",
};
const O = "min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink sm:min-h-8";

function gio(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

function nhanSang(l: LanDoiHinhThuc): string {
  if (l.tien_mat != null && l.chuyen_khoan != null) {
    return `Tiền mặt ${tien(l.tien_mat)} + Chuyển khoản ${tien(l.chuyen_khoan)}`;
  }
  return tenHinhThuc(l.sang);
}

export default function DoiHinhThuc({
  paymentCycleId,
  hinhThuc,
  soTien,
  doi,
  onXong,
}: {
  paymentCycleId: string;
  /** Hình thức HIỆU LỰC màn đang hiện (máy chủ đối chiếu, người khác vừa đổi → 409). */
  hinhThuc: string | null;
  /** Số tiền phiếu — để chia (phần tiền mặt = tổng − chuyển khoản). */
  soTien?: number | null;
  doi: TrangThaiDoi | null | undefined;
  onXong: () => void;
}) {
  const [mo, setMo] = useState(false);
  const [moi, setMoi] = useState<LuaChon | null>(null);
  const [soCk, setSoCk] = useState("");
  const [ma, setMa] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  if (!doi || (!doi.duoc && doi.lan_doi.length === 0)) return null;

  const tong = soTien ?? 0;
  const ck = docSoTien(soCk);
  const chiaHopLe = ck != null && ck > 0 && ck < tong;
  const coChia = tong > 1;
  const luaChon = (Object.keys(TEN_LUA_CHON) as LuaChon[]).filter(
    (k) => (k === "CHIA" ? coChia : true),
  );

  async function luu() {
    if (!moi) return;
    setDangGui(true);
    setLoi(null);
    try {
      const r = await fetch("/api/payment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "doi-hinh-thuc",
          paymentCycleId,
          hinhThuc: moi === "CHIA" ? null : moi,
          hinhThucCu: hinhThuc,
          tienMat: moi === "CHIA" && ck != null ? tong - ck : null,
          chuyenKhoan: moi === "CHIA" ? ck : null,
          reference: moi === "CASH" ? null : ma.trim() || null,
          lyDo: lyDo.trim() || null,
        }),
      });
      if (!r.ok) {
        const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
        setLoi(d?.message ?? d?.error ?? "Không đổi được hình thức. Thử lại giúp em.");
        return;
      }
      setMo(false);
      setMoi(null);
      setSoCk("");
      setMa("");
      setLyDo("");
      onXong();
    } finally {
      setDangGui(false);
    }
  }

  return (
    <div className="mt-1 space-y-1">
      {doi.lan_doi.map((l, i) => (
        <p key={`${l.luc}-${i}`} className="text-xs text-ink-muted">
          Đã đổi hình thức: {l.tu ? tenHinhThuc(l.tu) : "không rõ"} → <b className="text-ink">{nhanSang(l)}</b>
          {l.ma_gd ? ` · mã GD ${l.ma_gd}` : ""} · {gio(l.luc)} · {l.boi ?? "—"}
          {l.ly_do ? ` · ${l.ly_do}` : ""}
        </p>
      ))}
      {doi.duoc ? (
        mo ? (
          <div className="space-y-2 rounded-control bg-surface-muted p-2">
            <div role="radiogroup" aria-label="Hình thức mới" className="flex flex-wrap gap-2">
              {luaChon.map((k) => (
                <ChipChon key={k} kieu="mot" ten={`doi-ht-${paymentCycleId}`} chon={moi === k} onDoi={() => setMoi(k)}>
                  {TEN_LUA_CHON[k]}
                </ChipChon>
              ))}
            </div>
            {moi === "CHIA" ? (
              <div className="flex flex-wrap items-center gap-2 text-meta text-ink-soft">
                <label className="flex items-center gap-2">
                  Chuyển khoản
                  <input
                    inputMode="numeric"
                    aria-label="Số chuyển khoản"
                    value={soCk}
                    onChange={(e) => setSoCk(e.target.value)}
                    className={`${O} w-32 text-right tabular-nums`}
                  />
                </label>
                <span>
                  Tiền mặt: <b className="tabular-nums text-ink">{chiaHopLe && ck != null ? tien(tong - ck) : "—"}</b>
                  {" "}(tổng {tien(tong)})
                </span>
              </div>
            ) : null}
            <div className="flex flex-wrap items-end gap-2">
              {moi && moi !== "CASH" ? (
                <input
                  aria-label="Mã giao dịch (tuỳ chọn)"
                  placeholder="Mã giao dịch (tuỳ chọn)"
                  maxLength={100}
                  value={ma}
                  onChange={(e) => setMa(e.target.value)}
                  className={`${O} min-w-0 flex-1 basis-40`}
                />
              ) : null}
              <input
                aria-label="Lý do đổi (tuỳ chọn)"
                placeholder="Lý do (tuỳ chọn)"
                maxLength={500}
                value={lyDo}
                onChange={(e) => setLyDo(e.target.value)}
                className={`${O} min-w-0 flex-[2] basis-48`}
              />
            </div>
            <p className="text-xs text-ink-muted">
              Không phải huỷ phiếu: số tiền và phiếu giữ nguyên, báo cáo tính theo hình thức mới.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                size="sm"
                className="max-sm:h-10"
                disabled={dangGui || !moi || (moi === "CHIA" && !chiaHopLe)}
                onClick={() => void luu()}
              >
                Lưu hình thức mới
              </Button>
              <Button size="sm" variant="ghost" className="max-sm:h-10" onClick={() => setMo(false)}>
                Thôi
              </Button>
            </div>
          </div>
        ) : (
          <Button size="sm" variant="secondary" className="max-sm:h-10" onClick={() => setMo(true)}>
            Đổi hình thức
          </Button>
        )
      ) : null}
      {loi ? (
        <p role="alert" className="text-xs text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
