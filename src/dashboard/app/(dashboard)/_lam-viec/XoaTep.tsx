"use client";

// XOÁ / HOÀN TÁC TỆP KẾT QUẢ (V9, Tuyền chốt 30/09/2026) — dùng chung cho khung
// tệp phòng dịch vụ (`KhungTep`), từng ảnh (`AnhKetQua`), hộp xem (`Lightbox`),
// màn Khách hàng (`customers/TepKetQua`) và bàn Đối tác (`BangDoiTac`).
//
// KHÔNG CÓ LUẬT Ở ĐÂY. Ai xoá được, xoá thường hay "Đính chính – gỡ tệp", khôi
// phục được không — máy chủ quyết và trả cờ (`xoa_duoc`, `xoa_loai`,
// `xoa_ly_do`, `khoi_phuc_duoc`). Nút chỉ hiện khi cờ cho; không cho thì hiện
// câu lý do máy chủ trả. Xoá là XOÁ MỀM: tệp ẩn khỏi mọi màn, khôi phục được
// trong 30 ngày.

import { useState } from "react";
import { RotateCcw, Trash2 } from "lucide-react";

import Button from "@/components/ui/Button";
import ChipChon from "@/components/ui/ChipChon";
import { NUT_NEN_TOI } from "@/components/ui/Lightbox";
import PopoverNeo from "@/components/ui/PopoverNeo";
import { nhanLoi } from "@/lib/loi-api";
import { LY_DO_XOA_TEP, ghepLyDoXoa } from "@/lib/ly-do-xoa-tep";

/** Cờ máy chủ gắn vào mỗi tệp CÒN HIỆU LỰC. */
export interface CoXoaTep {
  xoa_duoc?: boolean;
  /** XOA | DINH_CHINH */
  xoa_loai?: string | null;
  /** Không được thì vì sao; Đính chính thì câu nhắc. */
  xoa_ly_do?: string | null;
}

/** Tệp đã xoá mềm (≤30 ngày, tệp vật lý còn) — `da_xoa` của danh sách tệp. */
export interface TepDaXoa {
  id: string;
  ten_hien_thi: string | null;
  service_order_id: string | null;
  appointment_id: string | null;
  ben?: number | null;
  da_xoa_luc: string;
  da_xoa_ly_do: string | null;
  da_xoa_loai: string | null;
  da_xoa_boi: string | null;
  khoi_phuc_duoc?: boolean;
  khoi_phuc_ly_do?: string | null;
  khoi_phuc_han?: string | null;
}

const O_CHU =
  "w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink placeholder:text-ink-faint";

function ngayGio(iso: string | null | undefined): string {
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

async function goi(duong: string, than: unknown): Promise<string | null> {
  try {
    const r = await fetch(duong, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    if (r.ok) return null;
    return nhanLoi(await r.json().catch(() => null), "Máy chủ từ chối.");
  } catch {
    return "Mất kết nối — chưa ghi được. Thử lại.";
  }
}

/** Khôi phục một tệp đã xoá. Trả câu lỗi, hoặc null nếu xong. */
export function khoiPhucTep(id: string): Promise<string | null> {
  return goi(`/api/cskh/ket-qua/${encodeURIComponent(id)}/khoi-phuc`, {});
}

/** Nút Xoá (hoặc "Đính chính – gỡ tệp") + popover chọn lý do. */
export function NutXoaTep({
  tepId,
  ten,
  co,
  nenToi = false,
  gon = false,
  onDaXoa,
}: {
  tepId: string;
  ten: string | null;
  co: CoXoaTep;
  /** Trên nền tối của hộp xem (Lightbox). */
  nenToi?: boolean;
  /** Chỉ biểu tượng (ô ảnh nhỏ). */
  gon?: boolean;
  onDaXoa: () => void;
}) {
  const [neo, setNeo] = useState<HTMLElement | null>(null);
  const [ma, setMa] = useState<string | null>(null);
  const [ghi, setGhi] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  if (!co.xoa_duoc) {
    // Máy chủ không cho: nói vì sao (ngắn, rê chuột xem đủ) — không ẩn im lặng.
    return co.xoa_ly_do && !gon ? (
      <span
        title={co.xoa_ly_do}
        className={`line-clamp-1 text-label ${nenToi ? "text-white/60" : "text-ink-faint"}`}
      >
        {co.xoa_ly_do}
      </span>
    ) : null;
  }

  const dinhChinh = co.xoa_loai === "DINH_CHINH";
  const nhan = dinhChinh ? "Đính chính – gỡ tệp" : "Xoá";
  const lyDo = ghepLyDoXoa(ma, ghi);

  function dong() {
    setNeo(null);
    setMa(null);
    setGhi("");
    setLoi(null);
  }

  async function xoa() {
    if (!lyDo || dang) return;
    setDang(true);
    setLoi(null);
    const l = await goi(`/api/cskh/ket-qua/${encodeURIComponent(tepId)}/xoa`, {
      ly_do: lyDo,
    });
    setDang(false);
    if (l) {
      setLoi(l);
      return;
    }
    dong();
    onDaXoa();
  }

  const mo = (e: React.MouseEvent<HTMLElement>) => {
    e.stopPropagation();
    setNeo(e.currentTarget);
  };

  return (
    <>
      {nenToi ? (
        <button type="button" onClick={mo} className={NUT_NEN_TOI} aria-label={`${nhan}: ${ten ?? "tệp"}`}>
          <Trash2 className="size-3.5" aria-hidden />
          {nhan}
        </button>
      ) : (
        <Button
          variant="danger"
          size="sm"
          onClick={mo}
          aria-label={`${nhan}: ${ten ?? "tệp"}`}
          title={nhan}
        >
          <Trash2 className="size-3.5" aria-hidden />
          {gon ? null : nhan}
        </Button>
      )}
      {neo ? (
        <PopoverNeo
          neo={neo}
          onDong={dong}
          dau={
            <div className="min-w-0">
              <p className="text-body font-semibold text-ink">{nhan}</p>
              <p className="truncate text-meta text-ink-muted">{ten ?? "(không tên)"}</p>
            </div>
          }
          chan={
            <div className="flex flex-col gap-2">
              {loi ? (
                <p role="alert" className="text-label text-danger">
                  {loi}
                </p>
              ) : null}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-label text-ink-muted">Khôi phục được trong 30 ngày.</span>
                <span className="flex gap-2">
                  <Button variant="ghost" size="md" onClick={dong} disabled={dang}>
                    Thôi
                  </Button>
                  <Button variant="danger" size="md" disabled={!lyDo || dang} onClick={() => void xoa()}>
                    {dang ? "Đang xoá…" : nhan}
                  </Button>
                </span>
              </div>
            </div>
          }
        >
          {dinhChinh && co.xoa_ly_do ? (
            <p className="mb-3 rounded-control bg-warning-bg px-3 py-2 text-meta text-warning">
              {co.xoa_ly_do}
            </p>
          ) : null}
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-body font-semibold text-ink">Lý do</legend>
            <div className="flex flex-col gap-1.5">
              {LY_DO_XOA_TEP.map((x) => (
                <ChipChon key={x.ma} kieu="mot" ten={`xoa-${tepId}`} chon={ma === x.ma} onDoi={() => setMa(x.ma)}>
                  {x.chu}
                </ChipChon>
              ))}
            </div>
            <label className="mt-2 block text-meta text-ink-muted" htmlFor={`xoa-ghi-${tepId}`}>
              {ma === "KHAC" ? "Viết rõ lý do (bắt buộc)" : "Ghi thêm (tuỳ chọn)"}
            </label>
            <textarea
              id={`xoa-ghi-${tepId}`}
              rows={2}
              maxLength={400}
              value={ghi}
              onChange={(e) => setGhi(e.target.value)}
              placeholder="vd: ảnh của khách khác, đã tải lại đúng ảnh"
              className={O_CHU}
            />
          </fieldset>
        </PopoverNeo>
      ) : null}
    </>
  );
}

/** Nút "Hoàn tác" / "Khôi phục" một tệp đã xoá. */
export function NutKhoiPhucTep({
  tepId,
  nhan = "Hoàn tác",
  nenToi = false,
  onXong,
}: {
  tepId: string;
  nhan?: string;
  nenToi?: boolean;
  onXong: () => void;
}) {
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  async function bam() {
    setDang(true);
    setLoi(null);
    const l = await khoiPhucTep(tepId);
    setDang(false);
    if (l) setLoi(l);
    else onXong();
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      {nenToi ? (
        <button type="button" onClick={() => void bam()} disabled={dang} className={NUT_NEN_TOI}>
          <RotateCcw className="size-3.5" aria-hidden />
          {dang ? "Đang khôi phục…" : nhan}
        </button>
      ) : (
        <Button variant="soft" size="sm" onClick={() => void bam()} disabled={dang}>
          <RotateCcw className="size-3.5" aria-hidden />
          {dang ? "Đang khôi phục…" : nhan}
        </Button>
      )}
      {loi ? (
        <span role="alert" className="text-label text-danger">
          {loi}
        </span>
      ) : null}
    </span>
  );
}

/** Dải "Đã xoá gần đây" — chỉ tệp máy chủ cho khôi phục. */
export function DaXoaGanDay({ ds, onXong }: { ds: TepDaXoa[]; onXong: () => void }) {
  const hien = ds.filter((t) => t.khoi_phuc_duoc);
  if (hien.length === 0) return null;
  return (
    <div className="mt-2 space-y-1" aria-label="Tệp đã xoá gần đây">
      {hien.map((t) => (
        <div
          key={t.id}
          className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1 rounded-control bg-surface-muted px-3 py-1.5 text-meta"
        >
          <span className="min-w-0 flex-1 truncate text-ink-muted">
            <span className="line-through">{t.ten_hien_thi ?? "Tệp kết quả"}</span>
            {" · đã "}
            {t.da_xoa_loai === "DINH_CHINH" ? "gỡ (đính chính)" : "xoá"}
            {t.da_xoa_boi ? ` bởi ${t.da_xoa_boi}` : ""}
            {t.da_xoa_ly_do ? ` — ${t.da_xoa_ly_do}` : ""}
            {t.khoi_phuc_han ? ` · khôi phục được tới ${ngayGio(t.khoi_phuc_han)}` : ""}
          </span>
          <NutKhoiPhucTep tepId={t.id} onXong={onXong} />
        </div>
      ))}
    </div>
  );
}
