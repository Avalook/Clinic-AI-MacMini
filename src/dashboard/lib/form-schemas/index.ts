// Registry form chuyên khoa: service_code → schema. Engine + route đọc từ đây.
// Thêm form mới = thêm 1 config + 1 dòng đăng ký (KHÔNG sửa engine/route).
// Only doctor-sourced schemas are exposed. NK has no standalone source section
// and stays quarantined until the clinic signs off a dedicated form.

import type { FormSchema } from "./types";
import { pkSchema } from "./pk";
import { skSchema } from "./sk";
import { ntSchema } from "./nt";
import { hmvsSchema } from "./hmvs";

const REGISTRY: Record<string, FormSchema> = {
  PK: pkSchema,
  SK: skSchema,
  NT: ntSchema,
  HMVS: hmvsSchema,
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
