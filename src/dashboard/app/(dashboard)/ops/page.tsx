// VẬN HÀNH HỆ THỐNG — một mục thanh bên, ba tab (Tuyền "gộp hết" 18/09/2026).
//
// Trước đó là ba màn cho cùng một người (Quản lý): /ops, /portal ("Command
// Center") và /ops/telemetry ("Sức khoẻ API"), hai trong số đó cùng đọc
// /api/ops/summary. Hai đường cũ giờ chuyển hướng vào đúng tab của chúng.
// Xem docs/SITEMAP.md.
import Link from "next/link";
import { buttonClass } from "@/components/ui/Button";
import { requireNavAccess } from "../../../lib/clinic-session";
import OpsCenter from "./OpsCenter";
import SucKhoeApi from "./SucKhoeApi";
import LoiCanhBao from "./LoiCanhBao";
import NhatKyVanHanh from "./NhatKyVanHanh";
import ToanCanh from "./ToanCanh";

export const dynamic = "force-dynamic";

const TAB = [
  { ma: "he-thong", ten: "Hệ thống" },
  { ma: "api", ten: "Sức khoẻ API" },
  { ma: "toan-canh", ten: "Toàn cảnh" },
  // Theo dõi lỗi Pha 1 (27/09/2026): bộ canh gác + kho lỗi tự dựng, nhật ký ai
  // làm gì / bao lâu. Xem services/canh_gac.py, kho_loi.py, nhat_ky_van_hanh.py.
  { ma: "loi", ten: "Lỗi & cảnh báo" },
  { ma: "nhat-ky", ten: "Nhật ký vận hành" },
] as const;
type MaTab = (typeof TAB)[number]["ma"];

export default async function OpsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  await requireNavAccess("/ops");
  const { tab } = await searchParams;
  // Tham số lạ (gõ tay, link hỏng) thì về tab đầu, không ném.
  const dangMo: MaTab = TAB.some((t) => t.ma === tab) ? (tab as MaTab) : "he-thong";
  return (
    <>
      <nav aria-label="Vận hành hệ thống" className="flex flex-wrap gap-2 px-4 pt-4 lg:px-5">
        {TAB.map((t) => (
          <Link
            key={t.ma}
            href={t.ma === "he-thong" ? "/ops" : `/ops?tab=${t.ma}`}
            aria-current={t.ma === dangMo ? "page" : undefined}
            className={buttonClass(t.ma === dangMo ? "primary" : "ghost", "sm")}
          >
            {t.ten}
          </Link>
        ))}
      </nav>
      {dangMo === "api" ? (
        <SucKhoeApi />
      ) : dangMo === "toan-canh" ? (
        <ToanCanh />
      ) : dangMo === "loi" ? (
        <LoiCanhBao />
      ) : dangMo === "nhat-ky" ? (
        <NhatKyVanHanh />
      ) : (
        <OpsCenter />
      )}
    </>
  );
}
