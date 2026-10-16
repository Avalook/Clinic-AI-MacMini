// Kho thuốc — danh mục thuốc + tồn theo lô. Đọc qua backend
// `GET /api/v1/pharmacy/danh-muc` và `GET /api/v1/pharmacy/inventory`
// (24/09/2026; trước đọc thẳng `drug_batch` bằng Supabase). 25/09: thêm tab
// Danh mục (sửa tên/giá/hướng dẫn) và nhập lô / điều chỉnh / huỷ. 29/09: thêm
// phiếu nhập, kiểm kho, thẻ kho, xuất nhập tồn (đọc qua `/api/pharmacy/[action]`).

import { fetchFromBackend } from "../../../../lib/backend-proxy";
import { requireNavAccess } from "../../../../lib/clinic-session";
import { QUYEN_BAN_LE, quyenCuaToi } from "../../../../lib/quyen-cua-toi";
import type { DongChoGanLo } from "./ChoGanLo";
import type { ThuocKho } from "./DanhMucKho";
import type { CauHinhHan, ExpiryState } from "./InventoryBoard";
import KhoThuoc from "./KhoThuoc";

export const dynamic = "force-dynamic";

interface LoTon {
  id: string;
  drug_catalog_id: string | null;
  name_base: string | null;
  variant: string | null;
  batch_code: string;
  expiry_date: string | null;
  quantity_on_hand: number;
  unit: string;
  cost_price: number | null;
  received_at: string | null;
  // 29/09/2026: máy chủ tính hạn theo ngày VN — màn không tự đếm ngày.
  trang_thai_han: ExpiryState;
  canh_bao_han: boolean;
  huy_lo_txn_id: string | null;
  // 14/10 (G7): lô nằm ở KHO hay QUẦY (cơ sở không tách thì mọi lô là QUAY).
  noi_chua: "KHO" | "QUAY";
}

// Link từ báo cáo hàng hoá (`/reports?tab=hang-hoa`) mở thẳng tab Kiểm kê ca:
// `/pharmacy/inventory?tab=kiem-ke-ca&ngay=YYYY-MM-DD&ca=SANG|CHIEU|TOI`. Tham số
// lạ (gõ tay, link hỏng) bị bỏ — màn mở tab đầu / hôm nay như thường, không ném.
const NGAY_HOP_LE = /^\d{4}-\d{2}-\d{2}$/;
const CA_HOP_LE = ["SANG", "CHIEU", "TOI"] as const;

export default async function PharmacyInventoryPage({
  searchParams,
}: {
  searchParams?: Promise<{ tab?: string; ngay?: string; ca?: string }>;
}) {
  await requireNavAccess("/pharmacy/inventory");
  const { tab, ngay, ca } = (await searchParams) ?? {};
  const [data, dm, cho, quyen, cauHinhHan, tach] = await Promise.all([
    fetchFromBackend<{ items: LoTon[]; tach_kho_quay?: boolean }>("/api/v1/pharmacy/inventory"),
    fetchFromBackend<{ items: ThuocKho[] }>("/api/v1/pharmacy/danh-muc"),
    // 28/09: thuốc đã giao chưa gán lô — đọc hỏng thì tab rỗng, không chặn màn.
    fetchFromBackend<{ dong: DongChoGanLo[] }>("/api/v1/pharmacy/cho-gan-lo"),
    // Ghi kho (nhập, kiểm, điều chỉnh, sửa danh mục) = `pharmacy.dispense` —
    // chỉ để ẨN nút; máy chủ vẫn tự kiểm ở mọi lệnh.
    quyenCuaToi(),
    fetchFromBackend<CauHinhHan>("/api/v1/pharmacy/so-ngay-canh-bao"),
    // G7: công tắc tách kho / quầy + người này có sửa được không (máy chủ quyết).
    fetchFromBackend<{ tach_kho_quay: boolean; sua_duoc: boolean }>("/api/v1/pharmacy/tach-kho-quay"),
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
    .sort((a, b) => (a.expiry_date ?? "9999").localeCompare(b.expiry_date ?? "9999"))
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
      moBanLe={QUYEN_BAN_LE.some((q) => quyen.has(q))}
      cauHinhHan={cauHinhHan ?? undefined}
      tachKhoQuay={data.tach_kho_quay === true}
      suaTachDuoc={tach?.sua_duoc === true}
      tabDau={tab}
      ngayKiemKe={ngay && NGAY_HOP_LE.test(ngay) ? ngay : undefined}
      caKiemKe={CA_HOP_LE.find((c) => c === ca)}
    />
  );
}
