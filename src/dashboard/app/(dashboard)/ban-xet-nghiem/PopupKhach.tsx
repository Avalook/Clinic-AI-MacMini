// (Client — chỉ `BanXetNghiem.tsx` dùng.) Popup "mọi lần xét nghiệm của khách" khi bấm
// một khách ở ô tìm (bản mẫu 05/11). Chỉ VẼ việc máy chủ đã trả cho bàn: chữ trạng
// thái, chip, câu "vì sao", tiền/mẫu/kết quả — không tự suy luật. Bấm một dòng ⇒ mở
// đúng ngày + khách đó ở tab "Việc theo ngày".

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import HopChiTiet from "@/components/ui/HopChiTiet";

import { ngayVN, tien, type Viec } from "./kieu";

export default function PopupKhach({
  ten,
  maBn,
  viec,
  onMo,
  onDong,
}: {
  ten: string;
  maBn: string | null;
  viec: Viec[];
  onMo: (v: Viec) => void;
  onDong: () => void;
}) {
  const ds = [...viec].sort((a, b) => b.ngay_chi_dinh.localeCompare(a.ngay_chi_dinh));
  const conDo = ds.filter((v) => v.trang_thai.con_ton).length;
  return (
    <HopChiTiet tieuDe={`${ten}${maBn ? ` · Mã KH ${maBn}` : ""}`} onDong={onDong}>
      <p className="mb-3 text-meta text-ink-muted">
        {ds.length} chỉ định xét nghiệm · {conDo} việc còn dở
      </p>
      <ul className="divide-y divide-line rounded-card border border-line">
        {ds.map((v) => (
          <li key={v.order_id} className="flex flex-col gap-1 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-body">
                <span className="font-semibold text-ink">{v.ten_dich_vu}</span>{" "}
                <span className="text-ink-muted">
                  · {ngayVN(v.ngay_chi_dinh)} · {v.ten_doi_tac}
                </span>
              </p>
              <Chip tone={v.trang_thai.chip_mau}>{v.trang_thai.chip_nhan}</Chip>
            </div>
            <p className="text-meta text-ink-soft">{v.trang_thai.vi_sao}</p>
            <p className="text-meta text-ink-muted">
              Tiền: {v.da_thu !== null ? `đã thu ${tien(v.da_thu)}` : `chưa thu${v.gia_goi_y ? ` (gợi ý ${tien(v.gia_goi_y)})` : ""}`} · Mẫu:{" "}
              {/* Công tắc "Hiện mã ống" tắt ⇒ ma_mau null dù đã có mẫu (mau_id). */}
              {v.ma_mau ?? (v.mau_id ? "đã lấy mẫu" : "chưa lấy")} · Kết quả: {v.ten_tep ?? "chưa có"}
            </p>
            <div>
              <Button type="button" size="sm" variant="ghost" onClick={() => onMo(v)}>
                Mở việc này
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </HopChiTiet>
  );
}
