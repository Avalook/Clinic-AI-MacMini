"use client";

// KHỐI VIỆC ĐỐI TÁC — MỘT bộ phần dùng chung cho bàn `/doi-tac` và Phòng đối
// tác ở `/phong/<phòng đối tác>` (Tuyền 16/10/2026: "chạy CHUNG trạng thái và
// lệnh, bấm ở đâu cũng đồng bộ").
//
//   ChipDoiTac      — chữ trạng thái máy chủ viết (`trang_thai_chu`): chỉ hai
//                     chữ riêng "Đã nhận mẫu · chờ kết quả" / "Có kết quả";
//                     trước khi nhận mẫu là chữ chung "Chờ làm".
//   KetQuaDoiTac    — phiếu kết quả theo mẫu của loại chỉ định + [Trả kết quả]
//                     + hoàn tác (Trả kết quả / Nhận mẫu).
//   ThuHoDoiTac     — ô TUỲ CHỌN ghi số tiền đã thu hộ (sổ của khối Đối tác,
//                     không vào tiền phòng khám); để trống là không ghi gì.
//
// Không luật nào ở đây: nút nào hiện là cờ máy chủ (`nhan_mau_duoc`,
// `tra_ket_qua_duoc`…), mọi lệnh đi `/api/doi-tac/*` → `DoiTacService`.

import { useState } from "react";
import { CircleCheck } from "lucide-react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import NutHoanTac, { type DuLieuHoanTac, type KetQuaHoanTac } from "@/components/ui/NutHoanTac";
import PhieuKetQua, { type MauKetQua } from "./PhieuKetQua";

export type TrangThaiDoiTac = "CHO_LAY_MAU" | "DA_LAY_MAU" | "DA_NHAN_MAU" | "DA_GUI_KET_QUA";

/** DA_NHAN_MAU và DA_GUI_KET_QUA đều là XONG (máy chủ: VIEC_DOI_TAC_XONG). */
export const XONG_DOI_TAC: ReadonlySet<TrangThaiDoiTac> = new Set<TrangThaiDoiTac>([
  "DA_NHAN_MAU",
  "DA_GUI_KET_QUA",
]);

/** Chữ dự phòng khi máy chủ cũ chưa trả `trang_thai_chu` — cùng bộ chữ. */
export const CHU_DOI_TAC: Record<TrangThaiDoiTac, string> = {
  CHO_LAY_MAU: "Chờ làm",
  DA_LAY_MAU: "Chờ làm",
  DA_NHAN_MAU: "Đã nhận mẫu · chờ kết quả",
  DA_GUI_KET_QUA: "Có kết quả",
};

export interface DaThuDoiTac {
  id: string;
  so_tien: number;
  hinh_thuc: "CASH" | "TRANSFER";
  ghi_chu: string | null;
  luc: string | null;
  boi?: string | null;
}

/** Phần chung của một việc đối tác máy chủ trả (`DoiTacService._dung_viec`). */
export interface ViecDoiTacChung {
  chi_dinh_id: string;
  ten_dich_vu: string;
  trang_thai: TrangThaiDoiTac;
  trang_thai_chu?: string;
  cho_tai_lieu_luc: string | null;
  ket_qua_luc: string | null;
  doi_tac_thu?: boolean;
  gia_tham_khao?: number | null;
  da_thu?: DaThuDoiTac | null;
  mau_ket_qua?: MauKetQua[];
  mau_goi_y?: string | null;
  phieu?: { id: string; form_id: string; trang_thai: string }[];
  nhan_mau_duoc?: boolean;
  co_noi_dung_ket_qua?: boolean;
  tra_ket_qua_duoc?: boolean;
}

const TEN_HINH_THUC: Record<DaThuDoiTac["hinh_thuc"], string> = {
  CASH: "Tiền mặt",
  TRANSFER: "Chuyển khoản",
};

export function tienVnd(n: number): string {
  return `${n.toLocaleString("vi-VN")}đ`;
}

export function chuDoiTac(v: Pick<ViecDoiTacChung, "trang_thai" | "trang_thai_chu">): string {
  return v.trang_thai_chu ?? CHU_DOI_TAC[v.trang_thai];
}

export function ChipDoiTac({ viec }: { viec: Pick<ViecDoiTacChung, "trang_thai" | "trang_thai_chu"> }) {
  const xong = XONG_DOI_TAC.has(viec.trang_thai);
  return (
    <Chip tone={viec.trang_thai === "DA_GUI_KET_QUA" ? "success" : xong ? "info" : "neutral"}>
      {xong ? <CircleCheck className="size-3.5" aria-hidden="true" /> : null}
      {chuDoiTac(viec)}
    </Chip>
  );
}

/** Gửi một lệnh của bàn đối tác — trả câu lỗi máy chủ (null = được). */
export async function guiLenhDoiTac(
  duong: string,
  than: Record<string, unknown>,
): Promise<{ loi: string | null; chiTiet?: Record<string, unknown> }> {
  try {
    const r = await fetch(duong, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    if (r.ok) return { loi: null };
    const d = (await r.json().catch(() => null)) as {
      error?: string;
      message?: string;
      detail?: { message?: string; chi_tiet?: Record<string, unknown> };
      chi_tiet?: Record<string, unknown>;
    } | null;
    return {
      loi: d?.message ?? d?.detail?.message ?? d?.error ?? "Không ghi được.",
      chiTiet: d?.chi_tiet ?? d?.detail?.chi_tiet,
    };
  } catch {
    return { loi: "Mất kết nối — CHƯA ghi được." };
  }
}

/** Lệnh hoàn tác của bàn đối tác cho `NutHoanTac` / `ThongBaoHoanTac`. */
export function hoanTacDoiTac(
  lenh: "huy-nhan-mau" | "huy-tra-ket-qua",
  chiDinhId: string,
  them: Record<string, unknown> = {},
): (duLieu: DuLieuHoanTac) => Promise<KetQuaHoanTac> {
  return async (duLieu) => {
    const kq = await guiLenhDoiTac("/api/doi-tac/lenh", {
      lenh,
      chi_dinh_id: chiDinhId,
      ...them,
      ...duLieu,
    });
    return kq.loi === null
      ? { ok: true }
      : { ok: false, loi: kq.loi, ...(kq.chiTiet ? { chiTiet: kq.chiTiet } : {}) };
  };
}

/** Phiếu kết quả theo mẫu + [Trả kết quả] + hoàn tác — sau khi nhận mẫu là
 *  chỗ chính; trước đó vẫn mở được (đối tác bận chưa bấm Nhận mẫu). */
export function KetQuaDoiTac({
  viec,
  duongPhieu,
  onDoi,
  moLaiPhong = false,
}: {
  viec: ViecDoiTacChung;
  /** `/api/doi-tac/phieu` (tài khoản đối tác) hoặc `/api/phieu` (nhân sự). */
  duongPhieu: string;
  /** Vừa ghi / hoàn tác — màn tải lại. */
  onDoi: () => void;
  /** Phòng đối tác: hoàn tác nhận mẫu mở lại cả lần làm của phòng. */
  moLaiPhong?: boolean;
}) {
  const [moPhieu, setMoPhieu] = useState(false);
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const mau = viec.mau_ket_qua ?? [];
  const coKetQua = viec.trang_thai === "DA_GUI_KET_QUA";
  const daNhanMau = viec.trang_thai === "DA_NHAN_MAU";
  const phieuDau = viec.phieu?.[0] ?? null;

  const traKetQua = async () => {
    setDangGui(true);
    setLoi(null);
    const kq = await guiLenhDoiTac("/api/doi-tac/lenh", {
      lenh: "tra-ket-qua",
      chi_dinh_id: viec.chi_dinh_id,
    });
    setDangGui(false);
    if (kq.loi) setLoi(kq.loi);
    else onDoi();
  };

  return (
    <div className="space-y-2">
      {mau.length > 0 ? (
        <Button size="sm" variant="ghost" onClick={() => setMoPhieu((v) => !v)}>
          {moPhieu ? "Đóng phiếu kết quả" : phieuDau ? "Mở phiếu kết quả" : "Điền phiếu kết quả"}
        </Button>
      ) : null}
      {moPhieu ? (
        <PhieuKetQua
          serviceOrderId={viec.chi_dinh_id}
          mau={mau}
          mauMacDinh={phieuDau?.form_id?.replace(/^KQ_/, "") ?? viec.mau_goi_y ?? null}
          duong={duongPhieu}
          onHoanTat={() => onDoi()}
        />
      ) : null}
      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center justify-end gap-2">
        {coKetQua ? (
          <NutHoanTac
            goi={hoanTacDoiTac("huy-tra-ket-qua", viec.chi_dinh_id)}
            onXong={onDoi}
            nhan="Hoàn tác trả kết quả"
            tieuDe="Hoàn tác “Trả kết quả”?"
            moTa="Việc về “Đã nhận mẫu · chờ kết quả” — tệp và phiếu giữ nguyên"
          />
        ) : null}
        {daNhanMau ? (
          <NutHoanTac
            goi={hoanTacDoiTac("huy-nhan-mau", viec.chi_dinh_id, moLaiPhong ? { mo_lai_phong: true } : {})}
            onXong={onDoi}
            nhan="Hoàn tác nhận mẫu"
            tieuDe="Hoàn tác “Đã nhận mẫu”?"
            moTa="Việc về “Chờ làm”"
          />
        ) : null}
        {!coKetQua ? (
          <Button
            size="lg"
            variant="primary"
            disabled={dangGui || !viec.tra_ket_qua_duoc}
            title={
              viec.tra_ket_qua_duoc
                ? undefined
                : "Tải tệp kết quả lên hoặc Hoàn tất phiếu kết quả trước"
            }
            onClick={() => void traKetQua()}
          >
            {dangGui ? "Đang ghi…" : "Trả kết quả"}
          </Button>
        ) : null}
      </div>
      {!coKetQua && !viec.tra_ket_qua_duoc ? (
        <p className="text-right text-label text-ink-muted">
          Tải tệp kết quả lên hoặc Hoàn tất phiếu kết quả rồi bấm Trả kết quả.
        </p>
      ) : null}
    </div>
  );
}

/** THU HỘ ĐỐI TÁC (16/10/2026): ô TUỲ CHỌN ghi số tiền đã thu + hình thức. Để
 *  trống là không ghi gì — thu hộ không chặn việc nào khác. Ghi vào sổ thu hộ
 *  của khối Đối tác (không vào tiền phòng khám); huỷ ghi nhận bắt lý do. */
export function ThuHoDoiTac({ viec, onDoi }: { viec: ViecDoiTacChung; onDoi: () => void }) {
  const [soTien, setSoTien] = useState(
    viec.gia_tham_khao != null && viec.gia_tham_khao > 0 ? String(viec.gia_tham_khao) : "",
  );
  const [hinhThuc, setHinhThuc] = useState<DaThuDoiTac["hinh_thuc"]>("CASH");
  const [lyDo, setLyDo] = useState("");
  const [moHuy, setMoHuy] = useState(false);
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const da = viec.da_thu ?? null;

  const gui = async (duong: string, than: Record<string, unknown>) => {
    setDangGui(true);
    setLoi(null);
    const kq = await guiLenhDoiTac(duong, { chi_dinh_id: viec.chi_dinh_id, ...than });
    setDangGui(false);
    if (kq.loi) {
      setLoi(kq.loi);
      return false;
    }
    onDoi();
    return true;
  };

  if (da) {
    return (
      <div className="space-y-2 rounded-control bg-surface-muted px-3 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-meta text-ink">
            Đã thu hộ {tienVnd(da.so_tien)} · {TEN_HINH_THUC[da.hinh_thuc]}
            {da.boi ? ` · ${da.boi}` : ""}
          </p>
          {!moHuy ? (
            <Button variant="ghost" size="sm" disabled={dangGui} onClick={() => setMoHuy(true)}>
              Huỷ ghi nhận
            </Button>
          ) : null}
        </div>
        {moHuy ? (
          <div className="flex flex-wrap items-end gap-2">
            <label className="min-w-0 flex-1">
              <span className="text-label font-semibold text-ink-muted">Lý do huỷ ghi nhận</span>
              <input
                value={lyDo}
                onChange={(e) => setLyDo(e.target.value)}
                maxLength={2000}
                placeholder="VD: ghi nhầm số tiền"
                className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
              />
            </label>
            <Button variant="ghost" size="md" disabled={dangGui} onClick={() => setMoHuy(false)}>
              Thôi
            </Button>
            <Button
              variant="danger"
              size="md"
              disabled={dangGui || lyDo.trim().length < 3}
              onClick={() =>
                void gui("/api/doi-tac/huy-da-thu", { ly_do: lyDo }).then((ok) => {
                  if (ok) {
                    setMoHuy(false);
                    setLyDo("");
                  }
                })
              }
            >
              {dangGui ? "Đang ghi…" : "Huỷ ghi nhận"}
            </Button>
          </div>
        ) : null}
        {loi ? <p role="alert" className="text-meta text-danger">{loi}</p> : null}
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-control bg-surface-muted px-3 py-2">
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
        <label className="block">
          <span className="text-label font-semibold text-ink-muted">Số tiền đã thu hộ (tuỳ chọn)</span>
          <input
            value={soTien}
            onChange={(e) => setSoTien(e.target.value)}
            inputMode="numeric"
            placeholder="Để trống nếu không thu"
            className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body tabular-nums text-ink"
          />
        </label>
        <label className="block">
          <span className="text-label font-semibold text-ink-muted">Hình thức</span>
          <select
            value={hinhThuc}
            onChange={(e) => setHinhThuc(e.target.value as DaThuDoiTac["hinh_thuc"])}
            className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
          >
            <option value="CASH">Tiền mặt</option>
            <option value="TRANSFER">Chuyển khoản</option>
          </select>
        </label>
        <Button
          variant="soft"
          size="md"
          disabled={dangGui || !soTien.trim()}
          onClick={() => void gui("/api/doi-tac/da-thu-tien", { so_tien: soTien, hinh_thuc: hinhThuc })}
        >
          {dangGui ? "Đang ghi…" : "Ghi thu hộ"}
        </Button>
      </div>
      {loi ? <p role="alert" className="text-meta text-danger">{loi}</p> : null}
    </div>
  );
}
