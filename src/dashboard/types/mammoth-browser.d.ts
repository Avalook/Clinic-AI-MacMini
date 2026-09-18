// Bản dựng cho trình duyệt của mammoth (đổi DOCX → HTML) không kèm khai báo
// kiểu. Chỉ khai phần màn hình dùng.
declare module "mammoth/mammoth.browser" {
  export function convertToHtml(input: {
    arrayBuffer: ArrayBuffer;
  }): Promise<{ value: string; messages: unknown[] }>;
}
