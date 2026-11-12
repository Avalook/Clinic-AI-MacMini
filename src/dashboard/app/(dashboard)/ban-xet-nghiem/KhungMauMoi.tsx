// (Client — chỉ `BanXetNghiem.tsx` dùng.) Khung ngay sau khi lấy mẫu thành công.
// Có mã (công tắc "Hiện mã ống" bật — máy chủ trả `ma_mau`) ⇒ mã to để viết / dán lên
// ống. Không mã (tắt, mặc định 09/11) ⇒ chỉ "Đã lấy mẫu · Hẹn trả …". Màn không tự suy:
// có mã hay không là do máy chủ trả.

import { ngayVN } from "./kieu";

export default function KhungMauMoi({ ma, hen }: { ma: string | null; hen: string | null }) {
  if (!ma) {
    return (
      <div className="rounded-card border border-line bg-surface p-4 text-center shadow-card">
        <p className="text-body font-semibold text-ink">Đã lấy mẫu{hen ? ` · Hẹn trả ${ngayVN(hen)}` : ""}</p>
      </div>
    );
  }
  return (
    <div className="rounded-card border border-line bg-surface p-4 text-center shadow-card">
      <p className="text-meta text-ink-muted">Mã ống — viết / dán lên ống</p>
      <p className="font-mono text-title font-bold tracking-widest text-ink">{ma}</p>
      {hen ? <p className="text-meta text-ink-muted">Hẹn trả {ngayVN(hen)}</p> : null}
    </div>
  );
}
