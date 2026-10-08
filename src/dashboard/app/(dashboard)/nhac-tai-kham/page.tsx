// Nhắc tái khám — danh sách CSKH phải gọi, lấy từ GET /api/v1/cskh/recalls.
//
// KHÁC /cskh-tasks. Màn kia là việc quanh LỊCH ĐÃ CÓ (nhắc lịch mai, nhắc sớm
// trong tuần, lịch bác sĩ từ chối) và nó đọc thẳng bảng `appointment`. Màn này
// là người CHƯA CÓ LỊCH: bác sĩ đã dặn ngày tái khám trong phiếu khám mà bệnh
// nhân chưa đặt lại. Hai danh sách rời nhau — một người nằm ở đây đúng là người
// KHÔNG nằm ở kia, vì endpoint loại mọi ai đã có lịch hẹn còn hiệu lực.
//
// Toàn bộ luật (nhìn lại 183 ngày, hạn tới +7 ngày, loại người đã đặt lịch, chỉ
// trả đúng lời dặn chứ không trả bệnh án) nằm trong RecallService phía FastAPI.
// Trang này không tự dựng lại một bản nào của luật đó.

import { requireNavAccess } from "../../../lib/clinic-session";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import { layCoSo } from "../../../lib/danh-muc";
import { listBookableDoctors } from "../../../lib/doctors-server";
import LieuTrinhCskh from "./LieuTrinhCskh";
import TabNhacTaiKham from "./TabNhacTaiKham";
import ViecGoiNhac, { type DuLieu } from "./ViecGoiNhac";

export const dynamic = "force-dynamic";

export default async function NhacTaiKhamPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  await requireNavAccess("/nhac-tai-kham");
  const { tab } = await searchParams;

  // null = backend không trả lời (chưa cấu hình CLINIC_API_URL, hết phiên, 403).
  // Phải phân biệt với danh sách rỗng — "không đọc được" và "hôm nay không ai
  // cần gọi" nhìn giống hệt nhau trên màn hình mà hậu quả thì ngược nhau.
  //
  // Endpoint này SINH VIỆC của hôm nay trước khi trả về. Dự án chưa có bộ hẹn
  // giờ nào, nên mở màn hình là đường chắc chắn nhất; hàm sinh idempotent nên
  // tải lại trang mười lần vẫn ra đúng chừng ấy việc.
  //
  // Bác sĩ + cơ sở: cho [Đặt lịch buổi kế] của tab Liệu trình — mở đúng bộ đặt
  // lịch sẵn có (`DatLichModal`), như màn Quản lý khách hàng.
  const [duLieu, coSo, bacSi] = await Promise.all([
    fetchFromBackend<DuLieu>("/api/v1/cskh/recall-jobs"),
    layCoSo(),
    listBookableDoctors(),
  ]);

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      {/* Tiêu đề và câu mô tả nay nằm ở THANH TRÊN CÙNG (GlobalHeader), cùng
          chỗ với mọi trang khác. Để cả hai nơi thì tiêu đề hiện hai lần và phần
          việc thật bị đẩy xuống gần nửa màn hình. */}

      <TabNhacTaiKham
        tabDau={tab === "lieu-trinh" ? "lieu-trinh" : "nhac"}
        nhac={<ViecGoiNhac duLieu={duLieu} khongDocDuoc={duLieu === null} />}
        lieuTrinh={
          <LieuTrinhCskh
            doctors={bacSi}
            locations={coSo.map((c) => ({ id: c.id, label: c.name }))}
          />
        }
      />
    </main>
  );
}
