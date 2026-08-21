// Bộ nhớ tạm có HẠN GIỜ cho dữ liệu tra cứu — thứ gần như không đổi mà mọi
// trang đều hỏi lại.
//
// VÌ SAO CẦN. Đo trên staging 22/08/2026: một lần mở /customers đi ~50 vòng
// gọi PostgREST, mỗi vòng kèm nghi lễ BEGIN/set_config/COMMIT (145 trên 238
// câu SQL là nghi lễ, không phải dữ liệu). Bản thân database chỉ tốn 191ms;
// chi phí nằm ở SỐ VÒNG. Và số vòng ấy trả giá kép khi đông: dựng một trang
// tốn 53ms CPU lúc chạy một mình, nhưng 132ms khi 60 người cùng mở — phần
// chênh là chi phí tranh chấp của hàng nghìn lời hứa đang bay.
//
// `cache()` của React chỉ sống trong MỘT lượt dựng trang. Danh sách cơ sở và
// dịch vụ thì giống nhau giữa mọi lượt, mọi người — nên nhớ chúng qua nhiều
// lượt là cắt thẳng số vòng gọi.
//
// BA LUẬT BẮT BUỘC, mỗi luật chữa một kiểu hỏng riêng:
//
//   ① KHOÁ PHẢI CÓ clinic_id. Hệ này nhiều phòng khám. Một bộ nhớ tạm không
//     phân biệt phòng khám sẽ trả danh sách dịch vụ của phòng A cho phòng B —
//     kiểu rò rỉ nặng nhất mà hệ nhiều tenant có thể mắc. Hàm `nhoTheoPhongKham`
//     BẮT BUỘC nhận clinic_id, không có đường vòng.
//
//   ② CHỈ DỮ LIỆU TRA CỨU. Không nhớ lịch hẹn, ghế trống, trạng thái bệnh
//     nhân. Nói chính xác: nhớ ghế trống ĐỂ HIỂN THỊ thì được phép (trigger
//     sức chứa mới là chốt quyết lúc bấm Đặt), nhưng bộ nhớ này không có cơ
//     chế làm tươi theo sự kiện nên cứ cấm hẳn cho tới khi cần thật — một ô
//     "còn trống" quá hạn 60 giây trên màn hình là 60 giây người trực hứa
//     nhầm với khách. Danh sách cơ sở / dịch vụ thì tệ nhất là chậm vài chục
//     giây khi quản lý vừa thêm một dòng.
//
//   ③ HỎNG THÌ ĐỪNG NHỚ. Nếu hàm nạp ném lỗi hoặc trả rỗng, không ghi vào bộ
//     nhớ tạm: nhớ một danh sách rỗng suốt 60 giây là cả phòng khám nhìn thấy
//     ô chọn trống mà không hiểu vì sao.
//
// Bộ nhớ nằm TRONG TIẾN TRÌNH. Với 4 tiến trình Next thì có 4 bản, mỗi bản tự
// hết hạn — chấp nhận được vì dữ liệu chỉ-đọc và hạn ngắn; đổi sang Redis là
// việc của lúc chạy nhiều máy, không phải bây giờ.

/** Hạn mặc định. Đủ ngắn để quản lý sửa danh mục xong thấy đổi trong một phút. */
export const HAN_MAC_DINH_MS = 60_000;

interface O<T> {
  giaTri: T;
  hetHan: number;
}

const kho = new Map<string, O<unknown>>();

/**
 * Lấy dữ liệu tra cứu của MỘT phòng khám, nhớ lại trong `hanMs`.
 *
 * @param ten     tên loại dữ liệu, ví dụ "co-so" — chỉ để đọc log cho dễ
 * @param clinicId phòng khám sở hữu dữ liệu; BẮT BUỘC, xem luật ①
 * @param nap     hàm nạp thật, chỉ chạy khi chưa nhớ hoặc đã hết hạn
 */
export async function nhoTheoPhongKham<T>(
  ten: string,
  clinicId: string,
  nap: () => Promise<T>,
  hanMs: number = HAN_MAC_DINH_MS,
): Promise<T> {
  // Không có phòng khám thì KHÔNG nhớ. Thà chậm còn hơn trả nhầm dữ liệu của
  // phòng khám khác — và một khoá "undefined" dùng chung là đúng cách để nhầm.
  if (!clinicId) return nap();

  const khoa = `${ten}::${clinicId}`;
  const co = kho.get(khoa);
  if (co && co.hetHan > Date.now()) return co.giaTri as T;

  const giaTri = await nap();

  // Luật ③: rỗng hoặc hỏng thì không ghi. `null`/`undefined` cũng vậy.
  const dangNho =
    giaTri !== null &&
    giaTri !== undefined &&
    !(Array.isArray(giaTri) && giaTri.length === 0);
  if (dangNho) kho.set(khoa, { giaTri, hetHan: Date.now() + hanMs });

  return giaTri;
}

/** Quên một loại dữ liệu của một phòng khám — gọi sau khi GHI vào danh mục. */
export function quen(ten: string, clinicId: string): void {
  kho.delete(`${ten}::${clinicId}`);
}

/** Quên sạch. Chỉ dùng trong bài kiểm. */
export function quenHet(): void {
  kho.clear();
}

/** Số mục đang nhớ — cho bài kiểm và cho màn Vận hành nếu cần soi. */
export function soMucDangNho(): number {
  return kho.size;
}
