import type { Metadata, Viewport } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import { connection } from "next/server";
import "./globals.css";
import { DaiStaging } from "@/components/ui/DaiStaging";
import { NapCauHinhCongKhai } from "@/components/NapCauHinhCongKhai";
import { cauHinhTuMoiTruong, maScriptCauHinh } from "@/lib/cau-hinh-cong-khai";

const inter = Inter({
  variable: "--font-sans",
  // "vietnamese" is not optional. Without it the browser falls back for every
  // đ, ơ, ư and stacked tone mark, and a clinical screen full of patient names
  // renders in two different typefaces.
  subsets: ["latin", "vietnamese"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Dr4Women — Dashboard",
  description: "Dashboard nội bộ phòng khám Dr4Women.",
  applicationName: "Dr4Women ClinicAI",
  // iPhone: "Thêm vào MH chính" mở như app riêng (không thanh Safari). Thanh
  // trạng thái "default" = chữ đen trên nền trắng, nội dung KHÔNG chui dưới tai
  // thỏ — nên không phải đệm safe-area phía trên (phía dưới BottomNav đã đệm).
  appleWebApp: { capable: true, title: "Dr4Women", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  // Cùng --color-surface của header — xem app/manifest.ts.
  themeColor: "#ffffff",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // CẤU HÌNH CÔNG KHAI ĐỌC LÚC CHẠY (01/10/2026) — một ảnh chạy cả staging lẫn
  // prod. `connection()` buộc dựng theo từng request: trang nào bị dựng sẵn lúc
  // `next build` sẽ mang cấu hình RỖNG của máy dựng. Xem lib/cau-hinh-cong-khai.ts.
  await connection();
  const cauHinh = cauHinhTuMoiTruong();
  return (
    <html
      lang="vi"
      suppressHydrationWarning
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        {/* Có mặt TRƯỚC mọi mã trình duyệt: supabase-js, tên cookie phiên,
            công tắc quyền đọc từ đây. Chỉ giá trị công khai. */}
        <script
          id="cau-hinh-cong-khai"
          dangerouslySetInnerHTML={{ __html: maScriptCauHinh(cauHinh) }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        <NapCauHinhCongKhai cauHinh={cauHinh} />
        <DaiStaging appEnv={cauHinh.appEnv} />
        {children}
      </body>
    </html>
  );
}
