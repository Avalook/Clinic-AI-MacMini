// Nhà thuốc — contract tiền–thuốc CP4 (19/09/2026).
//
// Đọc QUA MÁY CHỦ (`GET /api/v1/pharmacy/ban-thuoc`), không đọc thẳng
// Supabase như bản trước: màn này phải biết giai đoạn tiền thuốc của lượt (đã
// khám xong chưa, lần thu nào đang chờ / đã thu, lô nào đang giữ / đã bán) và
// những nút nào được phép — đó là luật nghiệp vụ, sống ở FastAPI.

import { fetchFromBackend } from "../../../lib/backend-proxy";
import { requireNavAccess } from "../../../lib/clinic-session";
import PharmacyBoard from "./PharmacyBoard";
import type { ManNhaThuoc } from "./ban-thuoc";

export const dynamic = "force-dynamic";

export default async function PharmacyPage() {
  await requireNavAccess("/pharmacy");
  const man = await fetchFromBackend<ManNhaThuoc>("/api/v1/pharmacy/ban-thuoc");
  if (!man) {
    return (
      <div className="p-6 text-body text-danger">
        Không đọc được đơn thuốc từ máy chủ. Tải lại trang; nếu vẫn lỗi, báo quản lý.
      </div>
    );
  }
  return <PharmacyBoard man={man} />;
}
