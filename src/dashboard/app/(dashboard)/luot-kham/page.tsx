// Luồng khám lát 1: check-in → sinh hiệu → bác sĩ khám → duyệt chỉ định →
// điều phối → làm dịch vụ → quay lại bác sĩ → kết thúc.
//
// Chạy SONG SONG với các màn cũ (bàn khám, hàng đợi, điều phối). Không màn cũ
// nào đọc bảng của luồng này và ngược lại — xem migration 20260911000001.

import { requireNavAccess } from "../../../lib/clinic-session";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import LuotKhamBoard, { type Bang } from "./LuotKhamBoard";

export const dynamic = "force-dynamic";

export default async function LuotKhamPage() {
  await requireNavAccess("/luot-kham");
  const bang = await fetchFromBackend<Bang>("/api/v1/luot-kham/bang");
  return (
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      {/* `null` = backend không trả lời, KHÁC "hôm nay chưa có ai". */}
      <LuotKhamBoard initial={bang} />
    </main>
  );
}
