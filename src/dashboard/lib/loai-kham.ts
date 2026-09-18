// Các MÀN KHÁM RIÊNG — mỗi loại khám một màn, một mục ở thanh bên.
//
// Tuyền chốt 16/09/2026: *"tách hẳn các màn khám ra cho tôi, khám nội tiết có
// gì, phụ khoa có gì… cho thành node ở sidebar"*.
//
// VÌ SAO TÁCH. Trước đây chỉ có MỘT "Bàn khám" chung, và nó chọn phiếu theo mã
// phiếu của dịch vụ. Cùng lúc có một phiếu thứ hai (ClinicalRecordForm, trong
// "Công việc của tôi") tự dò phiếu bằng chữ trong tên dịch vụ. Hai luật cho một
// câu hỏi, và chúng ra hai câu trả lời: "Sản 1" ở màn này là rỗng, ở màn kia là
// phiếu Sản.
//
// Tách màn thì màn TỰ NÓ là câu trả lời: vào "Khám nội tiết" là phiếu Nội tiết.
//
// NỘI DUNG TỪNG PHIẾU KHÔNG NẰM Ở ĐÂY. Nó nằm trong năm tệp lib/form-schemas/
// (pk, sk, nt, hmvs, nk), dựng từ tài liệu bàn giao Tuyền đã gửi. Tệp này chỉ
// nói: màn nào, tên gì, dùng phiếu nào.
//
// Mã phiếu phải khớp `clinical_form_catalogue.form_code` và cột
// `service_type.form_code` ở database — lọc khách theo đúng cột ấy.

export interface LoaiKham {
  /** Đoạn đường dẫn: /kham/<slug>. */
  slug: string;
  /** Mã phiếu — khớp `service_type.form_code`. */
  formCode: string;
  /** Tên hiện ở thanh bên và đầu màn. */
  ten: string;
}

export const LOAI_KHAM: readonly LoaiKham[] = [
  { slug: "noi-tiet", formCode: "NT", ten: "Khám nội tiết" },
  { slug: "phu-khoa", formCode: "PK", ten: "Khám phụ khoa" },
  { slug: "san", formCode: "SK", ten: "Khám sản" },
  { slug: "hiem-muon", formCode: "HMVS", ten: "Khám hiếm muộn" },
  { slug: "nam-khoa", formCode: "NK", ten: "Khám nam khoa" },
];

export function loaiKhamTheoSlug(slug: string): LoaiKham | null {
  return LOAI_KHAM.find((l) => l.slug === slug) ?? null;
}

export const HREF_KHAM = (slug: string) => `/kham/${slug}`;
