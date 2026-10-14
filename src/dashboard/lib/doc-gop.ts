// MỘT LƯỢT ĐỌC MỘT LÚC CHO MỖI ĐƯỜNG DẪN — gộp các lượt hỏi lại chồng nhau.
//
// VÌ SAO (đo prod 14/10/2026, 30 phút, ~14 request/giây). `/api/luot-kham` bị gọi
// 3.557 lần, `/api/phieu-kham` 2.400 lần. Một tin `visit`/`service_order` làm hàng
// chục chỗ trên cùng màn Bàn khám hỏi lại; tin tới lệch nhau vài trăm ms nên nhịp
// gộp ở `useNgheBang` không gộp hết, và lượt trước CHƯA XONG đã có lượt sau. Mỗi
// lượt là một truy vấn thật trên một VPS 4 nhân.
//
// LUẬT (cùng tinh thần `lib/mot-luot`, nhưng THEO TỪNG ĐƯỜNG DẪN và CHIA SẺ kết quả):
//   - Chưa có lượt nào đang bay cho `khoa` → chạy ngay.
//   - Có lượt vừa mới bắt đầu (≤ `CUA_SO_CHUNG_MS`, tức cùng một đợt dựng màn) →
//     dùng chung kết quả của nó. Hai chỗ trong một màn cùng đọc một đường dẫn lúc
//     mở màn chỉ tốn một lượt.
//   - Có lượt đang bay từ lâu hơn → KHÔNG dùng chung kết quả của nó (nó có thể đã
//     đọc TRƯỚC thay đổi vừa xảy ra, và người gọi chính là vì thay đổi ấy mà hỏi).
//     Xếp đúng MỘT lượt chạy ngay sau khi lượt đang bay xong; mọi người gọi chen
//     vào trong lúc ấy cùng nhận kết quả của lượt nối đuôi này.
// Nên không bao giờ quá HAI lượt cho một đường dẫn tại một thời điểm, và không ai
// nhận dữ liệu cũ hơn lúc mình gọi.
//
// Kết quả được CHIA SẺ nguyên tham chiếu cho nhiều người gọi: ai nhận cũng phải
// coi nó là chỉ-đọc (đặt vào state, lọc/map ra mảng mới — không `.sort()` tại chỗ).

/** Hai lần gọi cách nhau không quá ngần này là CÙNG một đợt dựng màn. */
export const CUA_SO_CHUNG_MS = 50;

export type GopDoc = <T>(khoa: string, chay: () => Promise<T>) => Promise<T>;

interface Muc {
  dang: Promise<unknown>;
  batDau: number;
  sau: Promise<unknown> | null;
}

/** Một sổ riêng. Dùng chung thì lấy `gopDoc` bên dưới; test tạo sổ mới. */
export function taoGopDoc(bayGio: () => number = Date.now): GopDoc {
  const bay = new Map<string, Muc>();

  function chayMoi<T>(khoa: string, chay: () => Promise<T>): Promise<T> {
    // `async` bọc để một hàm ném đồng bộ cũng thành lời hứa bị từ chối, không
    // làm sổ kẹt một mục không bao giờ xoá.
    const p = (async () => chay())();
    const muc: Muc = { dang: p, batDau: bayGio(), sau: null };
    bay.set(khoa, muc);
    const xong = () => {
      if (bay.get(khoa) === muc) bay.delete(khoa);
    };
    p.then(xong, xong);
    return p;
  }

  return <T>(khoa: string, chay: () => Promise<T>): Promise<T> => {
    const muc = bay.get(khoa);
    if (!muc) return chayMoi(khoa, chay);
    if (bayGio() - muc.batDau <= CUA_SO_CHUNG_MS) return muc.dang as Promise<T>;
    // `xong` (đăng ký trong chayMoi, TRƯỚC dòng này) đã xoá mục cũ khi `dang` xong,
    // nên `chayMoi` ở đây tạo mục mới sạch.
    muc.sau ??= muc.dang
      .then(
        () => undefined,
        () => undefined,
      )
      .then(() => chayMoi(khoa, chay));
    return muc.sau as Promise<T>;
  };
}

/** Sổ dùng chung cho cả tab trình duyệt. */
export const gopDoc: GopDoc = taoGopDoc();
