// Mã riêng của MỘT TAB, để hai tab không giẫm lên bản nháp của nhau.
//
// VÌ SAO CẦN. `localStorage` dùng chung cho mọi tab cùng tên miền. Bản nháp của
// màn bệnh án khoá theo lượt khám (`…:phieu-kham:<id lượt>`) nên hai tab mở hai
// bệnh nhân khác nhau không đụng nhau — đúng. Nhưng form KHÁCH MỚI chưa có id
// nào để khoá theo, và nó đang dùng chữ "form" cố định:
//
//     clinicai:nhap:<staff>:khach-moi:form
//
// Lễ tân mở hai tab cùng nhập hai khách (chuyện thường ở quầy: một người đang
// gọi điện, một người đứng trước mặt) thì tab gõ sau ghi đè bản nháp của tab
// gõ trước, và người kia F5 một cái là nhận về thông tin của khách không phải
// của mình. Đây là kiểu lỗi tệ nhất: dữ liệu SAI chứ không phải dữ liệu MẤT.
//
// VÌ SAO `sessionStorage`. Nó là kho DUY NHẤT riêng cho từng tab; localStorage
// và cookie đều dùng chung. Mã sống đúng bằng đời tab: mở tab mới là mã mới,
// tải lại trang thì giữ nguyên — nên F5 vẫn khôi phục được bản nháp của chính
// tab ấy, đúng mục đích ban đầu của việc lưu nháp.
//
// KHÔNG DÙNG MÃ NÀY CHO DANH TÍNH. Nó chỉ để tách chỗ cất nháp. Phiên đăng nhập
// vẫn nằm ở cookie và do máy chủ xác minh; một chuỗi ngẫu nhiên trình duyệt tự
// đặt thì không chứng minh được gì cả.

const KHOA = "clinicai:ma-tab";

/** Mã của tab hiện tại. Máy chủ (SSR) không có tab nào → trả chuỗi rỗng. */
export function maTab(): string {
  if (typeof window === "undefined") return "";
  try {
    let ma = window.sessionStorage.getItem(KHOA);
    if (!ma) {
      // randomUUID chỉ có trong ngữ cảnh bảo mật; staging/prod chạy HTTP thường
      // nên KHÔNG được coi là luôn có (xem memory "http thường không phải
      // secure context"). Rơi về một chuỗi ngẫu nhiên đủ dùng.
      ma =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
      window.sessionStorage.setItem(KHOA, ma);
    }
    return ma;
  } catch {
    // Trình duyệt chặn kho (chế độ riêng tư, chính sách máy trạm) → không có mã
    // riêng. Lúc ấy hành vi đúng bằng hành vi cũ: chung một chỗ cất nháp.
    return "";
  }
}
