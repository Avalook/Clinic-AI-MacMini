// Màn của ĐỐI TÁC — một trang, một việc: gửi kết quả vừa làm xong.
//
// NẰM NGOÀI NHÓM `(dashboard)`, cùng chỗ với màn TV phòng chờ và vì cùng một lẽ:
// người mở trang này không phải nhân viên phòng khám, nên họ không nhận khung
// bảng điều khiển — không thanh bên, không chuông báo, không trang chủ. Đặt nó
// trong nhóm ấy thì `layout.tsx` (vốn đẩy vai PARTNER về đây) sẽ đẩy chính
// trang này về chính nó: một vòng chuyển hướng không lối ra.
//
// Ở ngoài nhóm ấy thì layout KHÔNG còn gác quyền hộ, nên trang tự gác — đúng bài
// học của các trang /print: chỉ dựa vào RLS là gõ thẳng URL vẫn vào được.
//
// KHÔNG đọc database ở đây, khác mọi màn trong bảng điều khiển. Dữ liệu đi qua
// `/api/doi-tac` → FastAPI, nơi `get_partner_identity` gác cửa và nơi truy vấn
// lọc theo `node_definition.lam_ben_ngoai`. Gọi PostgREST từ đây là mở cho một
// tài khoản NGOÀI phòng khám một đường đọc bảng, và đó đúng là thứ vai này
// không được có.

import Link from "next/link";
import { redirect } from "next/navigation";

import { requireClinicRole } from "../../lib/clinic-session";
import { canSeeNav } from "../../lib/roles";
import BangDoiTac from "./BangDoiTac";

export const dynamic = "force-dynamic";

export default async function TrangDoiTac() {
  const role = await requireClinicRole();
  if (!canSeeNav(role, "/doi-tac")) redirect("/home");

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 lg:p-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">
            Gửi kết quả
          </h1>
          <p className="text-sm text-ink-muted">
            Những việc phòng khám đã gửi sang, đang chờ kết quả của bạn.
          </p>
        </div>
        {/* Quản lý vào đây để KIỂM chứ không để làm việc — mà trang này nằm ngoài
            bảng điều khiển nên không có thanh bên để bấm về. Thiếu lối ra thì
            người kiểm phải gõ tay URL, và vai đối tác thì không được thấy lối
            này vì /home của họ vốn đã đóng. */}
        {role === "MANAGEMENT" ? (
          <Link
            href="/home"
            className="inline-flex min-h-10 items-center rounded-control border border-line px-3 text-sm font-medium text-ink"
          >
            ← Về bảng điều khiển
          </Link>
        ) : null}
      </header>
      <BangDoiTac />
    </div>
  );
}
