/**
 * Một màn khám RIÊNG cho từng loại khám: /kham/noi-tiet, /kham/phu-khoa, …
 *
 * Dùng lại nguyên Bàn khám bác sĩ — Tuyền chốt đó là màn chuẩn ("đây là view tôi
 * muốn làm") — chỉ khác một điều: danh sách chỉ gồm khách của ĐÚNG loại khám này,
 * lọc theo `service_type.form_code`. Không có thân màn thứ hai để lệch nhau.
 *
 * Xem lib/loai-kham.ts để biết vì sao tách.
 */

import { notFound } from "next/navigation";

import { requireNavAccess } from "@/lib/clinic-session";
import { HREF_KHAM, loaiKhamTheoSlug } from "@/lib/loai-kham";
import { fetchCatalogue } from "@/lib/orders-server";
import { fetchWorklist } from "@/lib/worklist-server";

import DoctorBoard from "../../doctor/board/DoctorBoard";
import LiveBoardSync from "../../LiveBoardSync";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ loai: string }>;
}) {
  const loai = loaiKhamTheoSlug((await params).loai);
  return { title: `${loai?.ten ?? "Khám"} · ClinicAI` };
}

export default async function TrangKham({
  params,
}: {
  params: Promise<{ loai: string }>;
}) {
  const loai = loaiKhamTheoSlug((await params).loai);
  if (!loai) notFound();
  await requireNavAccess(HREF_KHAM(loai.slug));

  const [result, catalogue] = await Promise.all([
    fetchWorklist("khu_bac_si"),
    fetchCatalogue(),
  ]);

  return (
    <>
      <LiveBoardSync />
      <main className="page-in flex flex-col gap-4 p-4 xl:p-6">
        <header>
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">{loai.ten}</h1>
        </header>
        {!result.ok ? (
          // Mất kết nối không được trông giống một phòng khám vắng khách.
          <div className="rounded-card border border-danger bg-danger-bg p-5">
            <p className="font-medium text-danger">Không tải được danh sách khám</p>
            <p className="mt-1 text-sm text-danger">
              {result.reason === "no-session"
                ? "Phiên đăng nhập đã hết hạn — đăng nhập lại."
                : "Không kết nối được máy chủ. ĐỪNG coi đây là không có khách."}
            </p>
          </div>
        ) : (
          <DoctorBoard
            catalogue={catalogue.ok ? catalogue.data : []}
            items={result.items
              // LỌC THEO MÃ PHIẾU CỦA DỊCH VỤ, không theo chữ trong tên. Dò theo
              // tên là con đường đã cho "Sản 1" hai câu trả lời ở hai màn.
              .filter((i) => i.form_code === loai.formCode)
              .sort(
                (a, b) =>
                  new Date(a.created_at ?? 0).getTime() -
                  new Date(b.created_at ?? 0).getTime(),
              )}
          />
        )}
      </main>
    </>
  );
}
