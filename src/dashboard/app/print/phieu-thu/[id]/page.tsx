// In PHIẾU THU / PHIẾU HOÀN của quầy (27/09/2026, đợt 3 — bản mẫu quầy thu).
// Mở từ tab Lịch sử của /thu-ngan. Quyền đọc do máy chủ gác
// (GET /api/v1/cashier/phieu/{id} — cùng quyền đứng quầy thu).
import InPhieuThu from "./InPhieuThu";

export const dynamic = "force-dynamic";
export const metadata = { title: "In phiếu thu · ClinicAI" };

export default async function InPhieuThuPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ loai?: string }>;
}) {
  const { id } = await params;
  const { loai } = await searchParams;
  return <InPhieuThu id={id} loai={loai === "hoan" ? "hoan" : "thu"} />;
}
