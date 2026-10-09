// MỘT LƯỢT TẢI MỘT LÚC — cho màn tự fetch và nghe sự kiện (`useNgheBang`).
//
// VÌ SAO (đo staging 09/10/2026). Một lần thu tiền đụng nhiều bảng; tin tới
// lệch nhau vài giây (worker sự kiện xếp phòng sau khi thu), nên nhịp gộp 250ms
// không gộp hết. Mỗi tin bắn một lượt tải mới trong khi lượt trước CHƯA XONG —
// log ghi ba lượt `/api/cashier` cùng một giây, ba lần liên tiếp, và chính ba
// truy vấn song song ấy đẩy DB staging tới OOM.
//
// LUẬT: đang có lượt chạy thì không mở lượt mới, chỉ GHI LẠI việc cần chạy;
// lượt đang chạy xong thì chạy đúng MỘT lượt nữa bằng việc ghi lại SAU CÙNG
// (bao nhiêu lần gọi chen vào cũng gộp thành một). Việc sau cùng, không phải
// việc đầu: đổi ngày / quầy giữa chừng thì lượt tải lại đọc đúng ngày đang xem.
// Không bỏ lượt chen vào — bỏ thì dữ liệu đổi trong lúc đang tải sẽ không bao
// giờ hiện ra.
//
// Người gọi `await` nhận lời hứa xong cả lượt tải lại, nên chỗ "gửi lệnh rồi
// tải lại" vẫn thấy dữ liệu SAU lệnh của mình.

export type MotLuot = (chay: () => Promise<void>) => Promise<void>;

export function taoMotLuot(): MotLuot {
  let dang: Promise<void> | null = null;
  let sau: (() => Promise<void>) | null = null;

  return (chay) => {
    sau = chay;
    if (dang) return dang;
    dang = (async () => {
      try {
        while (sau) {
          const viec = sau;
          sau = null;
          await viec();
        }
      } finally {
        dang = null;
        sau = null;
      }
    })();
    return dang;
  };
}
