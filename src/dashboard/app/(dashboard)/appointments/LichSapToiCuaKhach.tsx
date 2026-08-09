// "Khách này đã có lịch gì" — khối cảnh báo đặt trùng ở panel Đặt lịch.
//
// Quang 09/08/2026: *"không có hiện thông báo đó thì đặt vô tội vạ quá, lịch
// sau lại chồng lên lịch trước"*.
//
// KHÔNG CÓ CẢNH BÁO KHÔNG ĐƯỢC ĐỒNG NGHĨA VỚI "KHÁCH CHƯA CÓ LỊCH".
//
// Đó là lý do khối này có bốn trạng thái chứ không phải một. Bản đầu chỉ vẽ khi
// `length > 0`: lượt hỏi hỏng (mất mạng, 401 vì phiên hết hạn, 500) thì màn hình
// trông y hệt lúc khách sạch lịch — im lặng, không dấu hiệu nào. Người trực ca
// đọc sự im lặng ấy thành "được, đặt đi", và đó đúng là cái đặt chồng mà khối
// này sinh ra để chặn.
//
// Nên: hỏi xong mà không có lịch thì NÓI RA là đã kiểm; hỏi hỏng thì NÓI RA là
// chưa kiểm được. Hai câu khác nhau, và người đọc phân biệt được.

import { fmtDayTime } from "@/lib/datetime";

export interface LichCu {
  id: string;
  slot_start: string;
  status: string;
  doctor_id: string | null;
  service_type_id: string | null;
}

export type TrangThaiTra =
  /** Chưa hỏi xong (đang tải, hoặc chưa chọn khách). */
  | { kind: "dang-hoi" }
  /** Hỏi xong. `items` rỗng = khách chưa có lịch nào sắp tới. */
  | { kind: "xong"; items: LichCu[] }
  /** Hỏi hỏng — KHÔNG được im lặng. */
  | { kind: "hong" };

export default function LichSapToiCuaKhach({
  tra,
  tenDichVu,
  tenBacSi,
}: {
  tra: TrangThaiTra;
  /** id dịch vụ → tên. Không tra được thì trả "". */
  tenDichVu: (id: string | null) => string;
  /** id bác sĩ → tên. Không tra được thì trả "". */
  tenBacSi: (id: string | null) => string;
}) {
  if (tra.kind === "dang-hoi") {
    return (
      <p className="rounded-xl border border-line bg-surface-muted px-3 py-2 text-[11px] text-ink-muted">
        Đang xem khách này đã có lịch nào chưa…
      </p>
    );
  }

  // HỘP ĐỎ "Chưa kiểm được lịch cũ của khách" ĐÃ BỎ — Quang chốt 09/08/2026,
  // sau khi nó chiếm gần hết panel trong lúc thử màn Đặt lịch.
  //
  // ĐÁNH ĐỔI, GHI RA ĐÂY VÌ NÓ NGƯỢC VỚI GHI CHÚ ĐẦU FILE. Nhánh này là lượt
  // hỏi HỎNG, và giờ nó không vẽ gì — tức màn hình lại trông y hệt lúc khách
  // sạch lịch. Cái im lặng ấy chính là thứ khối này sinh ra để chặn.
  //
  // Thứ THẬT SỰ phải sửa là lý do lượt hỏi hỏng (`/api/appointments` trả về
  // không-ok cho khách đang chọn), không phải cái hộp báo rằng nó hỏng. Bỏ hộp
  // đi thì lỗi vẫn còn, chỉ là không ai thấy nữa.
  if (tra.kind === "hong") {
    return null;
  }

  if (tra.items.length === 0) {
    return (
      <p className="rounded-xl border border-line bg-surface-muted px-3 py-2 text-[11px] text-ink-muted">
        Đã kiểm: khách chưa có lịch nào sắp tới.
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-warning/40 bg-warning-bg p-3 text-xs">
      <div className="font-bold text-warning">
        Khách này đã có {tra.items.length} lịch sắp tới
      </div>
      <ul className="mt-1.5 space-y-1 text-ink">
        {tra.items.map((l) => (
          <li key={l.id} className="leading-snug">
            <b>{fmtDayTime(l.slot_start)}</b>
            {" · "}
            {tenDichVu(l.service_type_id) || "—"}
            {" · "}
            {tenBacSi(l.doctor_id) || "Chưa phân bác sĩ"}
          </li>
        ))}
      </ul>
      <p className="mt-1.5 text-[11px] text-ink-muted">
        Đặt thêm vẫn được — đây chỉ là để bạn biết trước.
      </p>
    </div>
  );
}
