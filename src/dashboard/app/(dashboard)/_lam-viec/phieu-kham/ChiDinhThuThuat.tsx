"use client";

// Mục F — CHỈ ĐỊNH THỦ THUẬT.
//
// Chọn một thủ thuật = tạo một CHỈ ĐỊNH (`service_order`) — việc của module Chỉ
// định, qua lệnh của nó, có người duyệt. Phiếu không giữ danh sách thủ thuật
// nào của riêng mình. Nên component này ĐIỀU KHIỂN TỪ NGOÀI: báo `onChon`, còn
// tạo chỉ định là việc của Bàn khám.
//
// Danh sách là NHÃN của tài liệu nguồn. Mục nào danh mục chưa gắn mã dịch vụ
// (`service_code` trống) thì khoá lại và nói ra — không tự dò tên "Soi cổ tử
// cung" để đoán ra mã, vì đoán sai là chỉ định nhầm dịch vụ và thu nhầm tiền.

import Chip from "@/components/ui/Chip";
import type { ThuThuatNguon } from "@/lib/phieu-kham";

export default function ChiDinhThuThuat({
  ds,
  daChon,
  onChon,
}: {
  ds: ThuThuatNguon[];
  /** Mã mục (`procedure_N`) đang có chỉ định. */
  daChon: string[];
  /** Không truyền = chỉ đọc (chưa nối lệnh tạo chỉ định). */
  onChon?: (t: ThuThuatNguon, chon: boolean) => void;
}) {
  const thieuMa = ds.filter((t) => !t.service_code).length;
  return (
    <div className="space-y-2">
      {thieuMa > 0 ? (
        <p className="text-meta text-ink-muted">
          {thieuMa}/{ds.length} mục chưa được danh mục gắn mã dịch vụ — chưa tạo
          chỉ định được.
        </p>
      ) : null}
      <ul className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2 lg:grid-cols-3">
        {ds.map((t) => {
          const khoa = !onChon || !t.service_code || Boolean(t.khoa);
          return (
            <li key={t.ma}>
              <label className="flex min-h-10 items-center gap-2 text-body text-ink">
                <input
                  type="checkbox"
                  checked={daChon.includes(t.ma)}
                  disabled={khoa}
                  onChange={(e) => onChon?.(t, e.target.checked)}
                  className="size-4 accent-brand-600"
                />
                <span className={khoa ? "text-ink-muted" : ""}>{t.nhan}</span>
                {t.form_id_ket_qua ? <Chip tone="brand">Có biểu mẫu</Chip> : null}
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
