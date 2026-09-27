/**
 * DANH SÁCH PHÒNG DỊCH VỤ (CORE-C, 23/09/2026).
 *
 * Trước đây thanh bên khai sẵn chín phòng theo mã (`/phong/KN-SA1`…). Quản lý
 * thêm phòng hay đổi tên phòng thì thanh bên không đổi theo, và người không có
 * ca hôm nay thấy chín mục chen nhau. Nay MỘT mục "Phòng dịch vụ" dẫn tới đây:
 * danh sách đọc thẳng từ `clinic_room` (phòng đang bật, có bước dịch vụ), phòng
 * mình đứng hôm nay lên đầu. Đường dẫn theo `room_id` — đổi tên phòng không làm
 * gãy link.
 *
 * Phòng KHÁM (bước `KHAM-*`) không nằm ở đây: nó có Bàn khám riêng.
 */

import Link from "next/link";

import { fetchFromBackend } from "@/lib/backend-proxy";
import { requireNavAccess } from "@/lib/clinic-session";

import { type PhongHomNay } from "../_lam-viec/api";

export const dynamic = "force-dynamic";
export const metadata = { title: "Phòng dịch vụ · ClinicAI" };

const LA_PHONG_KHAM = (nodes: string[]) => nodes.some((n) => n.startsWith("KHAM-"));

export default async function DanhSachPhongPage() {
  await requireNavAccess("/phong");
  const d = await fetchFromBackend<PhongHomNay>("/api/v1/luot-kham/phong-hom-nay");
  if (!d) {
    return (
      <p className="rounded-card border border-danger bg-danger-bg p-4 text-body text-danger">
        Chưa đọc được danh sách phòng. Tải lại trang sau ít phút.
      </p>
    );
  }
  const cuaToi = new Set(d.phong_cua_toi.map((p) => p.id));
  const phong = d.tat_ca_phong
    .filter((p) => !LA_PHONG_KHAM(p.nodes))
    .sort((a, b) => Number(cuaToi.has(b.id)) - Number(cuaToi.has(a.id)));

  if (phong.length === 0) {
    return (
      <p className="rounded-card bg-surface p-4 text-body text-ink-muted shadow-card">
        Chưa có phòng dịch vụ nào đang bật. Quản lý thêm phòng ở Cấu hình phòng khám.
      </p>
    );
  }

  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {phong.map((p) => (
        <li key={p.id}>
          <Link
            href={`/phong/${p.id}`}
            className="flex min-h-16 flex-col justify-center gap-1 rounded-card bg-surface p-4 shadow-card transition-colors hover:bg-surface-sunken"
          >
            <span className="text-emph font-semibold text-ink">{p.ten}</span>
            <span className="text-meta text-ink-muted">
              {cuaToi.has(p.id) ? "Hôm nay bạn đứng phòng này" : p.tang ? `Tầng ${p.tang}` : " "}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
