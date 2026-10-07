"use client";

// KHUNG PHẢI — CÁC CHỈ ĐỊNH CỦA KHÁCH ĐANG CHỌN (Tuyền chốt bố cục 07/10/2026 tối).
//
// Cột trái mỗi khách một dòng; bấm dòng thì đây liệt kê các chỉ định PHÒNG NÀY
// LÀM ĐƯỢC của khách (máy chủ trả, kèm trạng thái nhìn từ phòng), MỖI DÒNG MỘT
// NÚT theo trạng thái máy chủ nói:
//   sắp đến / đang chờ ở phòng khác (nhận được) → [Nhận]
//   chờ ở đây → [Bắt đầu]   ·   đang làm → [Xong]
// + [Nhận cả N] khi ≥2 chỉ định nhận được. Bấm tên chỉ định (đã ở phòng) thì
// phiếu kết quả của nó mở ngay bên dưới. Thứ tự làm tuỳ người dùng.
//
// [Bắt đầu] / [Xong] không tự gọi lệnh ở đây: chọn chỉ định rồi nhờ khung phiếu
// bên dưới (`KhachTrongPhong`) làm đúng lệnh nó vẫn làm (đọc revision, hỏi lại
// khi máy chủ trả 409) — một chỗ xử lý, không hai.

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { type ThongBao } from "@/components/ui/ThongBaoHoanTac";

import { cauChiDinhPhong, type ChiDinhPhong, type DongHangCho } from "../../_lam-viec/api";
import ChonBacSiLam, { coChonBacSi, type LuaChonBacSi } from "../../_lam-viec/ChonBacSiLam";
import NhanChiDinh from "./NhanChiDinh";

export type HanhDong = "bat-dau" | "xong";

interface Dong {
  id: string;
  ten: string;
  nhan: string;
  chuyen: boolean;
  chuaChot: boolean;
  nhanDuoc: boolean;
  /** Hành động theo trạng thái máy chủ: chờ ở đây → bắt đầu, đang làm → xong. */
  hanh: HanhDong | null;
  dong: DongHangCho | null;
}

export default function KhungChiDinhKhach({
  roomId,
  visitId,
  khach,
  maKhach,
  dangO,
  chiDinh,
  dong,
  chon,
  choNhan,
  bacSi,
  bacSiLamId,
  onChonBacSi,
  onChonDong,
  onHanhDong,
  onDaNhan,
  onBao,
}: {
  roomId: string;
  visitId: string;
  khach: string | null;
  maKhach: string | null;
  /** Nhãn nơi khách đang ở (máy chủ viết) — chỉ khách chưa ở phòng này. */
  dangO: string | null;
  chiDinh: ChiDinhPhong[];
  /** Dòng hàng chờ của khách ở phòng này. */
  dong: DongHangCho[];
  /** Dòng hàng chờ đang mở phiếu bên dưới. */
  chon: string | null;
  /** Được bấm Nhận (dây bật, hôm nay). */
  choNhan: boolean;
  bacSi: LuaChonBacSi[];
  bacSiLamId: string;
  onChonBacSi: (id: string) => void;
  onChonDong: (dongId: string) => void;
  onHanhDong: (dongId: string, hanh: HanhDong) => void;
  onDaNhan: () => void;
  onBao: (tb: ThongBao) => void;
}) {
  const theoRef = new Map(dong.map((d) => [d.ref_id, d]));
  // Không có danh sách máy chủ (ngày cũ): vẽ theo dòng hàng chờ.
  const hang: Dong[] =
    chiDinh.length > 0
      ? chiDinh.map((c) => {
          const d = theoRef.get(c.id) ?? null;
          return {
            id: c.id,
            ten: c.ten ?? "—",
            nhan: cauChiDinhPhong(c),
            chuyen: c.chuyen,
            chuaChot: c.chua_chot,
            nhanDuoc: c.nhan_duoc,
            hanh: d && c.trang_thai === "cho" ? "bat-dau" : d && c.trang_thai === "lam" ? "xong" : null,
            dong: d,
          };
        })
      : dong.map((d) => ({
          id: d.ref_id,
          ten: d.viec ?? "—",
          nhan: d.trang_thai === "done" ? "xong" : d.trang_thai === "serving" ? "đang làm" : "chờ ở đây",
          chuyen: false,
          chuaChot: false,
          nhanDuoc: false,
          hanh: d.trang_thai === "serving" ? "xong" : d.trang_thai === "waiting" || d.trang_thai === "called" ? "bat-dau" : null,
          dong: d,
        }));
  const nhanDuoc = choNhan ? hang.filter((h) => h.nhanDuoc) : [];

  return (
    <section aria-label={`Chỉ định của ${khach ?? "khách"}`} className="space-y-2 rounded-card bg-surface p-3 shadow-card">
      <header className="flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 text-body text-ink">
          <b className="font-semibold">{khach ?? "—"}</b>
          {maKhach ? <span className="text-ink-muted"> · {maKhach}</span> : null}
          {dangO ? <span className="text-meta text-ink-muted"> · {dangO}</span> : null}
        </p>
        {nhanDuoc.length > 0 && coChonBacSi(bacSi) ? (
          <ChonBacSiLam co="nho" ds={bacSi} value={bacSiLamId} onChon={onChonBacSi} />
        ) : null}
        {nhanDuoc.length >= 2 ? (
          <span className="flex flex-wrap items-center gap-2">
            <NhanChiDinh
              roomId={roomId}
              visitId={visitId}
              khach={khach}
              ids={nhanDuoc.map((h) => h.id)}
              nhan={`Nhận cả ${nhanDuoc.length}`}
              bacSiLamId={bacSiLamId}
              onXong={onDaNhan}
              onBao={onBao}
            />
          </span>
        ) : null}
      </header>
      {hang.length === 0 ? (
        <p className="text-meta text-ink-muted">Khách chưa có chỉ định nào phòng này làm được.</p>
      ) : (
        <ul className="divide-y divide-line">
          {hang.map((h) => {
            const dangChon = h.dong !== null && h.dong.id === chon;
            return (
              <li key={h.id} className="flex flex-wrap items-center gap-x-2 gap-y-1 py-1.5">
                {h.dong ? (
                  <button
                    type="button"
                    onClick={() => onChonDong(h.dong!.id)}
                    aria-pressed={dangChon}
                    className={`min-w-0 flex-1 rounded-control px-1 text-left text-body hover:bg-surface-muted ${
                      dangChon ? "font-semibold text-brand-700" : "text-ink"
                    }`}
                  >
                    {h.ten}
                    {h.chuyen ? " ★" : ""} <span className="text-meta font-normal text-ink-muted">· {h.nhan}</span>
                    {h.dong.bac_si_lam ? <span className="text-meta text-brand-700"> · {h.dong.bac_si_lam}</span> : null}
                  </button>
                ) : (
                  <span className="min-w-0 flex-1 px-1 text-body text-ink">
                    {h.ten}
                    {h.chuyen ? " ★" : ""} <span className="text-meta text-ink-muted">· {h.nhan}</span>
                    {h.chuaChot ? <span className="text-meta text-ink-muted"> · chưa chốt</span> : null}
                  </span>
                )}
                {choNhan && h.nhanDuoc ? (
                  <NhanChiDinh
                    roomId={roomId}
                    visitId={visitId}
                    khach={khach}
                    ids={[h.id]}
                    variant={nhanDuoc.length >= 2 ? "soft" : "primary"}
                    bacSiLamId={bacSiLamId}
                    onXong={onDaNhan}
                    onBao={onBao}
                  />
                ) : h.hanh && h.dong ? (
                  <Button
                    type="button"
                    size="sm"
                    variant={h.hanh === "bat-dau" ? "primary" : "secondary"}
                    onClick={() => onHanhDong(h.dong!.id, h.hanh!)}
                  >
                    {h.hanh === "bat-dau" ? "Bắt đầu" : "Xong"}
                  </Button>
                ) : null}
                {h.dong?.da_sang_phong ? (
                  <Chip tone="danger" className="basis-full">
                    Khách đã sang {h.dong.da_sang_phong.phong ?? "phòng khác"} — bấm Xong hoặc Gián đoạn
                  </Chip>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
