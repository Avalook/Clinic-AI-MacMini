// PWA — cài ClinicAI lên màn hình chính điện thoại (Tuyền 27/09/2026: "giao
// diện PWA cho điện thoại"). Next phục vụ file này ở /manifest.webmanifest và tự
// gắn <link rel="manifest">; `proxy.ts` để nó đi thẳng (chưa đăng nhập vẫn đọc
// được — điện thoại đọc manifest TRƯỚC khi cài).
//
// KHÔNG CÓ SERVICE WORKER — CỐ Ý. Chrome/Safari cài được app mà không cần nó
// (tài liệu Next 16, guides/progressive-web-apps). Service worker để chạy
// offline nghĩa là lưu trang vào máy; trang ClinicAI mang hồ sơ bệnh nhân, và
// điện thoại thì hay mất / cho mượn. Mở lại khi có nhu cầu thật (thông báo đẩy)
// — và khi ấy service worker chỉ được lưu tệp tĩnh, không bao giờ lưu dữ liệu.
//
// Màu: manifest không đọc được CSS token nên ghi giá trị — `theme_color` =
// --color-surface (header trắng, thanh trạng thái liền màu header),
// `background_color` = màn chờ lúc mở app.

import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Dr4Women ClinicAI",
    short_name: "Dr4Women",
    description: "Phần mềm quản lý phòng khám Dr4Women.",
    lang: "vi",
    start_url: "/home",
    scope: "/",
    display: "standalone",
    orientation: "any",
    background_color: "#ffffff",
    theme_color: "#ffffff",
    icons: [
      { src: "/pwa/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/pwa/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/pwa/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
