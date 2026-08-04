// Check-out lượt khám — màn của Lễ tân (Notion §2).
//
// Dùng lại bảng màu của khu điều phối (`dispatch.css`, phạm vi `.dispatch-scope`)
// vì hai màn này đứng cạnh nhau trong luồng làm việc và cùng một người đọc.

import { requireNavAccess } from "../../../../lib/clinic-session";
import { fetchFromBackend } from "../../../../lib/backend-proxy";
import CheckoutBoard, { type CheckoutRow } from "./CheckoutBoard";
import "../../truong-ca/dispatch.css";

export const dynamic = "force-dynamic";

export default async function ReceptionCheckoutPage() {
  await requireNavAccess("/reception/checkout");

  const data = await fetchFromBackend<{ ok: boolean; items: CheckoutRow[] }>(
    "/api/v1/reception/checkout",
  );

  return (
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">
          Check-out lượt khám
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Đối soát điều kiện rồi đóng lượt. Còn việc chưa xong vẫn đóng được,
          nhưng phải ghi lý do.
        </p>
      </header>

      {/* `data === null` = backend không trả lời, KHÁC HẲN "không còn ai cần
          đóng". Truyền cờ xuống để màn hình nói ra thay vì vẽ danh sách rỗng. */}
      <CheckoutBoard initial={data?.items ?? []} ok={data !== null} />
    </main>
  );
}
