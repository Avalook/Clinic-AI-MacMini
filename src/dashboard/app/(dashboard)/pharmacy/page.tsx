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

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function PharmacyPage({
  searchParams,
}: {
  /** `luot` — chọn sẵn một lượt (V8: nút "Khách mua thuốc" ở Kho thuốc). */
  searchParams: Promise<{ luot?: string }>;
}) {
  await requireNavAccess("/pharmacy");
  const { luot } = await searchParams;
  const man = await fetchFromBackend<ManNhaThuoc>("/api/v1/pharmacy/ban-thuoc");
  if (!man) {
    return (
      <div className="p-6 text-body text-danger">
        Không đọc được đơn thuốc từ máy chủ. Tải lại trang; nếu vẫn lỗi, báo quản lý.
      </div>
    );
  }
  return <PharmacyBoard man={man} chonDau={luot && UUID_RE.test(luot) ? luot : null} />;
}
