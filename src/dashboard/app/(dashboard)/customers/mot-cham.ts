// MỘT CHẠM LÀ XONG — danh mục dùng chung cho CẢ HAI CỘT.
//
// QUANG 10/08/2026: *"ấn vào làm ngay là nó tick xanh luôn, vì nút làm ngay
// chính là action"*, và liệt kê đủ chín trạng thái phải như thế.
//
// VÌ SAO NÓ Ở FILE RIÊNG. Cột giữa cần bảng này để BẤM LÀ GHI; cột phải cần nó
// để BỎ ĐI cái nút ghi trùng — *"bỏ ô đã xác nhận cuộc gọi vì bên kia ấn là
// được rồi mà"*. Hai câu hỏi ngược nhau trên cùng một danh sách: để mỗi bên tự
// giữ một bản là sớm muộn một trạng thái vừa ghi được ở cột giữa vừa còn nút ở
// cột phải, tức người trực ghi hai dòng cho một cuộc gọi.
//
// Đây cũng là bản danh mục thứ N của mã trạng thái CSKH; `cskh-trang-thai-drift`
// canh nó cùng với các bản kia.

/** Một thao tác ghi thẳng vào sổ, không qua khối bên phải. */
export interface MotCham {
  /** `loai` gửi lên backend — phải nằm trong `LOAI_HOP_LE`. */
  loai: string;
  /** `ket_qua` gửi lên backend — phải nằm trong `KET_QUA_HOP_LE`. */
  ketQua: string;
  /** Nội dung mặc định ghi vào sổ khi người dùng không gõ ghi chú nào. */
  noiDung: string;
}

export const MOT_CHAM: Record<string, MotCham> = {
  // ── TRƯỚC KHÁM ────────────────────────────────────────────────────────────
  // Hai mã này trước 10/08/2026 phải đi qua khối bên phải mới ghi được. Nhưng
  // "đã gọi xác nhận lịch" là TOÀN BỘ nội dung của lần chạm ấy — bắt bấm nút
  // thứ hai ở một cột khác là hai thao tác cho một sự thật.
  //
  // `loai` phải khớp đúng thứ view dò để ĐÓNG nhánh, nếu không node tích xanh
  // mà chip bên trái đứng im:
  //   CHO_XAC_NHAN đóng bằng NOT EXISTS(loai = 'XAC_NHAN_LICH')
  //   NHAC_HEN_MAI đóng bằng NOT EXISTS(loai = 'NHAC_HEN')
  // (xem `v_viec_cskh`, migration 20260810000008).
  CHO_XAC_NHAN: {
    loai: "XAC_NHAN_LICH",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã gọi xác nhận lịch",
  },
  NHAC_HEN_MAI: {
    loai: "NHAC_HEN",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã gọi nhắc hẹn",
  },

  // ── SAU KHÁM ──────────────────────────────────────────────────────────────
  DA_CHECKIN: {
    loai: "CHECK_IN",
    ketQua: "GHI_NHAN",
    noiDung: "Khách đã tới quầy",
  },
  CHO_KQ_XN: {
    loai: "CHECK_XN",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã hỏi đơn vị xét nghiệm",
  },
  CHO_BAC_SI: {
    loai: "KHAC",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã hỏi bác sĩ về kết quả",
  },
  KQ_CHUA_GUI: {
    loai: "TRA_KQ",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã gửi kết quả cho bệnh nhân",
  },
  DA_TRA_KQ: {
    loai: "TRA_KQ",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã gọi trả kết quả xét nghiệm",
  },

  // ── BA VIỆC THEO DÕI SAU ──────────────────────────────────────────────────
  // Cả ba vẫn mang nhãn "tự chọn" ở cột giữa — hệ thống không có nguồn dữ liệu
  // để tự biết (không có ngày sinh con thật, dịch vụ thủ thuật đang tắt). "Tự
  // chọn" nói về việc AI QUYẾT, không nói về việc bấm mấy lần.
  //
  // `KHONG_FOLLOW_UP` Quang không nhắc tên, nhưng nó nằm cùng hàng với hai cái
  // kia và cùng bản chất: một quyết định ghi lại để ca sau khỏi gọi. Để một nút
  // trong hàng hành xử khác hai nút cạnh nó là thứ người dùng sẽ vấp ngay.
  //
  // ⚠️ `BO_QUA` BẮT BUỘC đi cùng kênh `KHONG_LIEN_HE` — backend kiểm
  // (`tuong_tac_cskh_service.ghi`) và database cũng có CHECK
  // `tuong_tac_bo_qua_thi_khong_lien_he`. Xem `kenhCho()` bên dưới.
  KHONG_FOLLOW_UP: {
    loai: "KHAC",
    ketQua: "BO_QUA",
    noiDung: "Không cần follow up sau thủ thuật",
  },
  SAU_SINH_1_THANG: {
    loai: "HOI_THAM",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã gọi chúc mừng đầy tháng",
  },
  SAU_THU_THUAT_1_NGAY: {
    loai: "HOI_THAM",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã gọi hỏi thăm sau thủ thuật",
  },
};

/** Trạng thái này ghi được chỉ bằng MỘT cú bấm ở cột giữa.
 *
 *  Cột phải đọc hàm này để BỎ nút ghi của mình đi — hai nút ghi cùng một việc
 *  là hai dòng sổ cho một cuộc gọi. */
export function laMotCham(ma: string | null | undefined): boolean {
  return Boolean(ma && ma in MOT_CHAM);
}

/** Kênh liên hệ đúng với một `ket_qua`.
 *
 *  BA LUẬT CHÉO CỦA BACKEND, viết ra ở đây vì gửi sai là 422 mà câu lỗi thì nằm
 *  tận `tuong_tac_cskh_service`:
 *
 *    BO_QUA   ⟺ KHONG_LIEN_HE   ("bỏ qua" là KHÔNG gọi ai cả)
 *    GHI_NHAN ⟺ TRUC_TIEP       (mốc tại quầy là việc XẢY RA, không phải cuộc gọi)
 *    còn lại  →  GOI
 *
 *  Nút "Ghi nhận: không cần gọi" từng gửi cứng `GOI` cho `BO_QUA` và vì thế
 *  CHƯA TỪNG ghi được lần nào — bấm là hiện dòng đỏ, và bước trên timeline
 *  không bao giờ tích xanh. */
export function kenhCho(ketQua: string): string {
  if (ketQua === "BO_QUA") return "KHONG_LIEN_HE";
  if (ketQua === "GHI_NHAN") return "TRUC_TIEP";
  return "GOI";
}
