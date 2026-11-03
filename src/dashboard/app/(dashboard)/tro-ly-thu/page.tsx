// THỬ TRỢ LÝ AI TRẢ LỜI KHÁCH (30/10/2026) — docs/KE-HOACH-TRO-LY-AI-KHACH.md.
//
// Màn nội bộ: nhân viên đóng vai khách nhắn tin, AI soạn NHÁP, người Duyệt /
// Sửa / Chuyển. Không gửi gì ra ngoài. Chưa vào lego/thanh bên — vào bằng
// đường dẫn; quyền `ops.view` và cờ `TRO_LY_BAT` do máy chủ quyết.
import { requireNavAccess } from "../../../lib/clinic-session";
import TroLyThu from "./TroLyThu";

export const dynamic = "force-dynamic";

export default async function TroLyThuPage() {
  await requireNavAccess("/tro-ly-thu");
  return <TroLyThu />;
}
