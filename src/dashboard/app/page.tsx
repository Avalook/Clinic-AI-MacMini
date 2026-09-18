import { redirect } from "next/navigation";
import { getVaiChinh } from "../lib/clinic-session";
import { roleLanding } from "../lib/roles";

// Root entry → trang đích THEO VAI TRÒ (bác sĩ → /tasks, còn lại → /home).
// Trước đây cứng /work-sessions khiến bác sĩ rơi vào trang ca trực (sai "bác sĩ
// chỉ 2 mục"). Middleware vẫn đẩy về /login nếu chưa đăng nhập.
// PHẢI động (18/09/2026): đích tuỳ vai người đang đăng nhập. Thiếu dòng này
// `next build` dựng sẵn trang lúc không có phiên → roleLanding(null) = /home,
// và từ đó MỌI người mở "/" đều về /home bất kể vai (đo trên prod 18/09).
export const dynamic = "force-dynamic";

export default async function Home() {
  const role = await getVaiChinh();
  redirect(roleLanding(role));
}
