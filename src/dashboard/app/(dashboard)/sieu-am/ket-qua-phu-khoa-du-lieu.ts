// KẾT QUẢ SIÊU ÂM PHỤ KHOA — phần THUẦN: kiểu dữ liệu và hai phép đổi giữa ô
// nhập và `findings` jsonb.
//
// Tách khỏi component để `node --test` nạp được: bài kiểm không chạy qua
// bundler nên không hiểu JSX. Cùng lý do với `lib/khach-moi-cu.ts`.
// Đây cũng là chỗ đáng canh nhất của tính năng: ô trống KHÁC số 0, và một chữ
// gõ nhầm vào ô số không được phép lọt xuống database.

export interface PhuKhoaFindings {
  tu_cung?: { d?: number; r?: number; c?: number; hinh_dang?: string; tu_the?: string };
  noi_mac?: { day_mm?: number; hinh_anh?: string };
  buong_trung_phai?: { d?: number; r?: number; c?: number; the_tich?: number; afc?: number };
  buong_trung_trai?: { d?: number; r?: number; c?: number; the_tich?: number; afc?: number };
  phan_phu?: string;
  dich_o_bung?: string;
  mo_ta?: string;
}


/** Số từ ô nhập, hoặc undefined — KHÔNG đổi ô trống thành 0: 0 là một phép đo,
 *  còn trống là "không đo". Hai thứ ấy khác nhau trên hồ sơ. */
function so(v: string): number | undefined {
  const t = v.trim();
  if (!t) return undefined;
  const n = Number(t);
  return Number.isFinite(n) ? n : undefined;
}



export type OChu = Record<string, string>;

/** Giá trị ô → `findings` để gửi lên. Bỏ hết khoá rỗng: một jsonb đầy `null`
 *  đọc lên trông như đã đo mà không thấy gì. */
export function dungFindings(v: OChu, moTa: string): PhuKhoaFindings | null {
  const nhom = (tien: string) => {
    const o = {
      d: so(v[`${tien}_d`] ?? ""),
      r: so(v[`${tien}_r`] ?? ""),
      c: so(v[`${tien}_c`] ?? ""),
      the_tich: so(v[`${tien}_the_tich`] ?? ""),
      afc: so(v[`${tien}_afc`] ?? ""),
    };
    const con = Object.fromEntries(
      Object.entries(o).filter(([, x]) => x !== undefined),
    );
    return Object.keys(con).length ? con : undefined;
  };

  const out: PhuKhoaFindings = {};
  const tc = nhom("tc");
  if (tc || v.tc_hinh_dang || v.tc_tu_the) {
    out.tu_cung = {
      ...tc,
      ...(v.tc_hinh_dang ? { hinh_dang: v.tc_hinh_dang } : {}),
      ...(v.tc_tu_the ? { tu_the: v.tc_tu_the } : {}),
    };
  }
  const nmDay = so(v.nm_day ?? "");
  if (nmDay !== undefined || v.nm_hinh_anh) {
    out.noi_mac = {
      ...(nmDay !== undefined ? { day_mm: nmDay } : {}),
      ...(v.nm_hinh_anh ? { hinh_anh: v.nm_hinh_anh } : {}),
    };
  }
  const btp = nhom("btp");
  if (btp) out.buong_trung_phai = btp;
  const btt = nhom("btt");
  if (btt) out.buong_trung_trai = btt;
  if (v.phan_phu?.trim()) out.phan_phu = v.phan_phu.trim();
  if (v.dich?.trim()) out.dich_o_bung = v.dich.trim();
  if (moTa.trim()) out.mo_ta = moTa.trim();
  return Object.keys(out).length ? out : null;
}

/** `findings` đã lưu → giá trị ô, để mở lại sửa được. */
export function doVaoO(f: PhuKhoaFindings | null): OChu {
  const t = (x: number | undefined) => (x === undefined ? "" : String(x));
  return {
    tc_d: t(f?.tu_cung?.d),
    tc_r: t(f?.tu_cung?.r),
    tc_c: t(f?.tu_cung?.c),
    tc_hinh_dang: f?.tu_cung?.hinh_dang ?? "",
    tc_tu_the: f?.tu_cung?.tu_the ?? "",
    nm_day: t(f?.noi_mac?.day_mm),
    nm_hinh_anh: f?.noi_mac?.hinh_anh ?? "",
    btp_d: t(f?.buong_trung_phai?.d),
    btp_r: t(f?.buong_trung_phai?.r),
    btp_c: t(f?.buong_trung_phai?.c),
    btp_the_tich: t(f?.buong_trung_phai?.the_tich),
    btp_afc: t(f?.buong_trung_phai?.afc),
    btt_d: t(f?.buong_trung_trai?.d),
    btt_r: t(f?.buong_trung_trai?.r),
    btt_c: t(f?.buong_trung_trai?.c),
    btt_the_tich: t(f?.buong_trung_trai?.the_tich),
    btt_afc: t(f?.buong_trung_trai?.afc),
    phan_phu: f?.phan_phu ?? "",
    dich: f?.dich_o_bung ?? "",
  };
}
