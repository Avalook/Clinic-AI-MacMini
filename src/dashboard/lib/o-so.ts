// Ô SỐ — hàm THUẦN cho `components/ui/OSo.tsx` (27/09/2026, mục 5 kế hoạch bản
// giao diện mẫu).
//
// Vì sao không dùng `<input type="number">`:
//   · nó chặn "12 x 8" (kích thước khối, đo hai chiều) — trình duyệt trả rỗng;
//   · "36,6" (dấu phẩy kiểu Việt) bị một số trình duyệt coi là rác;
//   · lăn chuột trên ô number đổi giá trị cả khi người dùng chỉ đang cuộn trang
//     lướt qua — số bệnh án đổi mà không ai hay;
//   · nút tăng/giảm bước 1 biến "36.6" thành "37.6".
//
// Ở đây chỉ có phép biến đổi chuỗi. "Số có hợp lệ với phiếu không" là việc của
// máy chủ (`phieu_kham/khung.py::_doc_so` — rác thì để trống kèm cảnh báo).
// Luật CLAUDE.md: hàm nhận đầu vào người gõ KHÔNG ném — rác trả rỗng / null.

/** Dấu nhân chấp nhận khi gõ kích thước: x X × * */
const DAU_NHAN = /\s*[xX×*]\s*/;
const MOT_SO = /^-?(\d+([.,]\d*)?|[.,]\d+)$/;

function chuoi(v: unknown): string {
  return typeof v === "string" ? v : typeof v === "number" && Number.isFinite(v) ? String(v) : "";
}

/**
 * Lọc ký tự LÚC GÕ: bỏ chữ cái, giữ chữ số, `,` `.` `-`, dấu nhân và khoảng
 * trắng. Không đổi thứ tự, không chuẩn hoá — người đang gõ dở ("36," hay
 * "12 x") phải thấy đúng cái mình gõ. CỐ Ý không bỏ dấu nhân ở ô số thường:
 * "12 x 8" mà lặng lẽ thành "128" là đổi số bệnh án — để nguyên, rời ô thì
 * `chuanHoaSo` trả null và màn tô viền lỗi.
 */
export function locKhiGo(v: unknown): string {
  return chuoi(v).replace(/[^\d.,\-xX×*\s]/g, "");
}

/** Một số: phẩy → chấm, ".5" → "0.5", "36." → "36". Không đọc được → null. */
function motSo(chu: string): string | null {
  const t = chu.trim();
  if (!MOT_SO.test(t)) return null;
  let s = t.replace(",", ".");
  if (s.startsWith(".")) s = `0${s}`;
  if (s.startsWith("-.")) s = `-0${s.slice(1)}`;
  if (s.endsWith(".")) s = s.slice(0, -1);
  return s === "-0" ? "0" : s;
}

/**
 * Chuẩn hoá LÚC RỜI Ô. Trả:
 *   ""    ô trống;
 *   chuỗi số chuẩn (dấu chấm thập phân — cùng dạng máy chủ lưu);
 *   "12 x 8" / "12 x 8 x 5" khi `kichThuoc` (mỗi chiều là một số);
 *   null  không đọc được — màn giữ nguyên chữ người gõ và tô viền lỗi.
 */
export function chuanHoaSo(v: unknown, kichThuoc = false): string | null {
  const chu = chuoi(v).trim().replace(/\s+/g, " ");
  if (!chu) return "";
  const don = motSo(chu);
  if (don !== null) return don;
  if (!kichThuoc) return null;
  const phan = chu.split(DAU_NHAN);
  if (phan.length < 2 || phan.length > 3) return null;
  const so = phan.map(motSo);
  return so.every((x): x is string => x !== null) ? so.join(" x ") : null;
}

/**
 * Lăn chuột một nấc: bước = hàng thập phân nhỏ nhất đang có ("36.6" → 0.1,
 * "37" → 1), giữ đúng số chữ số thập phân (không để 36.599999). Không lăn
 * qua số âm khi đang ≥ 0. Trả null = không đổi (ô trống, "12 x 8", rác).
 */
export function buocLan(v: unknown, huong: number): string | null {
  const s = motSo(chuoi(v));
  if (s === null || !Number.isFinite(huong) || huong === 0) return null;
  const tp = (s.split(".")[1] ?? "").length;
  const buoc = 10 ** -tp;
  const cu = Number(s);
  let moi = cu + (huong > 0 ? buoc : -buoc);
  if (cu >= 0 && moi < 0) moi = 0;
  const ra = moi.toFixed(tp);
  return ra === "-0" || /^-0\.0+$/.test(ra) ? ra.slice(1) : ra;
}

// ---------------------------------------------------------------------------
// Đơn vị cạnh ô số (bản mẫu: "Tuổi lần đầu thấy kinh [13] tuổi")
// ---------------------------------------------------------------------------

/** Chữ trong ngoặc cuối nhãn được coi là ĐƠN VỊ (không phải chú thích). */
const DON_VI_NGOAC: Record<string, string> = {
  "ngày": "ngày",
  "tuổi": "tuổi",
  "năm": "năm",
  "tháng": "tháng",
  "tuần": "tuần",
  "lần": "lần",
  "phút": "phút",
  "giờ": "giờ",
  "mm": "mm",
  "cm": "cm",
  "kg": "kg",
  "g": "g",
  "%": "%",
  "số chu kỳ": "chu kỳ",
};

/**
 * Nhãn + đơn vị cho ô số. Khung phiếu khám (27/09/2026) CHƯA có trường
 * `don_vi` — đơn vị nằm trong nhãn ("Chu kỳ kinh nguyệt (ngày)"). Hàm này chỉ
 * tách để HIỂN THỊ; `ma` ô và dữ liệu lưu không đổi. Khung có `don_vi` thì dùng
 * nó, bỏ qua suy đoán.
 */
export function nhanVaDonVi(ten: unknown, donVi?: unknown): { nhan: string; donVi: string | null } {
  const t = chuoi(ten).trim();
  const dv = chuoi(donVi).trim();
  if (dv) return { nhan: t, donVi: dv };
  const m = t.match(/^(.*\S)\s*\(([^()]+)\)$/);
  if (m) {
    const trong = m[2].trim().toLowerCase();
    if (trong in DON_VI_NGOAC) return { nhan: m[1], donVi: DON_VI_NGOAC[trong] };
  }
  if (/^tuổi\s/i.test(t)) return { nhan: t, donVi: "tuổi" };
  if (/^số ngày\s/i.test(t)) return { nhan: t, donVi: "ngày" };
  return { nhan: t, donVi: null };
}
