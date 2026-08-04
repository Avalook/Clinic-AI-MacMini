// Registry form chuyên khoa: service_code → schema. Engine + route đọc từ đây.
// Thêm form mới = thêm 1 config + 1 dòng đăng ký (KHÔNG sửa engine/route).
//
// NK ĐÃ MỞ (04/08/2026). Trước đây nó bị giữ ngoài registry vì `nk.ts` là bản
// lắp tạm từ các trường nam khoa nằm trong section Hiếm muộn của tài liệu bàn
// giao — không có mục Nam khoa riêng, nên không ai dám cho bác sĩ ký vào.
//
// Nay `nk.ts` dựng theo docs/spec-form-nam-khoa.md §5, và Quang đã ghi một dòng
// duyệt trong `clinical_form_approval` (bản dùng thử, chưa có chữ ký BS Nam
// khoa — ghi rõ trong `source_document`).
//
// HAI CÁI KHOÁ, VÀ CHÚNG ĐỘC LẬP. `clinical_form_catalogue.is_active` ở
// database quyết định form có hiệu lực không; registry này quyết định trình
// duyệt có dựng được form không. Mở một cái mà quên cái kia thì form im lặng
// không hiện — đúng chuyện vừa xảy ra. Bật form mới phải mở CẢ HAI.
import type { FormSchema } from "./types";
import { pkSchema } from "./pk";
import { skSchema } from "./sk";
import { ntSchema } from "./nt";
import { hmvsSchema } from "./hmvs";
import { nkSchema } from "./nk";

const REGISTRY: Record<string, FormSchema> = {
  PK: pkSchema,
  SK: skSchema,
  NT: ntSchema,
  HMVS: hmvsSchema,
  NK: nkSchema,
};

/** Schema theo service_code, hoặc null nếu chưa có config. */
export function getFormSchema(serviceCode: string | null | undefined): FormSchema | null {
  if (!serviceCode) return null;
  return REGISTRY[serviceCode.toUpperCase()] ?? null;
}

/** Đoán service_code từ TÊN dịch vụ (pilot: chưa truyền service_type.code).
 *  Map theo legend docx. Trả null nếu không khớp form nào đã cấu hình. */
export function resolveServiceCode(serviceName: string | null | undefined): string | null {
  const n = (serviceName ?? "").toLowerCase();
  // Thứ tự khớp: cụm dài/đặc thù trước (tránh "sản" nuốt "sản khoa" v.v.).
  if (n.includes("hiếm muộn") || n.includes("vô sinh") || n.includes("hiem muon") || n.includes("vo sinh"))
    return "HMVS";
  if (n.includes("nội tiết") || n.includes("noi tiet")) return "NT";
  if (n.includes("nam khoa")) return "NK";
  if (n.includes("phụ khoa") || n.includes("phu khoa")) return "PK";
  if (n.includes("sản") || n.includes("san khoa")) return "SK";
  return null;
}
