// Luật soát giờ ca ở TRÌNH DUYỆT — bản song song của
// `core/shifts.kiem_cau_hinh_ca`, để nói sớm ngay lúc gõ.
//
// CÓ HAI BẢN LÀ CÓ CHỦ Ý, và đây là ngoại lệ hiếm. Bình thường một luật hai bản
// là hai cơ hội để lệch nhau (xem giờ đóng cửa từng lệch 22:00/23:00 giữa hai
// file). Nhưng cảnh báo phải hiện lúc GÕ, mà gọi máy chủ sau mỗi phím là không
// làm được. Bù lại: máy chủ vẫn là chốt cuối và câu của nó mới là câu được
// hiện khi bấm Lưu, nên bản này sai theo hướng "báo thiếu" thì máy chủ vẫn
// chặn — chỉ mất một lần bấm.
//
// Tách khỏi file .tsx để `node --test` đọc được: bài kiểm không chạy được là
// bài kiểm không tồn tại.

export const CAC_CA = ["SANG", "CHIEU", "TOI"] as const;
export type MaCa = (typeof CAC_CA)[number];
export const NHAN: Record<MaCa, string> = {
  SANG: "Ca sáng",
  CHIEU: "Ca chiều",
  TOI: "Ca tối",
};
const NHAN_THU: Record<string, string> = {
  "0": "Chủ nhật",
  "1": "Thứ Hai",
  "2": "Thứ Ba",
  "3": "Thứ Tư",
  "4": "Thứ Năm",
  "5": "Thứ Sáu",
  "6": "Thứ Bảy",
};

export type Khung = { bat_dau: string; ket_thuc: string };
export type GioMoCua = Record<string, { mo: string; dong: string }>;

export function phut(hhmm: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm.trim());
  if (!m) return null;
  const g = Number(m[1]);
  const p = Number(m[2]);
  if (g < 0 || g > 24 || p < 0 || p > 59) return null;
  return g * 60 + p;
}

/** Cùng luật với `core/shifts.kiem_cau_hinh_ca`, để nói sớm. Máy chủ vẫn chốt. */
export function soatLoi(ca: Record<MaCa, Khung>, gio: GioMoCua): string[] {
  const loi: string[] = [];
  const p: Partial<Record<MaCa, [number, number]>> = {};

  for (const ma of CAC_CA) {
    const lo = phut(ca[ma].bat_dau);
    const hi = phut(ca[ma].ket_thuc);
    if (lo === null || hi === null) {
      loi.push(`${NHAN[ma]}: giờ phải dạng HH:MM.`);
      continue;
    }
    if (hi <= lo) {
      loi.push(`${NHAN[ma]}: giờ kết thúc phải sau giờ bắt đầu.`);
      continue;
    }
    p[ma] = [lo, hi];
  }

  const co = CAC_CA.filter((m) => p[m]).map((m) => [m, p[m]!] as const);
  for (let i = 1; i < co.length; i++) {
    const [maTruoc, [, hiTruoc]] = co[i - 1]!;
    const [maSau, [loSau]] = co[i]!;
    if (loSau < hiTruoc) {
      loi.push(
        `${NHAN[maSau]} bắt đầu trước khi ${NHAN[maTruoc]} kết thúc — ` +
          "hai ca chồng nhau thì KPI theo ca đếm đôi.",
      );
    }
  }

  for (const [thu, { mo, dong }] of Object.entries(gio)) {
    const lo = phut(mo ?? "");
    const hi = phut(dong ?? "");
    if (lo === null || hi === null) continue;
    for (const ma of CAC_CA) {
      const w = p[ma];
      if (!w) continue;
      if (w[0] < lo || w[1] > hi) {
        loi.push(
          `${NHAN_THU[thu] ?? `thứ ${thu}`} mở cửa ${mo}–${dong}, không chứa ` +
            `hết ${NHAN[ma]} — để nguyên thì ca bị cắt mà không báo gì.`,
        );
      }
    }
  }
  return loi;
}

