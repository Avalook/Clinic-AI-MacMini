// Ô chọn nhân viên khi xếp lịch làm việc (phòng khám 09/10/2026: "hiển thị đầy
// đủ họ tên; thêm ô tìm tên cho nhanh; phân nhóm Bác sĩ, Điều dưỡng, Trưởng ca,
// CSKH… kiểu xổ ra theo nhóm").
//
// CHỈ LỌC + CHIA NHÓM TẠI CHỖ trên danh sách máy chủ đã trả và giao diện đã lọc
// theo ma trận `vai_duoc_vao_tram` — không quyết ai được xếp (máy chủ kiểm lại
// khi lưu). Nhãn nhóm lấy `ROLE_LABEL` (khớp `NHAN_VAI` phía máy chủ), không
// chép bảng nhãn mới.

import { ROLE_LABEL, isClinicRole, type ClinicRole } from "./roles.ts";
import { chuanHoa } from "./tiep-don.ts";

export interface NguoiChonDuoc {
  id: string;
  /** Tên hiển thị (đã gọt viết tắt — `doctorName`). */
  name: string;
  /** `staff.primary_department`. */
  vai: string | null | undefined;
  /** `staff.full_name` nguyên văn — để tìm theo cả chữ đang lưu. */
  hoTen?: string | null;
  /** `staff.short_name` — tên gọi ở phòng khám ("Hà Vũ"). */
  tenNgan?: string | null;
}

export interface NhomNhanVien<T extends NguoiChonDuoc> {
  /** Mã vai; "KHAC" cho người không có / sai mã vai. */
  ma: string;
  nhan: string;
  nguoi: T[];
}

/** Nhóm đứng đầu theo lời phòng khám; các vai còn lại theo thứ tự `ROLE_LABEL`. */
const THU_TU_DAU: ClinicRole[] = ["DOCTOR", "NURSE_ULTRASOUND", "TRUONG_CA", "CSKH"];
const THU_TU: string[] = [
  ...THU_TU_DAU,
  ...(Object.keys(ROLE_LABEL) as ClinicRole[]).filter((v) => !THU_TU_DAU.includes(v)),
];
export const MA_NHOM_KHAC = "KHAC";

function chu(s: unknown): string {
  return typeof s === "string" ? chuanHoa(s) : "";
}

/** Bỏ ký tự không phải chữ/số để chuỗi rác ("%%", "(", "\\") không làm hỏng
 *  so khớp — còn lại rỗng thì coi như chưa gõ gì. */
function tuKhoa(kim: unknown): string[] {
  return chu(kim)
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter(Boolean);
}

/** Người có khớp ô tìm không. Rỗng / toàn ký tự rác = khớp hết. Mọi từ gõ vào
 *  phải có mặt (bỏ dấu, không phân biệt hoa thường) trong họ tên, tên hiển thị
 *  hoặc tên gọi — "le quyet" khớp "Bác sĩ · BSNT. Lê Thiệu Quyết". */
export function khopNhanVien(kim: unknown, n: NguoiChonDuoc): boolean {
  const tu = tuKhoa(kim);
  if (tu.length === 0) return true;
  const nguon = [n.name, n.hoTen, n.tenNgan].map(chu).join(" ").replace(/[^\p{L}\p{N}\s]/gu, " ");
  return tu.every((t) => nguon.includes(t));
}

/** Chia danh sách thành nhóm theo vai, đã lọc theo ô tìm. Nhóm rỗng bỏ đi;
 *  trong nhóm xếp theo tên (tiếng Việt). Người không có vai → nhóm "Khác". */
export function nhomNhanVien<T extends NguoiChonDuoc>(
  ds: readonly T[] | null | undefined,
  kim: unknown = "",
): NhomNhanVien<T>[] {
  const theoMa = new Map<string, T[]>();
  for (const n of ds ?? []) {
    if (!n || typeof n.id !== "string") continue;
    if (!khopNhanVien(kim, n)) continue;
    const ma = typeof n.vai === "string" && isClinicRole(n.vai) ? n.vai : MA_NHOM_KHAC;
    const list = theoMa.get(ma) ?? [];
    list.push(n);
    theoMa.set(ma, list);
  }
  const thuTu = [...THU_TU, MA_NHOM_KHAC];
  return [...theoMa.entries()]
    .sort(([a], [b]) => thuTu.indexOf(a) - thuTu.indexOf(b))
    .map(([ma, nguoi]) => ({
      ma,
      nhan: ma === MA_NHOM_KHAC ? "Khác" : ROLE_LABEL[ma as ClinicRole],
      nguoi: [...nguoi].sort((x, y) =>
        String(x.name ?? "").localeCompare(String(y.name ?? ""), "vi"),
      ),
    }));
}

/** Đang gõ tìm (có từ khoá thật) — giao diện mở sẵn mọi nhóm có kết quả. */
export function dangTim(kim: unknown): boolean {
  return tuKhoa(kim).length > 0;
}
