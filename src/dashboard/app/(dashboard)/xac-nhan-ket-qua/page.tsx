/**
 * Màn "Xác nhận kết quả đối tác" ĐÃ BỎ (Tuyền 12/11/2026): tờ kết quả đối tác máy nhận
 * Hợp lệ ngay; nhân viên theo dõi + gán / gán lại ở Việc của đối tác (tab Kết quả,
 * mục "Thư email đã gán"). Link cũ (đánh dấu, chuông cũ) chuyển về đó.
 */

import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

export default function XacNhanKetQuaPage() {
  redirect("/ban-xet-nghiem");
}
