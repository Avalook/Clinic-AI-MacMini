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

  // HỎI HỎNG THÌ PHẢI NÓI RA — nhưng bằng MỘT DÒNG, không phải một cái hộp.
  //
  // Ba chặng của chỗ này, ghi lại đủ vì cả ba đều có lý:
  //
  //   08/08  hộp đỏ to, chiếm gần hết panel Đặt lịch
  //   09/08  Quang bỏ hẳn hộp ấy — nó lấn màn hình
  //   10/08  Quang: *"làm nốt cái lần trước đi"*
  //
  // Bỏ hẳn là đi quá: nhánh này KHÔNG vẽ gì, nên màn hình trông y hệt lúc khách
  // sạch lịch. Người trực đọc sự im lặng ấy thành "được, đặt đi" — đúng cái đặt
  // chồng mà khối này sinh ra để chặn, và đúng ca `ad87caf` (Lan đặt ba lần một
  // buổi). Cái sai là KÍCH THƯỚC, không phải sự tồn tại.
  //
  // Nay: một dòng cùng cỡ với hai nhánh kia, `role="alert"` để trình đọc màn
  // hình đọc lên ngay thay vì đợi người dùng rà tới. Không có nút, không chiếm
  // chỗ — chỉ đủ để người ta biết mình đang KHÔNG có thông tin, khác hẳn với
  // biết rằng khách sạch lịch.
  //
  // Nguyên nhân gốc vẫn còn: `/api/appointments` thỉnh thoảng trả không-ok cho
  // khách đang chọn. Dòng này không chữa nó, chỉ thôi giấu nó đi.
  if (tra.kind === "hong") {
    return (
      <p
        role="alert"
        className="rounded-xl border border-danger/40 bg-danger-bg px-3 py-2 text-[11px] font-medium text-danger"
      >
        Chưa kiểm được lịch cũ của khách — đừng coi là khách chưa có lịch. Thử
        chọn lại khách; còn lỗi thì kiểm ở màn Quản lý khách hàng trước khi đặt.
      </p>
    );
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
