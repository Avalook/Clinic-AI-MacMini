// BẢNG ĐIỀU PHỐI CỦA TRƯỞNG CA (Notion §4).
//
// Trang này TRƯỚC ĐÂY là một bảng CHỈ ĐỌC liệt kê các lượt khám tạo hôm nay —
// hữu ích, nhưng không phải việc của Trưởng ca. Yêu cầu khách hàng mô tả một
// mặt bàn điều phối: thấy ai đang ở đâu, chờ bao lâu, chuyển phòng, chọn tuyến.
//
// Bảng mới bao trọn phần cũ (mỗi bệnh nhân vẫn có giờ vào, bác sĩ, dịch vụ,
// trạng thái) và thêm phần thiếu: vị trí, thời gian chờ, bước kế tiếp, và các
// nút thật sự làm được gì đó. Lượt khám chưa được xếp trạm không biến mất — nó
// hiện thành cảnh báo "đã check-in nhưng chưa được xếp trạm nào", đúng chỗ cần
// nhìn thấy.

import { requireNavAccess } from "../../../lib/clinic-session";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import DispatchBoard, { type DispatchData } from "./DispatchBoard";
import type {
  DispatchAlert,
  DispatchHistoryRow,
  DispatchPatient,
  DispatchRoom,
  RouteTemplate,
} from "./types";
import "./dispatch.css";

export const dynamic = "force-dynamic";

export default async function TruongCaPage() {
  await requireNavAccess("/truong-ca");

  // Bốn lượt gọi SONG SONG — chúng không phụ thuộc nhau. Nối tiếp thì mỗi lần
  // mở trang tốn thêm ba vòng mạng tới Supabase (đo được ~80ms mỗi vòng).
  const [ov, al, rt, hi] = await Promise.all([
    fetchFromBackend<{ patients: DispatchPatient[]; rooms: DispatchRoom[] }>(
      "/api/v1/dispatch/overview",
    ),
    fetchFromBackend<{ items: DispatchAlert[] }>("/api/v1/dispatch/alerts"),
    fetchFromBackend<{ items: RouteTemplate[] }>("/api/v1/dispatch/routes"),
    fetchFromBackend<{ items: DispatchHistoryRow[] }>(
      "/api/v1/dispatch/history?limit=200",
    ),
  ]);

  const initial: DispatchData = {
    patients: ov?.patients ?? [],
    rooms: ov?.rooms ?? [],
    alerts: al?.items ?? [],
    routes: rt?.items ?? [],
    history: hi?.items ?? [],
    // `ov === null` = backend không trả lời. Màn hình phải NÓI RA điều đó —
    // một bảng trống trông y hệt "hôm nay chưa có ai đến", và Trưởng ca sẽ tin.
    ok: ov !== null,
  };

  return (
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">
          Điều phối ca
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Ai đang ở đâu, chờ bao lâu, và đi đâu tiếp — cập nhật liên tục.
        </p>
      </header>

      <DispatchBoard initial={initial} />
    </main>
  );
}
