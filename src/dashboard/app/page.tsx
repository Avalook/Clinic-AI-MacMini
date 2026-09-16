import { redirect } from "next/navigation";
import { getVaiChinh } from "../lib/clinic-session";
import { roleLanding } from "../lib/roles";

// Root entry → trang đích THEO VAI TRÒ (bác sĩ → /tasks, còn lại → /home).
// Trước đây cứng /work-sessions khiến bác sĩ rơi vào trang ca trực (sai "bác sĩ
// chỉ 2 mục"). Middleware vẫn đẩy về /login nếu chưa đăng nhập.
export default async function Home() {
  const role = await getVaiChinh();
  redirect(roleLanding(role));
}
