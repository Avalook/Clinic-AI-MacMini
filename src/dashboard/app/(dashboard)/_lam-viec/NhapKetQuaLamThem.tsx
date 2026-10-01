"use client";

// "NHẬP KẾT QUẢ" CHO DỊCH VỤ LÀM THÊM TẠI QUẦY (Tuyền 01/10/2026).
//
// Khách được tick "+ Nước tiểu" ở Tiếp đón / Đo sinh hiệu thì người đứng bàn
// thử que tại chỗ — kết quả phải ghi được NGAY, không đợi lên phòng. Màn này chỉ
// ghép hai mảnh có sẵn, y như ở phòng dịch vụ:
//   · `PhieuKetQua` — phiếu (mẫu do MÁY CHỦ chọn: đã gắn, hoặc CHUNG nhập tự
//     do), nháp → Hoàn tất → Sửa lại, cùng sự kiện với mọi kết quả khác;
//   · `KhungTep`   — tải ảnh que thử / PDF (đường tải tệp kết quả sẵn có).
//
// HOÀN TẤT Ở QUẦY = DỊCH VỤ XONG (phương án A, Tuyền chốt): máy chủ đóng dịch vụ
// bằng lệnh Bắt đầu + Xong có sẵn; Sửa lại / [Hoàn tác] thì dịch vụ về chờ làm. Chưa
// đóng được (chưa thu tiền, chưa xếp phòng, thiếu quyền…) thì máy chủ trả câu nói
// rõ vì sao + cờ `co_the_dong` để hiện [Đóng dịch vụ]. Không luật nào ở đây.

import { useState } from "react";

import { nhanLoi, type ThanLoi } from "@/lib/loi-api";
import BaoLoiCanhNut from "@/components/ui/BaoLoiCanhNut";
import Button from "@/components/ui/Button";

import KhungTep from "./KhungTep";
import PhieuKetQua from "./PhieuKetQua";

export interface DichVuLamThem {
  trang_thai: string;
  /** Dịch vụ do QUẦY đóng (Hoàn tất kết quả ở quầy) — hoàn tác được. */
  xong_tai_quay: boolean;
  xong_boi: string | null;
  xong_luc: string | null;
  /** Vì sao CHƯA đóng được — máy chủ quyết, màn hiện nguyên câu. */
  chan: { vi_sao: string; cau: string } | null;
  co_the_dong: boolean;
}

export interface KetQuaLamThem {
  /** Người này nhập được kết quả không (quyền điền phiếu — máy chủ quyết). */
  nhap_duoc: boolean;
  trang_thai: "CHUA_CO" | "DANG_NHAP" | "CO_KET_QUA";
  so_tep: number;
  clinic_patient_id: string | null;
  mau: { ma: string; ten: string; nhom?: string | null; cua_dich_vu?: boolean }[];
  mau_chon_san: string | null;
  /** true = quản lý chưa gắn mẫu, đang dùng mặc định của máy. */
  mac_dinh: boolean;
  dich_vu?: DichVuLamThem;
}

/** Nhãn nút theo trạng thái kết quả. */
export function nhanNutKetQua(nhan: string, tt: KetQuaLamThem["trang_thai"]): string {
  if (tt === "CO_KET_QUA") return `Xem / sửa kết quả ${nhan}`;
  if (tt === "DANG_NHAP") return `Tiếp tục nhập kết quả ${nhan}`;
  return `Nhập kết quả ${nhan}`;
}

function gio(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function NhapKetQuaLamThem({
  tieuDe,
  serviceOrderId,
  ketQua,
  onDoi,
  onDong,
}: {
  tieuDe: string;
  serviceOrderId: string;
  ketQua: KetQuaLamThem;
  /** Phiếu hoàn tất / tệp vừa lên / dịch vụ đổi — màn cha đọc lại trạng thái. */
  onDoi: () => void;
  onDong: () => void;
}) {
  const dv = ketQua.dich_vu;
  const [cauVuaNhan, setCauVuaNhan] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  async function goi(thaoTac: "dong-dich-vu" | "hoan-tac-dich-vu") {
    setDang(true);
    setLoi(null);
    try {
      const r = await fetch("/api/lam-them", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thao_tac: thaoTac, du_lieu: { order_id: serviceOrderId } }),
      });
      const d = (await r.json().catch(() => null)) as
        | (ThanLoi & { da_dong?: boolean; cau?: string | null })
        | null;
      if (!r.ok) {
        setLoi(nhanLoi(d, "Không thực hiện được — thử lại."));
      } else if (thaoTac === "dong-dich-vu" && d && d.da_dong === false) {
        setLoi(d.cau ?? "Chưa đóng được dịch vụ.");
      } else {
        setCauVuaNhan(null);
      }
      onDoi();
    } catch {
      setLoi("Mất kết nối — chưa lưu, bấm lại.");
    } finally {
      setDang(false);
    }
  }

  // Máy chủ là nguồn: có `dv` thì chỉ tin `chan` của nó (câu vừa nhận lúc Hoàn tất
  // chỉ dùng khi chưa có gói đọc lại — tránh câu cũ "chưa xếp phòng" còn lại).
  const cauChua = dv ? (dv.chan?.cau ?? null) : cauVuaNhan;

  return (
    <section
      aria-label={`Kết quả ${tieuDe}`}
      className="w-full min-w-0 space-y-3 rounded-card border border-line bg-surface p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-body font-semibold text-ink">Kết quả {tieuDe}</h3>
        <Button type="button" size="sm" variant="ghost" onClick={onDong}>
          Đóng
        </Button>
      </div>
      <PhieuKetQua
        serviceOrderId={serviceOrderId}
        mau={ketQua.mau}
        mauMacDinh={ketQua.mau_chon_san}
        onHoanTat={(r) => {
          setCauVuaNhan(r.dichVuCau ?? null);
          onDoi();
        }}
      />
      {dv?.xong_tai_quay ? (
        <div className="space-y-2 rounded-control border border-success bg-success-bg px-3 py-2">
          <p className="text-body text-success">
            Dịch vụ đã XONG tại quầy
            {dv.xong_boi ? ` — ${dv.xong_boi}` : ""}
            {dv.xong_luc ? ` lúc ${gio(dv.xong_luc)}` : ""}.
          </p>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={dang}
            onClick={() => void goi("hoan-tac-dich-vu")}
          >
            Hoàn tác — mở lại dịch vụ
          </Button>
          <p className="text-meta text-ink-muted">
            Dịch vụ về lại hàng chờ phòng; kết quả đã nhập vẫn còn. Bấm [Sửa lại] ở phiếu
            cũng mở lại dịch vụ, [Xác nhận sửa] / [Huỷ sửa] đóng lại.
          </p>
        </div>
      ) : cauChua || dv?.co_the_dong ? (
        <div className="space-y-2 rounded-control border border-warning bg-warning-bg px-3 py-2">
          <p className="text-body text-warning">
            {cauChua ?? "Kết quả đã hoàn tất nhưng dịch vụ CHƯA đóng."}
          </p>
          {dv?.co_the_dong ? (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              disabled={dang}
              onClick={() => void goi("dong-dich-vu")}
            >
              Đóng dịch vụ
            </Button>
          ) : null}
        </div>
      ) : null}
      <BaoLoiCanhNut>{loi}</BaoLoiCanhNut>
      {ketQua.clinic_patient_id ? (
        <KhungTep
          clinicPatientId={ketQua.clinic_patient_id}
          serviceOrderId={serviceOrderId}
          tieuDe="Ảnh · PDF kết quả"
          onDaTaiLen={onDoi}
        />
      ) : null}
    </section>
  );
}
