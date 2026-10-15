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
  /** Cuộc gọi này xác nhận khách sẽ đến, không chỉ ghi nhận đã liên hệ. */
  khachXacNhan?: boolean;
}

export const MOT_CHAM: Record<string, MotCham> = {
  // CÒN ĐÚNG MỘT MỤC (Tuyền chốt 16/09/2026). Dòng trạng thái mới chỉ còn các ô
  // CSKH tự làm; "Hẹn gọi lại" / "Không gọi được" ghi thẳng ở VungLamViecKhach
  // (cùng mã GOI_LAI, khác `ket_qua`). Các mục cũ đã rời bảng:
  //   · VUOT_SUC_CHUA, NHAC_HEN_MAI, SAU_SINH_1_THANG, SAU_THU_THUAT_1_NGAY — bỏ
  //     khỏi dòng trạng thái (vượt sức chứa lên khung báo dưới tên khách);
  //   · CHO_KQ_XN, CHO_BAC_SI, KQ_CHUA_GUI, DA_TRA_KQ, KHONG_FOLLOW_UP — thành ô
  //     KHOÁ (đối tác / bác sĩ / nút gửi), nên cột phải GIỮ nút ghi của nó.
  //
  // `loai` phải khớp thứ view dò để ĐÓNG nhánh: CHO_XAC_NHAN đóng bằng
  // NOT EXISTS(loai = 'XAC_NHAN_LICH') — xem `v_viec_cskh`.
  CHO_XAC_NHAN: {
    loai: "XAC_NHAN_LICH",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã gọi xác nhận lịch",
    khachXacNhan: true,
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

/** TÊN TRẠNG THÁI SAU KHI ĐÃ LÀM — cho chip ở danh sách khách hàng.
 *
 *  QUANG 10/08/2026: *"sao tôi test thì mới chỉ có đã checkin, đã khám xong là
 *  bên danh sách khách hàng mới hiện… trong khi cả cần nhắc hẹn thì không"*.
 *
 *  ĐÂY KHÔNG PHẢI LỖI ĐƯỜNG TRUYỀN — chip vẫn suy lại từ database mỗi lần đọc.
 *  Nó là LỆCH MÔ HÌNH. `v_trang_thai_cskh` trả lời "việc CÒN PHẢI LÀM", nên bấm
 *  xong một việc là việc ấy ĐÓNG và biến khỏi chip. Chỉ hai thứ trụ lại được:
 *
 *    "Đã check-in"   suy từ `appointment.status`, là TRẠNG THÁI chứ không phải
 *                    việc — nên nó không đóng
 *    "Đã khám xong"  đường lùi cuối cùng, cũng đọc `appointment.status`
 *
 *  Đo trên staging: Sen đi trọn tám bước lúc 17:19, tám dòng sổ đều ghi thật —
 *  và chip của chị ấy chỉ hiện "Đã khám xong", vì sau bước cuối chị KHÔNG CÒN
 *  việc nào mở.
 *
 *  Cách chữa không phải sửa view (nó đang trả lời đúng câu hỏi của nó) mà là
 *  thêm một tầng: hết việc thì chip nói LẦN CHẠM GẦN NHẤT. Người trực nhìn
 *  danh sách cần biết "khách này đang ở đâu", và khi không còn gì phải làm thì
 *  chỗ họ đang ở CHÍNH LÀ việc vừa xong. */
export const NHAN_DA_LAM: Record<string, string> = {
  CHO_XAC_NHAN: "Đã gọi xác nhận lịch",
  VUOT_SUC_CHUA: "Đã gọi chốt lịch vượt sức chứa",
  NHAC_HEN_MAI: "Đã gọi nhắc hẹn",
  GOI_LAI: "Đã gọi lại",
  HOI_LY_DO_HUY: "Đã hỏi lý do huỷ",
  DA_CHECKIN: "Đã check-in",
  CHO_KQ_XN: "Đã hỏi kết quả xét nghiệm",
  CHO_BAC_SI: "Đã nhắc bác sĩ duyệt",
  KQ_CHUA_GUI: "Đã gửi kết quả cho khách",
  DA_TRA_KQ: "Đã trả kết quả",
  KHONG_FOLLOW_UP: "Không cần follow up",
  SAU_SINH_1_THANG: "Đã gọi sau sinh",
  SAU_THU_THUAT_1_NGAY: "Đã gọi sau thủ thuật",
  HEN_GOI_LAI: "Đã hẹn gọi lại",
  MOI_TAI_KHAM: "Đã mời tái khám",
  NHAC_DI_KHAM: "Đã nhắc đi khám",
  QUAN_LY_DOI_GIO: "Quản lý đã đổi giờ",
};

/** Đường lùi cho những dòng ghi TRƯỚC khi có cột `trang_thai_ma`
 *  (migration 20260810000002), và cho mốc quầy vốn không mang mã trạng thái. */
export const NHAN_DA_LAM_THEO_LOAI: Record<string, string> = {
  XAC_NHAN_LICH: "Đã gọi xác nhận lịch",
  NHAC_HEN: "Đã gọi nhắc hẹn",
  CHECK_XN: "Đã hỏi kết quả xét nghiệm",
  TRA_KQ: "Đã trả kết quả",
  HOI_LY_DO_HUY: "Đã hỏi lý do huỷ",
  HOI_THAM: "Đã gọi hỏi thăm",
  CHECK_IN: "Đã check-in",
  CHECK_OUT: "Đã khám xong",
  THANH_TOAN: "Đã thanh toán",
  MUA_THUOC: "Đã mua thuốc",
  PHAN_HOI_THUOC: "Đã ghi phản hồi thuốc",
};

/** Chip cho một khách KHÔNG còn việc nào mở, dựa trên lần chạm gần nhất.
 *
 *  `null` = chưa từng có lần chạm nào, để chỗ gọi rơi tiếp về trạng thái lịch
 *  hẹn. `KHAC` cố ý không có nhãn riêng: ba trạng thái dùng chung loại ấy, đoán
 *  ở đó là nói sai tên việc vừa làm. */
export function nhanLanChamCuoi(cham: {
  trang_thai_ma?: string | null;
  loai?: string | null;
} | undefined): string | null {
  if (!cham) return null;
  const theoMa = cham.trang_thai_ma
    ? NHAN_DA_LAM[cham.trang_thai_ma]
    : undefined;
  if (theoMa) return theoMa;
  return (cham.loai && NHAN_DA_LAM_THEO_LOAI[cham.loai]) || null;
}
