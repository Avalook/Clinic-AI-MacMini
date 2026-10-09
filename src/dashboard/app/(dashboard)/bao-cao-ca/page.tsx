import Link from "next/link";
import { buttonClass } from "@/components/ui/Button";
import { requireNavAccess } from "@/lib/clinic-session";
import CuoiNgay from "../reports/CuoiNgay";
import BaoCaoHangHoa from "../reports/BaoCaoHangHoa";

export const dynamic = "force-dynamic";

export default async function BaoCaoCaPage({ searchParams }: {
  searchParams: Promise<{ tab?: string }>;
}) {
  await requireNavAccess("/bao-cao-ca");
  const { tab } = await searchParams;
  const hangHoa = tab === "hang-hoa";
  return (
    <main className="page-in min-w-0 space-y-4 p-4 lg:p-5">
      <h1 className="text-title font-semibold text-ink">Báo cáo ca của tôi</h1>
      <nav aria-label="Báo cáo ca" className="flex flex-wrap gap-2 print:hidden">
        <Link href="/bao-cao-ca" className={buttonClass(hangHoa ? "ghost" : "primary", "md")}>Cuối ca</Link>
        <Link href="/bao-cao-ca?tab=hang-hoa" className={buttonClass(hangHoa ? "primary" : "ghost", "md")}>Hàng hoá</Link>
      </nav>
      {hangHoa ? <BaoCaoHangHoa khoaCa /> : <CuoiNgay khoaCa />}
    </main>
  );
}
