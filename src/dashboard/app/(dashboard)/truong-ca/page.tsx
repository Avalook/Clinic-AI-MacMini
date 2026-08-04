// Toàn cảnh điều phối — một trong năm màn điều phối của Trưởng ca (Notion §4).
//
// Mỗi màn là một URL riêng thay vì một tab trong cùng trang: mở thẳng được, gửi
// link cho nhau được, nút Quay lại của trình duyệt chạy đúng, và thanh bên chỉ
// còn MỘT — trước đây cột tab trong trang là một thanh bên thứ hai nằm ngay
// cạnh thanh bên thật.

import { requireNavAccess } from "../../../lib/clinic-session";
import { loadLive, loadRoutes } from "./load";
import OverviewClient from "./OverviewClient";
import "./dispatch.css";
import LiveBoardSync from "../LiveBoardSync";

export const dynamic = "force-dynamic";

export default async function Page() {
  await requireNavAccess("/truong-ca");
  const [live, routes] = await Promise.all([loadLive(), loadRoutes()]);
  return (
    <>
      <LiveBoardSync />
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">Toàn cảnh điều phối</h1>
        <p className="mt-1 text-sm text-ink-muted">Ai đang ở đâu, chờ bao lâu, và đi đâu tiếp.</p>
      </header>
      <OverviewClient initial={live} routes={routes} />
    </main>
    </>
  );
}
