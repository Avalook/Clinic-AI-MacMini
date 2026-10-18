import { requireNavAccess } from "@/lib/clinic-session";
import { layCoSo } from "@/lib/danh-muc";
import KeToan from "./KeToan";

export const dynamic = "force-dynamic";
export const metadata = { title: "Kế toán" };

export default async function TrangKeToan() {
  await requireNavAccess("/ke-toan");
  const coSo = await layCoSo();
  return <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
    <header className="space-y-1">
      <h1 className="text-title font-semibold text-ink">Kế toán</h1>
    </header>
    <KeToan coSo={coSo} />
  </main>;
}
