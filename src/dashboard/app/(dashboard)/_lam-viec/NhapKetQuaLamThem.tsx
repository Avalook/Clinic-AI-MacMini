"use client";

// "NHẬP KẾT QUẢ" CHO DỊCH VỤ LÀM THÊM TẠI QUẦY (Tuyền 01/10/2026).
//
// Khách được tick "+ Nước tiểu" ở Tiếp đón / Đo sinh hiệu thì người đứng bàn
// thử que tại chỗ — kết quả phải ghi được NGAY, không đợi lên phòng. Màn này chỉ
// ghép hai mảnh có sẵn, y như ở phòng dịch vụ:
//   · `PhieuKetQua` — phiếu (mẫu do MÁY CHỦ chọn: đã gắn, hoặc CHUNG nhập tự
//     do), nháp → Hoàn tất → Sửa lại, cùng sự kiện với mọi kết quả khác;
//   · `KhungTep`   — tải ảnh que thử / PDF (đường tải tệp kết quả sẵn có).
// Không luật nào ở đây: mẫu nào, ai nhập được, đã có kết quả chưa đều do máy
// chủ trả (`ket_qua` trong `GET /api/lam-them`).

import Button from "@/components/ui/Button";

import KhungTep from "./KhungTep";
import PhieuKetQua from "./PhieuKetQua";

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
}

/** Nhãn nút theo trạng thái kết quả. */
export function nhanNutKetQua(nhan: string, tt: KetQuaLamThem["trang_thai"]): string {
  if (tt === "CO_KET_QUA") return `Xem / sửa kết quả ${nhan}`;
  if (tt === "DANG_NHAP") return `Tiếp tục nhập kết quả ${nhan}`;
  return `Nhập kết quả ${nhan}`;
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
  /** Phiếu hoàn tất / tệp vừa lên — màn cha đọc lại trạng thái. */
  onDoi: () => void;
  onDong: () => void;
}) {
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
        onHoanTat={() => onDoi()}
      />
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
