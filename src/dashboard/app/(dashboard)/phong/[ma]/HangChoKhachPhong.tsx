"use client";

// HÀNG CHỜ PHÒNG DỊCH VỤ THEO KHÁCH (Tuyền chốt 07/10/2026 — staging: một khách
// ba chỉ định hiện ba dòng, tiêu đề "1 đang chờ" mà danh sách "ĐANG CHỜ (3)").
//
// MỖI KHÁCH ĐÚNG MỘT DÒNG GỌN ở mọi nhóm (đang làm · đang chờ · đang làm việc
// khác · đã xong): số · tên · "N chỉ định" · nhãn. Không liệt kê từng chỉ định ở
// đây (bố cục Tuyền chốt 07/10 tối) — bấm dòng thì khung bên phải liệt kê chỉ
// định của khách với nút Nhận / Bắt đầu / Xong và mở phiếu.
//
// Khách vào nhóm "cao nhất" của mình: có chỉ định đang làm → Đang làm; không thì
// có chỉ định chờ → Đang chờ… (chỉ chia nhóm để đọc, thứ tự do MÁY CHỦ xếp — như
// `HangChoCot`).

import { Star } from "lucide-react";

import SoLuot from "@/components/ui/SoLuot";
import { nhanBuoiCuaLuot, type ChipLieuTrinh } from "@/lib/lieu-trinh";

import { cauDangOPhong, gioVn, soPhutTu, type ChiDinhPhong, type DongHangCho } from "../../_lam-viec/api";

type Nhom = "lam" | "cho" | "khac" | "xong" | "ve";

const NHOM: { ma: Nhom; ten: string }[] = [
  { ma: "lam", ten: "Đang làm" },
  { ma: "cho", ten: "Đang chờ" },
  // Khách đang ở bước khác (đang khám bác sĩ, đang làm ở phòng khác).
  { ma: "khac", ten: "Đang làm việc khác" },
  { ma: "xong", ten: "Đã xong" },
  // Chỉ ở NGÀY CŨ (29/09/2026): khách về khi việc này chưa xong.
  { ma: "ve", ten: "Khách đã về (chưa xong)" },
];

interface OKhach {
  visitId: string;
  dong: DongHangCho[];
  nhom: Nhom;
}

/** Nhóm của một khách = trạng thái "cao nhất" trong các dòng của khách. */
function nhomCua(dong: DongHangCho[]): Nhom {
  if (dong.some((d) => d.trang_thai === "serving")) return "lam";
  if (dong.some((d) => d.trang_thai === "waiting" || d.trang_thai === "called")) return "cho";
  if (dong.some((d) => d.trang_thai === "blocked")) return "khac";
  if (dong.some((d) => d.trang_thai === "left")) return "ve";
  return "xong";
}

/** Gom dòng hàng chờ thành ô khách, giữ thứ tự máy chủ (lần xuất hiện đầu). */
export function gomTheoKhach(dong: DongHangCho[]): OKhach[] {
  const theo = new Map<string, DongHangCho[]>();
  for (const d of dong) theo.set(d.visit_id, [...(theo.get(d.visit_id) ?? []), d]);
  return [...theo.entries()].map(([visitId, ds]) => ({ visitId, dong: ds, nhom: nhomCua(ds) }));
}

/** Dòng "chính" của khách: đang làm, rồi đang chờ, rồi dòng đầu. */
export function dongChinh(dong: DongHangCho[]): DongHangCho | null {
  return (
    dong.find((d) => d.trang_thai === "serving") ??
    dong.find((d) => d.trang_thai === "waiting" || d.trang_thai === "called") ??
    dong[0] ??
    null
  );
}

export default function HangChoKhachPhong({
  dong,
  chiDinhKhach,
  chon,
  onChon,
  trong,
  lieuTrinh = null,
}: {
  dong: DongHangCho[];
  /** visit_id → chỉ định phòng làm được + trạng thái (dây Nhận tại phòng bật). */
  chiDinhKhach: Record<string, ChiDinhPhong[]>;
  /** visit_id đang mở ở khung phải. */
  chon: string | null;
  onChon: (visitId: string) => void;
  trong: string;
  /** Chip liệu trình của cả lô (08/10/2026) — chỉ thêm chữ vào dòng phụ. */
  lieuTrinh?: ChipLieuTrinh | null;
}) {
  if (dong.length === 0) {
    return <p className="rounded-card border border-line bg-surface p-4 text-sm text-ink-muted">{trong}</p>;
  }
  const oKhach = gomTheoKhach(dong);
  return (
    <div className="space-y-3">
      {NHOM.map((n) => {
        const ds = oKhach.filter((k) => k.nhom === n.ma);
        if (ds.length === 0) return null;
        return (
          <section key={n.ma}>
            <h3 className="mb-1 px-1 text-label font-semibold uppercase tracking-wide text-ink-muted">
              {n.ten} ({ds.length})
            </h3>
            <ul className="space-y-1">
              {ds.map((k) => {
                const dau = k.dong[0];
                const chinh = dongChinh(k.dong) ?? dau;
                const dangChon = k.visitId === chon;
                const cd = chiDinhKhach[k.visitId] ?? [];
                const soChiDinh = cd.length > 0 ? cd.length : new Set(k.dong.map((d) => d.ref_id)).size;
                const sang = k.dong.find((d) => d.da_sang_phong)?.da_sang_phong ?? null;
                const oDau = k.dong.find((d) => d.dang_o_phong)?.dang_o_phong ?? null;
                const nhan = sang
                  ? `đã sang ${sang.phong ?? "phòng khác"} lúc ${gioVn(sang.luc)}`
                  : oDau
                    ? cauDangOPhong(oDau).toLowerCase()
                    : cd.some((c) => c.nhan_duoc)
                      ? "còn chỉ định chưa nhận"
                      : null;
                const phut =
                  chinh.trang_thai === "serving"
                    ? soPhutTu(chinh.bat_dau_luc)
                    : chinh.trang_thai === "done"
                      ? gioVn(chinh.xong_luc)
                      : soPhutTu(chinh.vao_hang_luc);
                return (
                  <li key={k.visitId}>
                    <button
                      type="button"
                      onClick={() => onChon(k.visitId)}
                      aria-pressed={dangChon}
                      className={`flex w-full items-center gap-2 rounded-control border px-2 py-1.5 text-left ${
                        dangChon ? "border-brand-500 bg-brand-50" : "border-line bg-surface"
                      } ${k.nhom === "xong" ? "opacity-70" : ""}`}
                    >
                      <span
                        title="Số check-in"
                        className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-sunken text-meta font-bold text-ink"
                      >
                        {dau.so_tiep_don ?? dau.so_thu_tu}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-1">
                          {dau.uu_tien ? (
                            <Star className="size-3.5 shrink-0 fill-warning text-warning" aria-label="Ưu tiên" />
                          ) : null}
                          <span className={`truncate text-sm font-semibold ${dau.uu_tien ? "text-danger" : "text-ink"}`}>
                            {dau.ten}
                          </span>
                          <SoLuot booking={dau.so_booking} className="shrink-0" />
                        </span>
                        <span className={`block truncate text-label ${sang ? "text-danger" : "text-ink-muted"}`}>
                          {[`${soChiDinh} chỉ định`, nhanBuoiCuaLuot(lieuTrinh, k.visitId, k.dong), nhan]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      </span>
                      <span className="shrink-0 text-right text-label text-ink-muted">{phut}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
