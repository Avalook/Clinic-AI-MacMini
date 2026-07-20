import { redirect } from "next/navigation";
import { getClinicRole } from "../lib/clinic-session";
import { roleLanding } from "../lib/roles";

// Root entry → trang đích THEO VAI TRÒ (bác sĩ → /tasks, còn lại → /home).
// Trước đây cứng /work-sessions khiến bác sĩ rơi vào trang ca trực (sai "bác sĩ
// chỉ 2 mục"). Middleware vẫn đẩy về /login nếu chưa đăng nhập.
export default async function Home() {
  const role = await getClinicRole();
  redirect(roleLanding(role));
}
