// Toàn cảnh điều phối — một trong năm màn điều phối của Trưởng ca (Notion §4).
//
// Mỗi màn là một URL riêng thay vì một tab trong cùng trang: mở thẳng được, gửi
// link cho nhau được, nút Quay lại của trình duyệt chạy đúng, và thanh bên chỉ
// còn MỘT — trước đây cột tab trong trang là một thanh bên thứ hai nằm ngay
// cạnh thanh bên thật.

import Link from "next/link";

import { requireNavAccess } from "../../../lib/clinic-session";
import { loadLive } from "./load";
import OverviewClient from "./OverviewClient";
import "./dispatch.css";
import LiveBoardSync from "../LiveBoardSync";

export const dynamic = "force-dynamic";

export default async function Page() {
  await requireNavAccess("/truong-ca");
  const live = await loadLive();
  return (
    <>
      <LiveBoardSync />
    {/* aria-label: vùng chính của màn, để trình đọc màn hình gọi tên được nó.
        Mất trong lần tái cấu trúc "năm màn điều phối lên thanh bên" và bài kiểm
        ranh giới đã bắt đúng — thêm lại vào CODE, không nới bài kiểm. */}
    <main
      aria-label="Tổng quan điều phối"
      className="page-in min-w-0 space-y-4 p-4 lg:p-5"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">Toàn cảnh điều phối</h1>
          <p className="mt-1 text-sm text-ink-muted">Ai đang ở đâu, chờ bao lâu, và đi đâu tiếp.</p>
        </div>
        {/* NỬA CÒN LẠI CỦA TOÀN CẢNH. Màn này chỉ thấy người ĐÃ vào phòng
            khám; ai đã hẹn mà chưa tới, ai gọi không được, ai chờ kết quả thì
            nằm ở Quản lý khách hàng. Trưởng ca vốn đã có quyền mở màn ấy, nhưng
            nó nằm lẫn giữa mười ba mục trong thanh bên nên không ai tìm ra
            (Tuyền 16/09: "cần bê quản lý khách hàng của cskh sang"). */}
        <Link
          href="/customers"
          className="inline-flex min-h-10 items-center rounded-control border border-line bg-surface px-3 text-sm font-medium text-ink"
        >
          Quản lý khách hàng →
        </Link>
      </header>
      <OverviewClient initial={live} />
    </main>
    </>
  );
}
