import { requireNavAccess } from "@/lib/clinic-session";
import { layCoSo } from "@/lib/danh-muc";
import DanhSachHoaDon from "./DanhSachHoaDon";

export const dynamic = "force-dynamic";
export const metadata = { title: "Danh sách hoá đơn" };

export default async function TrangHoaDon() {
  await requireNavAccess("/hoa-don");
  const coSo = await layCoSo();
  return <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
    <header><h1 className="text-title font-semibold text-ink">Danh sách hoá đơn</h1></header>
    <DanhSachHoaDon coSo={coSo} />
  </main>;
}
