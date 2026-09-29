// QUYỀN CỦA NGƯỜI ĐANG ĐĂNG NHẬP — để màn hình quyết HIỆN hay ẨN (24/09/2026).
//
// Đọc `GET /phan-quyen/toi` (danh sách capability còn hiệu lực). Ẩn/hiện KHÔNG
// phải bảo mật: backend vẫn tự kiểm quyền ở mọi lời gọi. Nhớ trong MỘT lượt dựng
// trang (`cache`) để nhiều chỗ hỏi mà chỉ tốn một lời gọi.

import { cache } from "react";
import { fetchFromBackend } from "./backend-proxy";

/** Có một trong các quyền này = làm việc được với NỘI DUNG Y KHOA (bệnh án,
 *  phiếu khám, kết quả). Khớp `QUYEN_Y_KHOA` ở `permissions/y_khoa.py`. */
export const QUYEN_Y_KHOA = [
  "clinical.intake.perform",
  "clinical.consult.perform",
  "clinical.record.write",
  "clinical.consult.finalize",
  "result.form.fill",
  "result.review.approve",
] as const;

export const quyenCuaToi = cache(async (): Promise<ReadonlySet<string>> => {
  const d = await fetchFromBackend<{ quyen: string[] }>("/api/v1/phan-quyen/toi");
  return new Set(d?.quyen ?? []);
});

/** Được mở nội dung y khoa không — thay `canReadClinical(role)` (theo vai). */
export async function docDuocYKhoa(): Promise<boolean> {
  const q = await quyenCuaToi();
  return QUYEN_Y_KHOA.some((x) => q.has(x));
}

/** Quầy in phiếu khám cho khách (27/09/2026). Khớp `QUYEN_IN_PHIEU` ở
 *  `permissions/y_khoa.py`: tiếp đón, thu tiền DV, thu tiền thuốc, giao thuốc. */
export const QUYEN_IN_PHIEU = [
  "reception.checkin.perform",
  "payment.service.collect",
  "payment.medicine.collect",
  "pharmacy.dispense",
  // CSKH in PDF trả khách theo từng ngày khám (28/09/2026) — chỉ đọc.
  "crm.manage",
] as const;

export async function inDuocPhieu(): Promise<boolean> {
  const q = await quyenCuaToi();
  return [...QUYEN_Y_KHOA, ...QUYEN_IN_PHIEU].some((x) => q.has(x));
}

/** Ghi sổ chăm sóc (gọi khách) — khớp `_INTAKE_GUARD` của
 *  `POST /api/v1/cskh/tuong-tac` (routers/cskh.py). Chỉ để ẨN/HIỆN mục
 *  "Gọi / ghi chăm sóc" ở menu ⋯ lịch hẹn; máy chủ vẫn tự kiểm. */
export const QUYEN_GHI_CHAM_SOC = [
  "crm.manage",
  "reception.checkin.perform",
  "dispatch.manage",
] as const;

/** Có ít nhất một quyền trong `can` (null = máy chủ chưa trả lời → không). */
export function coMotQuyen(quyen: readonly string[] | null, can: readonly string[]): boolean {
  return quyen !== null && can.some((q) => quyen.includes(q));
}
