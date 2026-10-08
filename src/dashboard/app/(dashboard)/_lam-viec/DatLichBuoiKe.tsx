"use client";

// [Đặt lịch buổi kế] của liệu trình (08/10/2026) — mở ĐÚNG bộ đặt lịch sẵn có
// (`DatLichModal` → `AppointmentBooking`), khoá vào loại khám nhóm Điều trị của
// dịch vụ liệu trình (máy chủ trả `service_type_id`). Check-in lịch ấy → consumer
// sinh chỉ định → trigger gắn buổi kế (phủ nếu đã trả trước). Không viết form mới.

import DatLichModal from "../customers/DatLichModal";
import type { LieuTrinh } from "@/lib/lieu-trinh";

export interface MucChon {
  id: string;
  label: string;
}

export default function DatLichBuoiKe({
  lt,
  doctors,
  locations,
  defaultLocationId,
  onDong,
  onXong,
}: {
  lt: LieuTrinh;
  doctors: MucChon[];
  locations: MucChon[];
  defaultLocationId?: string;
  onDong: () => void;
  onXong: (appointmentId: string) => void;
}) {
  if (!lt.service_type_id) return null;
  return (
    <DatLichModal
      tenKhach={lt.ten_khach ?? "khách"}
      clinicPatientId={lt.khach_id}
      doctors={doctors}
      locations={locations}
      defaultLocationId={defaultLocationId}
      khoaDichVu={{ serviceId: lt.service_type_id, label: lt.service_name }}
      tieuDe="Đặt lịch buổi kế"
      moTa={
        <>
          Liệu trình <b>{lt.service_name}</b> — đã làm {lt.da_lam}/{lt.so_buoi} buổi
          {lt.con_tra_truoc > 0 ? `, còn ${lt.con_tra_truoc} buổi đã trả` : ""}. Khách đến
          check-in thì buổi tự gắn vào liệu trình; tiền (nếu chưa trả) thu ở quầy.
        </>
      }
      onDong={onDong}
      onXong={onXong}
    />
  );
}
