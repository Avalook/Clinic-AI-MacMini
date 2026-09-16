// ĐO SINH HIỆU — một việc, một màn.
//
// Tuyền 16/09/2026: "điều dưỡng đang ngồi vào đo sinh hiệu thì phải có node là
// đo sinh hiệu, có danh sách khách theo thứ tự và cứ ấn vào mà điền thông tin
// sinh hiệu đo được cho họ".
//
// Trước đây việc này nằm lẫn trong "Hàng đợi tiếp nhận" và trong tab "Khám" của
// phiếu bệnh án — người đo phải biết mở chỗ nào. Màn này KHÔNG có luật riêng:
// danh sách là `GET /luot-kham/bang`, ghi là `POST …/vitals`, đúng hai đường mà
// mọi màn khác đang dùng. Luật bắt buộc chỉ số nào nằm ở backend (parse_vitals).

import { requireNavAccess } from "@/lib/clinic-session";
import BangDoSinhHieu from "./BangDoSinhHieu";

export const dynamic = "force-dynamic";
export const metadata = { title: "Đo sinh hiệu · ClinicAI" };

export default async function TrangDoSinhHieu() {
  await requireNavAccess("/do-sinh-hieu");
  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <header>
        <h1 className="text-2xl font-semibold text-ink">Đo sinh hiệu</h1>
        <p className="text-sm text-ink-muted">
          Khách đã check-in hôm nay, theo thứ tự đến. Bấm vào khách để điền.
        </p>
      </header>
      <BangDoSinhHieu />
    </main>
  );
}
