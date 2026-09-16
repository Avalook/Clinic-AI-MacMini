// Màn của ĐỐI TÁC — một trang, một việc: gửi kết quả vừa làm xong.
//
// KHÔNG đọc database ở đây, khác mọi màn khác trong thư mục này. Dữ liệu đi qua
// `/api/doi-tac` → FastAPI, nơi `get_partner_identity` gác cửa và nơi truy vấn
// lọc theo `node_definition.lam_ben_ngoai`. Gọi PostgREST từ đây sẽ mở cho một
// tài khoản NGOÀI phòng khám một đường đọc bảng, và đó đúng là thứ vai này
// không được có.

import { requireNavAccess } from "../../../lib/clinic-session";
import BangDoiTac from "./BangDoiTac";

export const dynamic = "force-dynamic";

export default async function TrangDoiTac() {
  await requireNavAccess("/doi-tac");
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          Gửi kết quả
        </h1>
        <p className="text-sm text-ink-muted">
          Những việc phòng khám đã gửi sang, đang chờ kết quả của bạn.
        </p>
      </header>
      <BangDoiTac />
    </div>
  );
}
