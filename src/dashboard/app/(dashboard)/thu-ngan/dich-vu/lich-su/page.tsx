import { requireNavAccess } from "@/lib/clinic-session";
import TabThuNgan from "../../TabThuNgan";

export const metadata = { title: "Lịch sử thu dịch vụ · ClinicAI" };
export const dynamic = "force-dynamic";

export default async function TrangLichSuThu() {
  await requireNavAccess("/thu-ngan/dich-vu/lich-su");
  return <main className="page-in flex min-w-0 flex-col gap-4 p-4 lg:p-5">
    <h1 className="text-title font-semibold text-ink">Lịch sử thu dịch vụ</h1>
    <TabThuNgan quay="dich_vu" chiXem />
  </main>;
}
