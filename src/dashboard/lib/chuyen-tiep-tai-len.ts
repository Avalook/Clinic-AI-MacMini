// Chuyển tiếp một lượt TẢI TỆP sang FastAPI theo luồng, KHÔNG thời hạn.
//
// VÌ SAO KHÔNG DÙNG fetch (Tuyền chốt 16/09/2026: không giới hạn dung lượng).
// `fetch` của Node (undici) chờ header trả lời tối đa 300 giây. FastAPI chỉ trả
// lời SAU KHI đã nhận hết tệp và chép xong lên kho Viettel — một video vài GB
// mất lâu hơn thế, và undici cắt kết nối giữa chừng: người dùng thấy "không kết
// nối được máy chủ" trong khi tệp gần lên xong. `node:http` không có hạn ấy.
//
// Thân request đi thẳng từ trình duyệt → Next → FastAPI, không nạp vào RAM.

import http from "node:http";
import https from "node:https";
import { Readable } from "node:stream";

export interface TraLoiTaiLen {
  status: number;
  text: string;
}

export function chuyenTiepTaiLen(
  url: string,
  request: Request,
  headers: Record<string, string>,
): Promise<TraLoiTaiLen> {
  const dich = new URL(url);
  const mod = dich.protocol === "https:" ? https : http;
  return new Promise((resolve, reject) => {
    const req = mod.request(
      dich,
      { method: "POST", headers, timeout: 0 },
      (res) => {
        const khuc: Buffer[] = [];
        res.on("data", (c: Buffer) => khuc.push(c));
        res.on("end", () =>
          resolve({
            status: res.statusCode ?? 502,
            text: Buffer.concat(khuc).toString("utf8"),
          }),
        );
        res.on("error", reject);
      },
    );
    req.on("error", reject);
    if (!request.body) {
      req.end();
      return;
    }
    const nguon = Readable.fromWeb(
      request.body as import("node:stream/web").ReadableStream<Uint8Array>,
    );
    // Trình duyệt huỷ giữa chừng → huỷ luôn phía FastAPI (nó dọn tệp tạm).
    nguon.on("error", (e) => req.destroy(e));
    nguon.pipe(req);
  });
}
