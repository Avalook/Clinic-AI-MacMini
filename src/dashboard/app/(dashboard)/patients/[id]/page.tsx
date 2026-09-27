import { redirect } from "next/navigation";

// GỘP (Tuyền 27/09/2026): "trang đang nhảy hiện tại là thừa, bỏ đi" — hồ sơ và
// lịch sử khám của một khách xem ở màn Danh sách bệnh nhân (hồ sơ hành chính +
// các lượt khám hiện ngay tại chỗ). Giữ đường này làm CHUYỂN HƯỚNG để link cũ /
// dấu trang vẫn mở đúng khách.
export default async function PatientRedirect({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/patient-list?chon=${encodeURIComponent(id)}`);
}
