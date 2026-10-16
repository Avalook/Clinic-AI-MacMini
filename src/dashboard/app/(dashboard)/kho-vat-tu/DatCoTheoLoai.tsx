"use client";

// Khối "Đặt cho cả loại" ở đầu tab DANH MỤC của Kho vật tư. Quản lý chọn Loại + Cờ + Bật/Tắt,
// màn HIỆN TRƯỚC "Sẽ đổi N vật tư" (máy chủ đếm — `ap_dung: false`), bấm [Áp dụng] thì xác
// nhận ngay tại chỗ rồi ghi (`ap_dung: true`). Sau khi áp có [Hoàn tác] = đặt giá trị ngược
// cho đúng những vật tư vừa đổi (`ids` máy chủ trả).
//
// Mọi luật ở máy chủ (`vat_tu_danh_muc_service.dat_co_hang_loat`): chỉ vật tư đang bán,
// chỉ đúng cờ được chọn, quyền = quyền sửa thuộc tính từng món. Màn chỉ vẽ và gửi lệnh.
// Cờ nằm trên chính cột của từng vật tư nên Thu ngân dịch vụ / Chờ duyệt tự ăn theo.

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import type { DongVatTu } from "../cashier/VatTuBangGia";

const LOAI = [
  ["VPP", "Văn phòng phẩm"],
  ["VTYT", "Vật tư y tế"],
  ["CHUA_PHAN_LOAI", "Chưa phân loại"],
] as const;
const CO = [
  ["kinh_doanh", "Được kinh doanh"],
  ["can_ql_duyet", "Cần QL duyệt bán"],
  ["can_duyet_nhap", "Cần duyệt nhập"],
] as const;
const O = "h-10 w-full rounded-control border border-line bg-surface px-2 text-body text-ink lg:h-8";

interface KetQua {
  ap_dung: boolean;
  so_doi: number;
  so_trong_loai: number;
  so_ngung_ban_bo_qua: number;
  ids: string[];
}

interface DaDoi {
  so: number;
  loai: string;
  co: string;
  bat: boolean;
  ids: string[];
}

const tenLoai = (ma: string) => LOAI.find(([k]) => k === ma)?.[1] ?? ma;
const tenCo = (ma: string) => CO.find(([k]) => k === ma)?.[1] ?? ma;

async function goi(
  duLieu: Record<string, unknown>,
): Promise<{ ok: true; kq: KetQua } | { ok: false; loi: string }> {
  try {
    const r = await fetch("/api/service-price/vat-tu-hang-loat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(duLieu),
    });
    if (r.ok) return { ok: true, kq: (await r.json()) as KetQua };
    const d = (await r.json().catch(() => null)) as {
      message?: string;
      detail?: unknown;
      error?: string;
    } | null;
    return {
      ok: false,
      loi: d?.message ?? (typeof d?.detail === "string" ? d.detail : null) ?? d?.error ?? "Máy chủ từ chối.",
    };
  } catch {
    return { ok: false, loi: "Mất kết nối — CHƯA đổi gì." };
  }
}

/** `ds` đổi tham chiếu mỗi lần danh mục tải lại (sau `router.refresh()`) nên xem trước tự đếm lại. */
export default function DatCoTheoLoai({ ds }: { ds: DongVatTu[] }) {
  const router = useRouter();
  const [loai, setLoai] = useState<string>("VPP");
  const [co, setCo] = useState<string>("kinh_doanh");
  const [bat, setBat] = useState(true);
  // Kết quả đếm gắn với khoá lựa chọn + bản danh mục nó đếm trên; khác khoá = đang đếm lại
  // (không setState đồng bộ trong effect).
  const [xemRa, setXemRa] = useState<{ khoa: string; ds: DongVatTu[]; kq: KetQua | null; loi: string | null } | null>(
    null,
  );
  const [hoiKhoa, setHoiKhoa] = useState<string | null>(null);
  const [ban, setBan] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [daDoi, setDaDoi] = useState<DaDoi | null>(null);

  const khoa = `${loai}|${co}|${bat}|${daDoi?.ids.length ?? "-"}`;
  const moi = xemRa !== null && xemRa.khoa === khoa && xemRa.ds === ds;
  const xem = moi ? xemRa.kq : null;
  const loiXem = moi ? xemRa.loi : null;
  const hoi = hoiKhoa === khoa && xem !== null;

  useEffect(() => {
    let huy = false;
    void goi({ loai, co, bat, ap_dung: false }).then((r) => {
      if (huy) return;
      setXemRa({ khoa, ds, kq: r.ok ? r.kq : null, loi: r.ok ? null : r.loi });
    });
    return () => {
      huy = true;
    };
  }, [loai, co, bat, ds, khoa]);

  async function ap(duLieu: Record<string, unknown>, hoanTac: boolean): Promise<void> {
    setBan(true);
    setLoi(null);
    const r = await goi({ ...duLieu, ap_dung: true });
    setBan(false);
    setHoiKhoa(null);
    if (!r.ok) {
      setLoi(r.loi);
      return;
    }
    // Vừa áp → cho phép Hoàn tác; vừa hoàn tác → xoá dải (không hoàn tác lòng vòng).
    setDaDoi(hoanTac ? null : { so: r.kq.so_doi, loai, co, bat, ids: r.kq.ids });
    router.refresh();
  }

  const so = xem?.so_doi ?? 0;

  return (
    <section
      aria-label="Đặt cho cả loại"
      className="rounded-card border border-hairline bg-surface px-4 py-3 shadow-card"
    >
      <h2 className="text-emph font-semibold text-ink">Đặt cho cả loại</h2>
      <p className="mb-3 text-meta text-ink-muted">
        Đặt một cờ cho mọi vật tư đang bán của một loại, thay vì tick từng món. Hàng đã tạm ngưng giữ nguyên.
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="space-y-1 text-body">
          <span>Loại vật tư</span>
          <select
            aria-label="Loại vật tư cần đặt cờ"
            className={O}
            value={loai}
            disabled={ban}
            onChange={(e) => {
              setLoai(e.target.value);
              setDaDoi(null);
            }}
          >
            {LOAI.map(([ma, ten]) => (
              <option key={ma} value={ma}>
                {ten}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-body">
          <span>Cờ</span>
          <select
            aria-label="Cờ cần đặt"
            className={O}
            value={co}
            disabled={ban}
            onChange={(e) => {
              setCo(e.target.value);
              setDaDoi(null);
            }}
          >
            {CO.map(([ma, ten]) => (
              <option key={ma} value={ma}>
                {ten}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-body">
          <span>Đặt thành</span>
          <select
            aria-label="Bật hay tắt cờ"
            className={O}
            value={bat ? "bat" : "tat"}
            disabled={ban}
            onChange={(e) => {
              setBat(e.target.value === "bat");
              setDaDoi(null);
            }}
          >
            <option value="bat">Bật</option>
            <option value="tat">Tắt</option>
          </select>
        </label>
      </div>
      <p role="status" aria-live="polite" className="mt-3 text-body text-ink">
        {loiXem
          ? null
          : xem === null
            ? "Đang đếm…"
            : so === 0
              ? `Không có vật tư nào cần đổi (${xem.so_trong_loai} vật tư thuộc loại này).`
              : `Sẽ đổi ${so} vật tư.`}
        {xem && xem.so_ngung_ban_bo_qua > 0 ? (
          <span className="text-meta text-ink-muted">
            {" "}
            Bỏ qua {xem.so_ngung_ban_bo_qua} vật tư đang tạm ngưng.
          </span>
        ) : null}
      </p>
      {loiXem ? (
        <p role="alert" className="text-body text-danger">
          {loiXem}
        </p>
      ) : null}
      <div className="mt-2 flex flex-col gap-2">
        {hoi ? (
          <XacNhanTaiCho
            cau={`${bat ? "Bật" : "Tắt"} “${tenCo(co)}” cho ${so} vật tư ${tenLoai(loai)}?`}
            nhanDongY={`Đặt cho ${so} vật tư`}
            dangGui={ban}
            onDongY={() => void ap({ loai, co, bat }, false)}
            onThoi={() => setHoiKhoa(null)}
          />
        ) : (
          <div>
            <Button
              type="button"
              variant="primary"
              disabled={ban || xem === null || so === 0}
              onClick={() => setHoiKhoa(khoa)}
            >
              Áp dụng
            </Button>
          </div>
        )}
        {loi ? (
          <p role="alert" className="text-body text-danger">
            {loi}
          </p>
        ) : null}
        {daDoi ? (
          <div className="flex flex-wrap items-center gap-2" role="status">
            <p className="text-body text-success">
              Đã {daDoi.bat ? "bật" : "tắt"} “{tenCo(daDoi.co)}” cho {daDoi.so} vật tư {tenLoai(daDoi.loai)}.
            </p>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={ban}
              onClick={() =>
                void ap({ loai: daDoi.loai, co: daDoi.co, bat: !daDoi.bat, ids: daDoi.ids }, true)
              }
            >
              Hoàn tác
            </Button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
