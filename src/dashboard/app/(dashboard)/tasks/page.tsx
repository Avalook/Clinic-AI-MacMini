// "CÔNG VIỆC CỦA TÔI" ĐÃ GỘP (Tuyền chốt 18/09/2026 — docs/SITEMAP.md mục C).
//
// Màn này từng rẽ năm nhánh theo vai, và mỗi nhánh là BẢN THỨ HAI của một màn
// đang sống: thu ngân có quầy thu riêng, bác sĩ có bàn khám, điều dưỡng có màn
// đo sinh hiệu. Hai bản của cùng một việc là chỗ sửa một bản, sót bản kia —
// 17/09 nút QR được gỡ ở đây trong khi quầy thu thật là /thu-ngan/*.
//
// Đường dẫn cũ vẫn mở được — đưa mỗi vai về đúng màn chuẩn của mình.
//
// Thư mục tasks/ vẫn giữ các component DÙNG CHUNG (ClinicalRecordForm,
// ServiceFormEngine…) — chỉ còn trang này là chuyển hướng.

import { redirect } from "next/navigation";
import { getVaiChinh } from "../../../lib/clinic-session";
import {
  isCashierRole,
  isDoctorRole,
  isNurseRole,
  isUltrasoundDoctorRole,
} from "../../../lib/roles";

// PHẢI động: đích đến tuỳ vai người đang đăng nhập. Không có dòng này thì
// `next build` dựng sẵn trang lúc KHÔNG có phiên → vai null → mọi người bị
// đông cứng về /home (bản build 18/09 báo ○ Static trước khi thêm).
export const dynamic = "force-dynamic";

export default async function TrangCu() {
  const role = await getVaiChinh();
  if (isCashierRole(role)) redirect("/thu-ngan/dich-vu");
  if (isUltrasoundDoctorRole(role)) redirect("/phong/KN-SA-T1");
  if (isDoctorRole(role)) redirect("/ban-kham");
  if (isNurseRole(role)) redirect("/do-sinh-hieu");
  if (role === "RECEPTION") redirect("/reception/queue");
  // Quản lý: phần "xác nhận lịch + nhật ký CSKH" cũ nay ở Quản lý khách hàng.
  if (role === "MANAGEMENT" || role === "CSKH") redirect("/customers");
  redirect("/home");
}
