// Kho thuốc — danh mục thuốc + tồn theo lô. Đọc qua backend
// `GET /api/v1/pharmacy/danh-muc` và `GET /api/v1/pharmacy/inventory`
// (24/09/2026; trước đọc thẳng `drug_batch` bằng Supabase). 25/09: thêm tab
// Danh mục (sửa tên/giá/hướng dẫn) và nhập lô / điều chỉnh / huỷ. 29/09: thêm
// phiếu nhập, kiểm kho, thẻ kho, xuất nhập tồn (đọc qua `/api/pharmacy/[action]`).

import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { requireNavAccess } from "../../../../lib/clinic-session";
import { quyenCuaToi } from "../../../../lib/quyen-cua-toi";
import type { DongChoGanLo } from "./ChoGanLo";
import type { ThuocKho } from "./DanhMucKho";
import type { ExpiryState } from "./InventoryBoard";
import KhoThuoc from "./KhoThuoc";

export const dynamic = "force-dynamic";

interface LoTon {
  id: string;
  drug_catalog_id: string | null;
  name_base: string | null;
  variant: string | null;
  // Bốn cột NOT NULL ở `drug_batch` (xem PharmacyService.nhap_lo).
  batch_code: string;
  expiry_date: string;
  quantity_on_hand: number;
  unit: string;
  cost_price: number | null;
  received_at: string | null;
  // 29/09/2026: máy chủ tính hạn theo ngày VN — màn không tự đếm ngày.
  trang_thai_han: ExpiryState;
  canh_bao_han: boolean;
}

export default async function PharmacyInventoryPage() {
  await requireNavAccess("/pharmacy/inventory");
  const [data, dm, cho, quyen] = await Promise.all([
    fetchFromBackend<{ items: LoTon[] }>("/api/v1/pharmacy/inventory"),
    fetchFromBackend<{ items: ThuocKho[] }>("/api/v1/pharmacy/danh-muc"),
    // 28/09: thuốc đã giao chưa gán lô — đọc hỏng thì tab rỗng, không chặn màn.
    fetchFromBackend<{ dong: DongChoGanLo[] }>("/api/v1/pharmacy/cho-gan-lo"),
    // Ghi kho (nhập, kiểm, điều chỉnh, sửa danh mục) = `pharmacy.dispense` —
    // chỉ để ẨN nút; máy chủ vẫn tự kiểm ở mọi lệnh.
    quyenCuaToi(),
  ]);
  if (!data || !dm) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được kho (máy chủ không trả lời hoặc tài khoản không có quyền xem nhà
        thuốc).
      </div>
    );
  }
  const batches = [...data.items]
    .sort((a, b) => a.expiry_date.localeCompare(b.expiry_date))
    .map(({ name_base, variant, ...b }) => ({
      ...b,
      quantity_on_hand: Number(b.quantity_on_hand),
      drug: { name_base, name_raw: name_base, variant },
    }));
  const thuoc = dm.items.map((t) => ({
    ...t,
    gia: t.gia == null ? null : Number(t.gia),
    ton: Number(t.ton),
    so_lo: Number(t.so_lo),
    ton_toi_thieu: t.ton_toi_thieu == null ? null : Number(t.ton_toi_thieu),
  }));
  const choGanLo = (cho?.dong ?? []).map((d) => ({
    ...d,
    so_luong: Number(d.so_luong),
    lo_gan_duoc: d.lo_gan_duoc.map((b) => ({ ...b, ton: Number(b.ton) })),
  }));
  return (
    <KhoThuoc
      batches={batches}
      thuoc={thuoc}
      choGanLo={choGanLo}
      ghiDuoc={quyen.has("pharmacy.dispense")}
    />
  );
}
