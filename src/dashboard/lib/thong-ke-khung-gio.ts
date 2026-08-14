// Gom lịch hẹn theo MỐC KHUNG GIỜ và đếm khám mới / khám cũ / dịch vụ.
//
// Tuyền 14/08/2026: *"cần thống kê số slot theo từng mốc khung h và phân ra
// theo khám mới, khám cũ & dịch vụ"*.
//
// Tách khỏi màn hình để kiểm được bằng `node --test`: đây là phép ĐẾM, và một
// phép đếm sai trên bảng quản lý thì không ai phát hiện được bằng mắt — nó chỉ
// ra một con số hơi khác, và người đọc tin nó.

// Đuôi `.ts` là CÓ CHỦ Ý: `node --test` phân giải module theo chuẩn ESM nên
// cần đuôi thật, còn tsconfig đã bật `allowImportingTsExtensions`. Thiếu nó thì
// phần đếm này không kiểm được bằng test — và đây đúng là phần cần kiểm nhất.
import { laKhamCu, laKhamMoi } from "./phan-loai-kham.ts";
import { VN_TZ } from "./datetime.ts";

/** Trạng thái KHÔNG chiếm chỗ — cùng danh sách với slot-capacity và backend. */
const TRANG_THAI_CHET = new Set(["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"]);

export interface LichDeDem {
  slot_start: string;
  status: string;
  phan_loai: string;
  service?: { name: string } | null;
}

export interface DongKhungGio {
  /** "07:00" — giờ Việt Nam. */
  khung: string;
  tong: number;
  khamMoi: number;
  khamCu: number;
  /** Chưa suy ra được mới/cũ. Hiện ra thành cột riêng chứ không gộp vào "cũ". */
  chuaRo: number;
  /** Tên dịch vụ → số lịch, đã xếp giảm dần. */
  dichVu: { ten: string; so: number }[];
}

/** Giờ:phút theo múi giờ Việt Nam. Trả "" nếu chuỗi giờ hỏng — KHÔNG ném:
 *  một dòng dữ liệu xấu không được làm trắng cả bảng thống kê. */
export function khungGioVN(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("vi-VN", {
    timeZone: VN_TZ,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function thongKeTheoKhungGio(items: LichDeDem[]): DongKhungGio[] {
  const theoKhung = new Map<
    string,
    { tong: number; moi: number; cu: number; chuaRo: number; dv: Map<string, number> }
  >();

  for (const a of items) {
    // LỊCH ĐÃ HUỶ KHÔNG ĐƯỢC ĐẾM. Bảng này trả lời "khung nào đang kín" — một
    // lịch huỷ không giữ chỗ của ai, và đếm nó vào là báo đầy chỗ còn trống.
    if (TRANG_THAI_CHET.has(a.status)) continue;
    const khung = khungGioVN(a.slot_start);
    if (!khung) continue;

    let o = theoKhung.get(khung);
    if (!o) {
      o = { tong: 0, moi: 0, cu: 0, chuaRo: 0, dv: new Map() };
      theoKhung.set(khung, o);
    }
    o.tong += 1;
    if (laKhamMoi(a.phan_loai)) o.moi += 1;
    else if (laKhamCu(a.phan_loai)) o.cu += 1;
    else o.chuaRo += 1;

    const ten = a.service?.name?.trim() || "(chưa chọn dịch vụ)";
    o.dv.set(ten, (o.dv.get(ten) ?? 0) + 1);
  }

  return [...theoKhung.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([khung, o]) => ({
      khung,
      tong: o.tong,
      khamMoi: o.moi,
      khamCu: o.cu,
      chuaRo: o.chuaRo,
      dichVu: [...o.dv.entries()]
        .map(([ten, so]) => ({ ten, so }))
        .sort((x, y) => y.so - x.so || x.ten.localeCompare(y.ten)),
    }));
}

/** Cộng dồn cả kỳ — dòng "Tổng" dưới bảng. Cộng LẠI TỪ ĐẦU chứ không cộng các
 *  dòng đã gom: gom rồi cộng thì một lỗi ở bước gom được nhân lên chứ không lộ
 *  ra. */
export function tongKet(items: LichDeDem[]): Omit<DongKhungGio, "khung"> {
  const dong = thongKeTheoKhungGio(items);
  const dv = new Map<string, number>();
  for (const d of dong) for (const x of d.dichVu) dv.set(x.ten, (dv.get(x.ten) ?? 0) + x.so);
  return {
    tong: dong.reduce((s, d) => s + d.tong, 0),
    khamMoi: dong.reduce((s, d) => s + d.khamMoi, 0),
    khamCu: dong.reduce((s, d) => s + d.khamCu, 0),
    chuaRo: dong.reduce((s, d) => s + d.chuaRo, 0),
    dichVu: [...dv.entries()]
      .map(([ten, so]) => ({ ten, so }))
      .sort((x, y) => y.so - x.so || x.ten.localeCompare(y.ten)),
  };
}
