/**
 * BẢNG HÀNH TRÌNH CHUNG (nhóm 3, Tuyền chốt 24/09/2026).
 *
 * Mỗi khách hôm nay: ĐANG Ở ĐÂU · ĐÃ XONG GÌ · CÒN CHỜ GÌ — một bảng cho mọi
 * người. "Đã xong gì" dựng từ sổ sự kiện (dòng thời gian); máy chủ tính hết,
 * màn chỉ vẽ.
 */

import { requireNavAccess } from "@/lib/clinic-session";

import LiveBoardSync from "../LiveBoardSync";
import BangHanhTrinh from "./BangHanhTrinh";

export const metadata = { title: "Hành trình khách hôm nay · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function HanhTrinhPage() {
  await requireNavAccess("/hanh-trinh");
  return (
    <>
      <LiveBoardSync />
      <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
        <BangHanhTrinh />
      </main>
    </>
  );
}
