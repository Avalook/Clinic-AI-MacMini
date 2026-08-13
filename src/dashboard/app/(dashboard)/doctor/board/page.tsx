/**
 * Bàn khám — the doctor's board.
 *
 * Reads the same worklist endpoint as reception with workspace=khu_bac_si. The
 * seven nodes in that workspace come from the clinic's own catalogue, so a
 * clinic that adds a consultation type gets it on the board without a deploy.
 */

import { requireNavAccess } from "@/lib/clinic-session";
import { fetchCatalogue } from "@/lib/orders-server";
import { fetchWorklist } from "@/lib/worklist-server";

import DoctorBoard from "./DoctorBoard";
import LiveBoardSync from "../../LiveBoardSync";

export const metadata = { title: "Bàn khám · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function DoctorBoardPage() {
  await requireNavAccess("/doctor/board");
  // Bảng dịch vụ nạp SẴN Ở ĐÂY để màn chỉ định mở được ngay bên cạnh thay vì
  // nhảy sang trang khác. Nó giống nhau với mọi bác sĩ và hiếm khi đổi — chính
  // trang /doctor/orders cũng nạp theo cách này.
  const [result, catalogue] = await Promise.all([
    fetchWorklist("khu_bac_si"),
    fetchCatalogue(),
  ]);

  return (
    <>
      <LiveBoardSync />
    <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
      {/* TIÊU ĐỀ VÀ NGÀY ĐÃ CÓ Ở THANH TRÊN CÙNG.
          Trang này từng in lại cả hai: một dòng "Danh sách khám bệnh đang mở"
          ngay dưới "Bàn khám bác sĩ", và một ô ngày ngay dưới ô ngày. Hai lần
          cùng một thông tin đẩy phần việc thật xuống gần nửa màn hình. */}

      {!result.ok ? (
        /* An outage must not look like an empty clinic. */
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">Không tải được bàn khám</p>
          <p className="mt-1 text-sm text-danger">
            {result.reason === "no-session"
              ? "Phiên đăng nhập đã hết hạn — đăng nhập lại."
              : "Không kết nối được máy chủ. ĐỪNG coi đây là bàn khám trống."}
            {result.detail ? ` (${result.detail})` : ""}
          </p>
        </div>
      ) : (
        <>
          <DoctorBoard
            catalogue={catalogue.ok ? catalogue.data : []}
            items={[...result.items].sort(
              (a, b) =>
                new Date(a.created_at ?? 0).getTime() -
                new Date(b.created_at ?? 0).getTime(),
            )}
          />
        </>
      )}
    </main>
    </>
  );
}
