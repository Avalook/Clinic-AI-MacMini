// Nhận phản hồi kèm ảnh từ Bảng điều khiển.
//
// Ảnh được ghi ra ĐĨA (.feedback/) thay vì nhét vào database: chúng là ảnh chụp
// màn hình để tôi mở ra xem, không phải dữ liệu của phòng khám. Để trong DB thì
// mỗi lần dump backup lại kéo theo vài MB ảnh, còn để ngoài đĩa thì tôi mở bằng
// trình xem ảnh bình thường.

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { NextResponse } from "next/server";

import { proxyJsonToBackend } from "../../../../lib/backend-proxy";

const DIR = process.env.FEEDBACK_DIR ?? path.join(process.cwd(), "..", "..", ".feedback");

export async function POST(request: Request) {
  const form = await request.formData().catch(() => null);
  if (!form) {
    return NextResponse.json({ error: "Dữ liệu không hợp lệ" }, { status: 400 });
  }

  const comment = String(form.get("comment") ?? "").trim();
  if (!comment) {
    return NextResponse.json({ error: "Chưa nhập mô tả" }, { status: 400 });
  }

  let imagePath: string | null = null;
  const file = form.get("image");
  if (file && file instanceof File && file.size > 0) {
    // Giới hạn 8MB: ảnh chụp màn hình lớn nhất cũng dưới mức này, và không có
    // lý do gì để một khung phản hồi nhận file tuỳ ý.
    if (file.size > 8 * 1024 * 1024) {
      return NextResponse.json({ error: "Ảnh quá lớn (>8MB)" }, { status: 413 });
    }
    await mkdir(DIR, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const name = `${stamp}.png`;
    await writeFile(path.join(DIR, name), Buffer.from(await file.arrayBuffer()));
    imagePath = `.feedback/${name}`;
  }

  return proxyJsonToBackend("POST", "/api/v1/console/feedback", {
    comment,
    severity: String(form.get("severity") ?? "nhan_xet"),
    page_url: String(form.get("page_url") ?? "") || null,
    role_at_time: String(form.get("role_at_time") ?? "") || null,
    image_path: imagePath,
  });
}
