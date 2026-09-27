// Màn của ĐỐI TÁC — một trang, một việc: nhận việc phòng khám gửi sang và gửi
// tài liệu kết quả về.
//
// NẰM NGOÀI NHÓM `(dashboard)`: `layout.tsx` của nhóm ấy đẩy vai PARTNER về đây,
// nên đặt trang này trong nhóm là một vòng chuyển hướng không lối ra. Nhưng từ
// 17/09/2026 (Tuyền: "clone thêm giao diện của vai trò chung cho tài khoản đối
// tác, hiện đang rất cơ bản") trang TỰ dựng cùng khung `Shell` — thanh bên, đầu
// trang, nút thoát — như mọi vai khác. Thanh bên của đối tác chỉ có đúng mục
// này (nav-items: `/doi-tac` chỉ mở cho PARTNER + MANAGEMENT).
//
// Ở ngoài nhóm ấy thì layout KHÔNG còn gác quyền hộ, nên trang tự gác — đúng bài
// học của các trang /print: chỉ dựa vào RLS là gõ thẳng URL vẫn vào được.
//
// KHÔNG đọc database ở đây. Dữ liệu đi qua `/api/doi-tac` → FastAPI, nơi
// `get_partner_identity` gác cửa và nơi truy vấn lọc theo
// `node_definition.lam_ben_ngoai`. Gọi PostgREST từ đây là mở cho một tài khoản
// NGOÀI phòng khám một đường đọc bảng, và đó đúng là thứ vai này không được có.

import { logout } from "../(auth)/login/actions";
import Shell from "../(dashboard)/Shell";
import { NotificationProvider } from "../(dashboard)/NotificationContext";
import { requireClinicRole, requireNavAccess } from "../../lib/clinic-session";
import { getCurrentStaff } from "../../lib/current-staff";
import { ROLE_LABEL } from "../../lib/roles";
import BangDoiTac from "./BangDoiTac";

export const dynamic = "force-dynamic";
export const metadata = { title: "Việc của đối tác · ClinicAI" };

export default async function TrangDoiTac() {
  const role = await requireClinicRole();
  // Lego 21 "Đối tác" (27/09/2026): cùng cửa trang với mọi màn lego. Tài khoản
  // đối tác bị `/phan-quyen/toi` từ chối (hai chiều khoá) nên rơi về luật vai
  // gốc — vẫn vào; backend `get_partner_identity` nay đòi thêm `partner.work`.
  await requireNavAccess("/doi-tac");
  const staff = await getCurrentStaff();
  const identity = [
    ROLE_LABEL[role],
    staff?.full_name ?? staff?.short_name ?? "",
    staff?.clinic_name ?? "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <NotificationProvider staffId={staff?.id ?? null}>
      <Shell
        role={role}
        identity={identity}
        tenNguoi={staff?.full_name ?? staff?.short_name ?? undefined}
        leaveAction={logout}
      >
        <main className="page-in flex flex-col gap-4">
          {/* Tiêu đề + đếm việc nằm trong BangDoiTac (cùng khuôn màn phòng,
              28/09/2026). */}
          <BangDoiTac />
        </main>
      </Shell>
    </NotificationProvider>
  );
}
