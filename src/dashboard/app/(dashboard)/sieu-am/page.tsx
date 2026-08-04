// Bộ phận Siêu âm — bốn màn (bản mẫu: src/truong-ca-prototype/.../ultrasound).
//
// Nạp sẵn hai tab đầu ở server để màn hiện ngay; hai tab sau nạp khi mở, vì
// người làm siêu âm ở tab hàng chờ gần như cả buổi.

import { requireNavAccess } from "../../../lib/clinic-session";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import LiveBoardSync from "../LiveBoardSync";
import UltrasoundBoard from "./UltrasoundBoard";
import type { SonoQueueItem, SonoRoom } from "./types";
import "../truong-ca/dispatch.css";

export const dynamic = "force-dynamic";

export default async function SieuAmPage() {
  await requireNavAccess("/sieu-am");

  const [queue, rooms] = await Promise.all([
    fetchFromBackend<{ items: SonoQueueItem[] }>("/api/v1/ultrasound/queue"),
    fetchFromBackend<{ items: SonoRoom[] }>("/api/v1/ultrasound/rooms"),
  ]);

  return (
    <>
      <LiveBoardSync />
      <UltrasoundBoard
        initialQueue={queue?.items ?? []}
        initialRooms={rooms?.items ?? []}
        // `null` = backend không trả lời. Truyền xuống để màn NÓI RA, thay vì
        // hiện một hàng chờ trống trông y hệt "không còn ai cần siêu âm".
        ok={queue !== null && rooms !== null}
      />
    </>
  );
}
