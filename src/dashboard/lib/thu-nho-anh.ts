// Thu nhỏ ảnh chuyển khoản trước khi gửi (≤ 1600px JPEG) — MỘT bản cho quầy thu
// (`thu-ngan/AnhChuyenKhoan.tsx`) và sổ thu hộ đối tác (`ban-xet-nghiem/BuocThuHo.tsx`).
// Ảnh chụp điện thoại vài MB thành vài trăm KB; HEIC của iPhone (trình duyệt đọc được)
// thành JPEG máy tính phòng khám xem được. Không đọc được ảnh ⇒ gửi nguyên, máy chủ
// tự kiểm kiểu.

const CANH_TOI_DA = 1600;

export async function thuNho(tep: File): Promise<Blob> {
  try {
    const bmp = await createImageBitmap(tep);
    const tile = Math.min(1, CANH_TOI_DA / Math.max(bmp.width, bmp.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bmp.width * tile);
    canvas.height = Math.round(bmp.height * tile);
    canvas.getContext("2d")?.drawImage(bmp, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, "image/jpeg", 0.85));
    return blob ?? tep;
  } catch {
    return tep;
  }
}
