// Kho vật tư (G8a, 14/10/2026) — đọc qua `GET /api/v1/vat-tu-kho/ton` (tồn từng nơi
// chứa kèm nhắc, danh sách nơi chứa, danh mục vật tư để chọn). Cửa trang theo LEGO
// "Kho vật tư" (`vat_tu.manage`); ghi qua proxy `/api/vat-tu-kho/[action]`.

import { fetchFromBackend } from "../../../lib/backend-proxy";
import { requireNavAccess } from "../../../lib/clinic-session";
import { quyenCuaToi } from "../../../lib/quyen-cua-toi";
import type { DongVatTu } from "../cashier/VatTuBangGia";
import type { GoiChoDuyet } from "./ChoDuyetVatTu";
import type { PhieuVatTu } from "./DanhSachPhieuVatTu";
import KhoVatTu from "./KhoVatTu";
import type { DongTon, NoiChua } from "./TonVatTu";

export const dynamic = "force-dynamic";

interface GoiTon {
  items: DongTon[];
  noi_chua: NoiChua[];
  vat_tu: DongVatTu[];
}

export default async function KhoVatTuPage() {
  await requireNavAccess("/kho-vat-tu");
  const [goi, phieu, choDuyet, quyen, ban] = await Promise.all([
    fetchFromBackend<GoiTon>("/api/v1/vat-tu-kho/ton"),
    // Đọc hỏng thì tab Phiếu hiện rỗng, không chặn cả màn.
    fetchFromBackend<{ items: PhieuVatTu[] }>("/api/v1/vat-tu-kho/phieu"),
    // G8b: yêu cầu nhập chờ duyệt. Đọc hỏng → tab Chờ duyệt tự báo, không chặn cả màn.
    fetchFromBackend<GoiChoDuyet>("/api/v1/vat-tu-kho/cho-duyet"),
    quyenCuaToi(),
    // Chỉ lấy số trên chip; danh sách đầy đủ do tab tự đọc. Đọc hỏng → chip trống.
    fetchFromBackend<{ cho_gan: number; cho_xu_ly: number }>("/api/v1/vat-tu-kho/ban"),
  ]);
  if (!goi) {
    return (
      <p role="alert" className="p-6 text-body text-danger">
        Không đọc được kho vật tư (máy chủ không trả lời hoặc tài khoản chưa có khối “Kho vật tư”).
      </p>
    );
  }
  const ton = goi.items.map((t) => ({
    ...t,
    so_luong: Number(t.so_luong),
    ton_toi_thieu: Number(t.ton_toi_thieu),
  }));
  return (
    <KhoVatTu
      ton={ton}
      noiChua={goi.noi_chua}
      vatTu={goi.vat_tu}
      phieu={(phieu?.items ?? []).map((p) => ({
        ...p,
        dong: p.dong.map((d) => ({
          ...d,
          so_luong: Number(d.so_luong),
          thuc_te: d.thuc_te == null ? null : Number(d.thuc_te),
          gia_nhap: Number(d.gia_nhap),
        })),
      }))}
      choDuyet={choDuyet}
      suaGiaDuoc={quyen.has("price.service.manage")}
      banCanXuLy={(ban?.cho_gan ?? 0) + (ban?.cho_xu_ly ?? 0)}
    />
  );
}
