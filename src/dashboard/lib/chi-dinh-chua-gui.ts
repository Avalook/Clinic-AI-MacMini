/**
 * Chỉ định đã TICK nhưng CHƯA GỬI (14/10/2026, bấm thật trên staging).
 *
 * Ở khối 2 "Chỉ định cận lâm sàng" bác sĩ tick dịch vụ rồi phải bấm thêm nút
 * "Chỉ định N mục" mới có chỉ định thật. Bấm [Hoàn tất] khi chưa bấm nút ấy thì
 * tick biến mất, khách sang quầy thu không có chỉ định nào — không ai báo gì.
 * Màn đọc cổng này để CHẶN Hoàn tất / chuyển khách và hỏi lại tại chỗ.
 *
 * Hàm thuần — không luật nghiệp vụ: chỉ nói "còn N mục chưa gửi" và gọi lại
 * đúng hàm gửi / bỏ chọn của khối 2; máy chủ vẫn kiểm mọi chỉ định như cũ.
 */

export interface ChiDinhChuaGui {
  /** Số mục đang tick, chưa gửi. */
  soMuc: number;
  /** Gửi chỉ định ngay (cùng nút "Chỉ định N mục"). true = đã gửi xong. */
  guiNgay: () => Promise<boolean>;
  /** Bỏ hết tick (không gửi gì). */
  boChon: () => void;
}

/** Có mục tick chưa gửi không (kiểu hẹp để dùng `.soMuc` / `.guiNgay`). */
export function conChiDinhChuaGui(
  chua: ChiDinhChuaGui | null | undefined,
): chua is ChiDinhChuaGui {
  return Boolean(chua) && (chua?.soMuc ?? 0) > 0;
}

/** Câu hỏi trung tính (không vàng-đỏ: tick chưa gửi là việc bình thường). */
export function cauChiDinhChuaGui(soMuc: number): string {
  return `Còn ${soMuc} mục đã chọn chưa gửi chỉ định — bấm “Chỉ định ${soMuc} mục” hoặc bỏ tick.`;
}

/**
 * Gộp nhiều khối cùng một phiếu (danh mục cận lâm sàng + danh mục thủ thuật):
 * cộng số mục, gửi lần lượt, bỏ chọn cả hai. Không có khối nào còn tick → null.
 */
export function gopChiDinhChuaGui(
  ds: ReadonlyArray<ChiDinhChuaGui | null | undefined>,
): ChiDinhChuaGui | null {
  const con = ds.filter(conChiDinhChuaGui);
  if (con.length === 0) return null;
  return {
    soMuc: con.reduce((t, c) => t + c.soMuc, 0),
    guiNgay: async () => {
      // Lần lượt, dừng ở khối đầu tiên gửi hỏng — không gửi nửa chừng rồi báo xong.
      for (const c of con) {
        if (!(await c.guiNgay())) return false;
      }
      return true;
    },
    boChon: () => {
      for (const c of con) c.boChon();
    },
  };
}

/**
 * [Chỉ định ngay rồi …]: gửi chỉ định trước; chỉ khi gửi xong mới chạy bước kế
 * (Hoàn tất / chuyển khách). Gửi hỏng → không làm bước kế, tick vẫn còn.
 */
export async function guiRoiTiep(
  chua: ChiDinhChuaGui,
  tiep: () => void | Promise<void>,
): Promise<boolean> {
  const xong = await chua.guiNgay();
  if (!xong) return false;
  await tiep();
  return true;
}
