// Ô "Đã gửi qua" cho nút "Đã gửi kết quả cho bệnh nhân" (Tuyền 12/11/2026: chọn kênh
// như thẻ việc ở Việc của đối tác). Trước đó nút luôn ghi sổ "GOI" và máy chủ đổi
// thành "Đưa trực tiếp" cho tờ kết quả — sai kênh thật. Tách tệp riêng vì
// HanhDongTrangThai.tsx đã quá trần kích thước.

import OChon from "@/components/ui/OChon";
import { KENH_GUI_SO_CSKH } from "@/lib/kenh-gui";

export default function ChonKenhGuiKq({
  value,
  onChange,
}: {
  value: string;
  onChange: (kenh: string) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-label text-ink-soft">
      Đã gửi qua
      <OChon
        className="flex-1"
        aria-label="Kênh đã gửi kết quả cho khách"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {KENH_GUI_SO_CSKH.map(([ma, nhan]) => (
          <option key={ma} value={ma}>
            {nhan}
          </option>
        ))}
      </OChon>
    </label>
  );
}
