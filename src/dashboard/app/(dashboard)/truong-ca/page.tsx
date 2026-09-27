// ĐIỀU PHỐI CA = HÀNG ĐỢI THEO TRẠM (Tuyền 27/09/2026 tối: "hàng đợi theo trạm
// → đổi tên thành điều phối ca; nút điều phối ca cũ xoá đi vì bản chất chức
// năng vào hàng đợi theo trạm rồi"). Mỗi phòng một thẻ, khách chờ quá ngưỡng
// tô đỏ, bấm khách → popup đổi phòng làm được việc ấy; mỗi phòng một TV.
// `/truong-ca/hang-doi` chỉ còn chuyển hướng về đây.
import { requireNavAccess } from "../../../lib/clinic-session";
import { loadLive } from "./load";
import QueuesClient from "./QueuesClient";
import "./dispatch.css";
import LiveBoardSync from "../LiveBoardSync";

export const dynamic = "force-dynamic";

export default async function Page() {
  await requireNavAccess("/truong-ca");
  const live = await loadLive();
  return (
    <>
      <LiveBoardSync />
      <main aria-label="Tổng quan điều phối" className="page-in min-w-0 space-y-4 p-4 lg:p-5">
        <header>
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">Điều phối ca</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Từng phòng, ai đang chờ và chờ bao lâu — bấm khách chờ quá lâu để chuyển sang phòng làm được việc ấy.
          </p>
        </header>
        <QueuesClient initial={live} />
      </main>
    </>
  );
}
