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
import LuuLuongOps from "./LuuLuongOps";
import AgentGiamSat from "./AgentGiamSat";

export const dynamic = "force-dynamic";

const TAB = [
  { ma: "he-thong", ten: "Hệ thống" },
  { ma: "api", ten: "Sức khoẻ API" },
  { ma: "toan-canh", ten: "Toàn cảnh" },
  { ma: "loi", ten: "Lỗi & cảnh báo" },
  { ma: "agent", ten: "Agent giám sát" },
  { ma: "nhat-ky", ten: "Nhật ký vận hành" },
  { ma: "traffic", ten: "Lưu lượng & Thiết bị" },
] as const;
type MaTab = (typeof TAB)[number]["ma"];

export default async function OpsPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string; co_so?: string }>;
}) {
  await requireNavAccess("/ops");
  const { tab, co_so } = await searchParams;
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
        <ToanCanh coSo={co_so} />
      ) : dangMo === "loi" ? (
        <LoiCanhBao />
      ) : dangMo === "agent" ? (
        <AgentGiamSat />
      ) : dangMo === "nhat-ky" ? (
        <NhatKyVanHanh />
      ) : dangMo === "traffic" ? (
        <LuuLuongOps />
      ) : (
        <OpsCenter />
      )}
    </>
  );
}
