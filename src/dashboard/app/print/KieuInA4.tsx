// KIỂU IN A4 dùng chung cho phiếu khám và phiếu kết quả (lát 5, 26/09/2026).
//
// Bản giao diện mẫu Tuyền duyệt: mọi phiếu A4, lề 14 / 12 / 16 mm (trên / hai bên
// / dưới), chân trang "DR4WOMEN CLINIC" + "Trang x / y"; không cắt đôi dòng bảng,
// ảnh, kết luận, chữ ký; tiêu đề mục đi liền nội dung; bảng dài lặp dòng tiêu đề.
//
// Đặt trên trang in (ngoài bố cục dashboard), nên `@page` chỉ áp cho trang ấy —
// cùng cách `/print/sono` và Tóm tắt khám bệnh đang làm.
//
// "Trang x / y" dùng ô lề trang (`@bottom-right`): Chrome/Edge in được; Safari
// chưa hỗ trợ ô lề nên bỏ qua dòng ấy (phần còn lại in bình thường).
//
// Lớp đánh dấu trong trang: `.in-giu` = không cắt đôi khối này; `.luoi-anh` =
// lưới ảnh — khi in mỗi ảnh là khối liền, không bao giờ bị cắt ngang.

const KIEU = `
@page {
  size: A4;
  margin: 14mm 12mm 16mm;
  @bottom-left {
    content: "DR4WOMEN CLINIC";
    font: 600 8pt system-ui, sans-serif;
    letter-spacing: 0.08em;
    color: var(--color-ink-muted, gray);
  }
  @bottom-right {
    content: "Trang " counter(page) " / " counter(pages);
    font: 8pt system-ui, sans-serif;
    color: var(--color-ink-muted, gray);
  }
}
@media print {
  html, body { background: white; }
  .in-a4 tr, .in-a4 figure, .in-a4 .in-giu { break-inside: avoid; }
  .in-a4 h1, .in-a4 h2, .in-a4 h3, .in-a4 caption { break-after: avoid; }
  .in-a4 thead { display: table-header-group; }
  /* ẢNH KHÔNG BAO GIỜ BỊ CẮT ĐÔI (Tuyền 30/09/2026). Ô trong lưới (grid) không
     chắc được trình duyệt giữ "break-inside: avoid" khi sang trang → khi in,
     lưới ảnh thành dòng chảy thường và mỗi ảnh là một khối inline-block: khối
     nguyên tử, trình duyệt buộc phải đẩy cả ảnh sang trang sau, không xẻ được.
     Ảnh cao quá cũng không vượt một trang A4 (297 − lề 30mm). */
  .in-a4 .luoi-anh { display: block; }
  .in-a4 .luoi-anh > figure {
    display: inline-block; width: 50%; vertical-align: top;
    box-sizing: border-box; padding: 1.5mm; break-inside: avoid;
  }
  .in-a4 img { break-inside: avoid; max-height: 250mm; }
}
`;

export default function KieuInA4() {
  return <style>{KIEU}</style>;
}
