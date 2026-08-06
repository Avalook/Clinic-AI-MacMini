// Check-out lượt khám — màn của Lễ tân (Notion §2).
//
// Dùng lại bảng màu của khu điều phối (`dispatch.css`, phạm vi `.dispatch-scope`)
// vì hai màn này đứng cạnh nhau trong luồng làm việc và cùng một người đọc.

import { requireNavAccess } from "../../../../lib/clinic-session";
import { fetchFromBackend } from "../../../../lib/backend-proxy";
import CheckoutBoard, { type CheckoutRow } from "./CheckoutBoard";
import "../../truong-ca/dispatch.css";
import LiveBoardSync from "../../LiveBoardSync";

export const dynamic = "force-dynamic";

export default async function ReceptionCheckoutPage() {
  await requireNavAccess("/reception/checkout");

  const data = await fetchFromBackend<{ ok: boolean; items: CheckoutRow[] }>(
    "/api/v1/reception/checkout",
  );

  return (
    <>
      <LiveBoardSync />
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      {/* Tiêu đề ở THANH TRÊN CÙNG (GlobalHeader) như mọi trang khác. */}

      {/* `data === null` = backend không trả lời, KHÁC HẲN "không còn ai cần
          đóng". Truyền cờ xuống để màn hình nói ra thay vì vẽ danh sách rỗng. */}
      <CheckoutBoard initial={data?.items ?? []} ok={data !== null} />
    </main>
    </>
  );
}
