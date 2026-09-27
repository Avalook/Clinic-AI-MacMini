import type { Metadata, Viewport } from "next";
import { Inter, Geist_Mono } from "next/font/google";
import "./globals.css";

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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="vi"
      suppressHydrationWarning
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
