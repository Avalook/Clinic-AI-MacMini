// Tên hiển thị của NHÂN VIÊN — một cái tên, đọc được, không lặp chức danh.
//
// VẤN ĐỀ NẰM Ở DỮ LIỆU. `staff.full_name` trên prod được nạp thành chuỗi ghép:
//
//     "Bác sĩ · BSNT. Lê Thiệu Quyết"
//     "Bác sĩ siêu âm · BS. Nguyễn Thành Đạt"
//     "Bác sĩ · TS.BS. Phan Chí Thành"
//
// Tức là chức danh ĐẦY ĐỦ, rồi dấu chấm giữa, rồi lại viết tắt của chính chức
// danh ấy, rồi mới tới tên. Màn hình in nguyên chuỗi ra nên người đọc thấy chữ
// "bác sĩ" hai lần và một cụm viết tắt chỉ người trong ngành hiểu.
//
// Quang chốt 09/08/2026: *"tên cứ bị trùng là sao… Bác sĩ siêu âm Nguyễn…,
// Bác sĩ nội tiết Hoàng Đình Thiệp, Bác sĩ Phan Chí Thành, Điều dưỡng Diễm
// Thuý, Trợ lý Duy Nam — chứ đừng để viết tắt xong trùng như kia nữa"*.
//
// LUẬT: phần TRƯỚC dấu "·" là chức danh và nó nói đúng; phần sau là viết tắt +
// tên. Nên bỏ viết tắt đi, giữ chức danh, ghép lại.
//
// SỬA Ở TẦNG HIỂN THỊ, KHÔNG SỬA DỮ LIỆU. `full_name` còn được dùng ở phiếu
// khám, chữ ký và bản in; sửa hàng loạt là một việc riêng cần đối chiếu từng
// người. Ô "Họ và tên" trong màn Quản lý nhân sự vẫn hiện giá trị THẬT đang lưu
// — nó là ô để sửa dữ liệu, không phải chỗ trình bày.

/** Viết tắt học hàm / chức danh đứng trước tên. Dài trước ngắn: "BSCKII" phải
 *  khớp trước "BS", nếu không "BS" ăn mất hai ký tự đầu và để lại "CKII". */
const VIET_TAT =
  "(?:GS|PGS|BSCKI{1,3}|BSNT|BSSA|BSCK|TS|Th\\.?S|ThS|BS|CN|DS|ĐD|TL)";

/** Cụm viết tắt ở ĐẦU chuỗi, nối nhau bằng dấu chấm hoặc khoảng trắng:
 *  "TS.BS. ", "Ths.BS. ", "BSNT. ", "BS. " */
const CUM_VIET_TAT = new RegExp(`^(?:${VIET_TAT}\\s*\\.?\\s*)+`, "i");

/** Viết tắt chuyên khoa → chữ đầy đủ, CHỈ dùng khi chức danh đứng trước còn
 *  chung chung ("Bác sĩ"). Chuỗi "Bác sĩ siêu âm · BSNT. Nguyễn Hữu Giáp" thì
 *  phần trước dấu chấm giữa đã nói rõ chuyên khoa rồi — tin nó, đừng ghi đè. */
const CHUYEN_KHOA: Record<string, string> = {
  BSNT: "Bác sĩ nội tiết",
  BSSA: "Bác sĩ siêu âm",
};

/** Tên người để HIỂN THỊ: "<Chức danh> <Tên riêng>", không lặp, không viết tắt.
 *
 *  Rỗng → "" (nơi gọi tự quyết "Chưa phân bác sĩ" / "—"). */
export function doctorName(raw: string | null | undefined): string {
  const goc = (raw ?? "").trim();
  if (!goc) return "";

  // Tách ở dấu chấm giữa (· hoặc -) NẾU có: trái = chức danh, phải = tên.
  const tach = goc.split(/\s*[·•]\s*/);
  let chucDanh = tach.length > 1 ? tach[0].trim() : "";
  let phanConLai = (tach.length > 1 ? tach.slice(1).join(" ") : goc).trim();

  // Viết tắt đứng đầu phần tên: nhớ lại nó là gì rồi cắt đi.
  const khop = phanConLai.match(CUM_VIET_TAT);
  if (khop) {
    const cum = khop[0].toUpperCase().replace(/[^A-ZĐ]/g, "");
    phanConLai = phanConLai.slice(khop[0].length).trim();
    // Chức danh còn chung chung mà viết tắt nói rõ chuyên khoa → dùng cái rõ hơn.
    if ((!chucDanh || chucDanh === "Bác sĩ") && CHUYEN_KHOA[cum]) {
      chucDanh = CHUYEN_KHOA[cum];
    }
  }

  if (!phanConLai) return chucDanh || goc;
  // Không có chức danh nào ở đầu (tên trần, nhập tay) → mặc định "Bác sĩ".
  // Đây là danh sách bác sĩ đặt lịch; ai không phải bác sĩ thì chuỗi gốc đã
  // mang sẵn chức danh của họ ("Điều dưỡng · …", "Trợ lý · …").
  return `${chucDanh || "Bác sĩ"} ${phanConLai}`.replace(/\s+/g, " ").trim();
}
