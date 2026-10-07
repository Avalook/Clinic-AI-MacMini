"use client";

// HÀNG CHỜ PHÒNG DỊCH VỤ THEO KHÁCH (Tuyền chốt 07/10/2026 — staging: một khách
// ba chỉ định hiện ba dòng, tiêu đề "1 đang chờ" mà danh sách "ĐANG CHỜ (3)").
//
// MỖI KHÁCH MỘT Ô ở mọi nhóm (đang làm · đang chờ · đang làm việc khác · đã xong).
// Khách vào nhóm "cao nhất" của mình: có chỉ định đang làm → Đang làm; không thì
// có chỉ định chờ → Đang chờ… (chỉ chia nhóm để đọc, thứ tự do MÁY CHỦ xếp — như
// `HangChoCot`). Trong ô: các chỉ định phòng làm được kèm trạng thái máy chủ trả
// (`chi_dinh_khach`) — bấm chỉ định có ở phòng để mở nó bên phải (Bắt đầu / Xong
// / hoàn tác vẫn theo từng chỉ định). "Nhận thêm" cho chỉ định còn lại.

import { Star } from "lucide-react";
import { useState } from "react";

import Button from "@/components/ui/Button";
import SoLuot from "@/components/ui/SoLuot";
import { type ThongBao } from "@/components/ui/ThongBaoHoanTac";

import {
  cauChiDinhPhong,
  gioVn,
  soPhutTu,
  type ChiDinhPhong,
  type DongHangCho,
} from "../../_lam-viec/api";
import NhanChiDinh from "./NhanChiDinh";

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

export default function HangChoKhachPhong({
  dong,
  chiDinhKhach,
  chon,
  onChon,
  nhanTaiPhong,
  bacSiLamId,
  onDaNhan,
  onBao,
  trong,
}: {
  dong: DongHangCho[];
  /** visit_id → chỉ định phòng làm được + trạng thái (dây Nhận tại phòng bật). */
  chiDinhKhach: Record<string, ChiDinhPhong[]>;
  chon: string | null;
  onChon: (id: string) => void;
  /** Mã phòng khi được "Nhận thêm" (dây bật, hôm nay) — null = không có nút. */
  nhanTaiPhong: string | null;
  bacSiLamId?: string;
  onDaNhan: () => void;
  onBao: (tb: ThongBao) => void;
  trong: string;
}) {
  const [moNhan, setMoNhan] = useState<string | null>(null);
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
                const chinh =
                  k.dong.find((d) => d.trang_thai === "serving") ??
                  k.dong.find((d) => d.trang_thai === "waiting" || d.trang_thai === "called") ??
                  dau;
                const dangChon = k.dong.some((d) => d.id === chon);
                const theoRef = new Map(k.dong.map((d) => [d.ref_id, d]));
                const cd = chiDinhKhach[k.visitId] ?? [];
                // Không có danh sách máy chủ (dây tắt / ngày cũ): vẽ theo dòng.
                const hang: { id: string; ten: string; nhan: string; dong?: DongHangCho; chuyen?: boolean }[] =
                  cd.length > 0
                    ? cd.map((c) => ({
                        id: c.id,
                        ten: c.ten ?? "—",
                        nhan: cauChiDinhPhong(c),
                        dong: theoRef.get(c.id),
                        chuyen: c.chuyen,
                      }))
                    : k.dong.map((d) => ({
                        id: d.ref_id,
                        ten: d.viec ?? "—",
                        nhan: d.trang_thai === "done" ? "xong" : d.trang_thai === "serving" ? "đang làm" : "chờ",
                        dong: d,
                      }));
                const nhanThem = nhanTaiPhong ? cd.filter((c) => c.nhan_duoc) : [];
                const phut =
                  chinh.trang_thai === "serving"
                    ? soPhutTu(chinh.bat_dau_luc)
                    : chinh.trang_thai === "done"
                      ? gioVn(chinh.xong_luc)
                      : soPhutTu(chinh.vao_hang_luc);
                return (
                  <li
                    key={k.visitId}
                    className={`rounded-control border px-2.5 py-2 ${
                      dangChon ? "border-brand-500 bg-brand-50" : "border-line bg-surface"
                    } ${k.nhom === "xong" ? "opacity-70" : ""}`}
                  >
                    <button
                      type="button"
                      onClick={() => onChon(chinh.id)}
                      aria-pressed={dangChon}
                      className="flex w-full items-start gap-2 text-left"
                    >
                      <span
                        title="Số check-in"
                        className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-sunken text-sm font-bold text-ink"
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
                        <span className="block text-label text-ink-muted">{hang.length} chỉ định</span>
                      </span>
                      <span className="shrink-0 text-right text-label text-ink-muted">{phut}</span>
                    </button>
                    <ul className="mt-1 space-y-0.5 pl-10">
                      {hang.map((h) => (
                        <li key={h.id}>
                          {h.dong ? (
                            <button
                              type="button"
                              onClick={() => onChon(h.dong!.id)}
                              aria-pressed={h.dong.id === chon}
                              className={`w-full rounded-control px-1 text-left text-label hover:bg-surface-muted ${
                                h.dong.id === chon ? "font-semibold text-brand-700" : "text-ink"
                              }`}
                            >
                              {h.ten}
                              {h.chuyen ? " ★" : ""} <span className="text-ink-muted">· {h.nhan}</span>
                              {h.dong.bac_si_lam ? <span className="text-brand-700"> · {h.dong.bac_si_lam}</span> : null}
                            </button>
                          ) : (
                            <span className="block px-1 text-label text-ink-muted">
                              {h.ten}
                              {h.chuyen ? " ★" : ""} · {h.nhan}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                    {nhanThem.length > 0 && nhanTaiPhong ? (
                      moNhan === k.visitId ? (
                        <div className="mt-1 pl-10">
                          <NhanChiDinh
                            roomId={nhanTaiPhong}
                            visitId={k.visitId}
                            khach={dau.ten}
                            chiDinh={cd}
                            bacSiLamId={bacSiLamId}
                            nhanNut="Nhận thêm"
                            onThoi={() => setMoNhan(null)}
                            onBao={onBao}
                            onXong={() => {
                              setMoNhan(null);
                              onDaNhan();
                            }}
                          />
                        </div>
                      ) : (
                        <div className="mt-1 pl-10">
                          <Button type="button" size="sm" variant="soft" onClick={() => setMoNhan(k.visitId)}>
                            Nhận thêm ({nhanThem.length})
                          </Button>
                        </div>
                      )
                    ) : null}
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
