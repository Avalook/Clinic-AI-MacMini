// BÁO LỖI TRÌNH DUYỆT VỀ KHO LỖI — chặn báo trùng để không tự DoS (14/10/2026).
//
// VÌ SAO. Đo prod 30 phút: `/api/loi` bị 429 mười một lần. Hai trang lỗi
// (`app/error.tsx`, `app/(dashboard)/error.tsx`) mỗi lần dựng là một lần POST. Lúc
// máy chủ quá tải, layout ném lỗi → trang lỗi → người dùng bấm "Thử lại" → dựng
// lại → lỗi lại → POST lại; mười máy cùng làm là một tràng báo giống hệt nhau đổ vào
// đúng cái máy chủ đang khổ — đường báo lỗi tự thành một nguồn tải, và bị chặn
// (429) đúng lúc kho lỗi cần nhận nhất.
//
// LUẬT.
//   - Cùng một lỗi (cùng nơi + loại + thông điệp, đã bỏ phần thay đổi theo từng lần
//     như digest, uuid, con số) CHỈ GỬI LẦN ĐẦU trong một cửa sổ `CUA_SO_MS`.
//   - Không nuốt: các lần trùng được ĐẾM, và hết cửa sổ thì gửi MỘT lần tóm tắt
//     "(lặp thêm N lần trong 5 phút)" — kho lỗi thấy cả quy mô, không chỉ lần đầu.
//   - Trần chung `TRAN_MOI_PHUT` lượt gửi mỗi phút cho mọi loại lỗi cộng lại (một
//     đợt lỗi KHÁC nhau liên tục cũng không đổ được vào máy chủ). Lượt vượt trần
//     được đếm và cộng vào lần gửi kế tiếp.
//   - Hỏng thì im: đây là đường báo lỗi, không được sinh thêm lỗi cho người dùng.

export const CUA_SO_MS = 5 * 60_000;
export const TRAN_MOI_PHUT = 6;
/** Số loại lỗi tối đa nhớ cùng lúc — chặn bộ nhớ phình khi thông điệp luôn khác. */
export const TRAN_SO_LOAI = 100;

export interface GoiLoi {
  vi_tri: string;
  kieu: string;
  thong_diep: string;
}

export interface CongBaoLoi {
  gui: (g: GoiLoi) => Promise<unknown>;
  bayGio: () => number;
  hen: (fn: () => void, ms: number) => unknown;
}

export type KetQuaBao = "gui" | "trung" | "tran";

/** Bỏ phần đổi theo từng lần để hai lần của CÙNG một lỗi ra cùng một khoá. */
export function khoaLoi(g: GoiLoi): string {
  const chuan = g.thong_diep
    .replace(/\(digest [^)]*\)/gi, "")
    .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, "#")
    .replace(/\d+/g, "#")
    .replace(/\s+/g, " ")
    .trim();
  return `${g.vi_tri}\u0000${g.kieu}\u0000${chuan}`;
}

interface Muc {
  lucDau: number;
  boQua: number;
  goi: GoiLoi;
}

export function taoBaoLoi(cong: CongBaoLoi, cuaSo: number = CUA_SO_MS) {
  const muc = new Map<string, Muc>();
  let lanGui: number[] = [];
  let tranBo = 0;

  function conChoGui(bay: number): boolean {
    lanGui = lanGui.filter((t) => bay - t < 60_000);
    return lanGui.length < TRAN_MOI_PHUT;
  }

  function guiThat(g: GoiLoi, bay: number, ghiChu: string) {
    lanGui.push(bay);
    const them = tranBo > 0 ? ` (đã bỏ qua ${tranBo} báo vượt trần)` : "";
    tranBo = 0;
    const thongDiep = `${g.thong_diep}${ghiChu}${them}`.slice(0, 1000);
    try {
      void cong.gui({ ...g, thong_diep: thongDiep }).catch(() => undefined);
    } catch {
      // Đường báo lỗi không được ném lỗi.
    }
  }

  return function bao(g: GoiLoi): KetQuaBao {
    const bay = cong.bayGio();
    const khoa = khoaLoi(g);
    const cu = muc.get(khoa);

    if (cu && bay - cu.lucDau < cuaSo) {
      cu.boQua += 1;
      // Lần trùng ĐẦU TIÊN hẹn một lần tóm tắt ở cuối cửa sổ.
      if (cu.boQua === 1) {
        cong.hen(() => {
          const m = muc.get(khoa);
          if (!m || m.boQua === 0) return;
          const n = m.boQua;
          muc.delete(khoa);
          const gio = cong.bayGio();
          if (conChoGui(gio)) {
            guiThat(m.goi, gio, ` (lặp thêm ${n} lần trong ${Math.round(cuaSo / 60_000)} phút)`);
          } else {
            tranBo += n;
          }
        }, cuaSo - (bay - cu.lucDau));
      }
      return "trung";
    }

    if (!conChoGui(bay)) {
      tranBo += 1;
      return "tran";
    }
    if (muc.size >= TRAN_SO_LOAI) muc.clear();
    muc.set(khoa, { lucDau: bay, boQua: 0, goi: g });
    guiThat(g, bay, "");
    return "gui";
  };
}

/** Bản dùng chung cho cả tab: gửi thật tới `/api/loi`. */
export const baoLoiTrinhDuyet = taoBaoLoi({
  gui: (g) =>
    fetch("/api/loi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(g),
    }),
  bayGio: () => Date.now(),
  hen: (fn, ms) => setTimeout(fn, ms),
});
