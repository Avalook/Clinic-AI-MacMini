import type { NextConfig } from "next";

// ``output: "standalone"`` (server tự đóng gói) CHỈ cho Docker/Render — bật bằng
// cờ TƯỜNG MINH BUILD_STANDALONE=1 (Dockerfile.dashboard đặt). Trên Vercel TUYỆT
// ĐỐI KHÔNG standalone: nó làm Vercel 404 mọi route. Mặc định Vercel-safe, KHÔNG
// phụ thuộc dò process.env.VERCEL (project Vercel mới có thể không expose biến đó
// lúc build → standalone lọt → 404).
const standalone = process.env.BUILD_STANDALONE === "1";

// BỘ NHỚ ĐỆM PHÍA TRÌNH DUYỆT — trước đây KHÔNG có, và đó là mặc định của Next
// chứ không phải một lựa chọn ai đó đã cân nhắc.
//
// Từ Next 15, `staleTimes.dynamic` mặc định là 0 giây. Cả 37 trang trong nhóm
// (dashboard) đều khai `export const dynamic = "force-dynamic"`, nên KHÔNG trang
// nào được giữ lại: rời trang rồi quay lại là dựng lại từ đầu trên server.
//
// Đo được (máy ở Việt Nam → Supabase Seoul): mỗi lượt gọi ~80ms, và một trang
// dày như /home hay /tasks gọi 13–18 lượt. Mười giây đệm biến thao tác quay lại
// một màn vừa rời thành tức thì, mà không ai phải đọc một con số quá 10 giây
// tuổi — ngưỡng chọn theo phía an toàn vì đây là màn hình lâm sàng.
//
// `static` chỉ áp cho trang tĩnh hoặc `<Link prefetch>` — không có trang nào như
// vậy trong nhóm (dashboard), nên nó chỉ chạm các trang ngoài (đăng nhập, in).
//
// Muốn tắt hẳn: xoá khối `experimental` này. Muốn mượt hơn nữa nhưng chấp nhận
// dữ liệu cũ hơn: tăng `dynamic`. Đừng tăng nó để chữa một trang chậm — trang
// chậm thì sửa bằng cách bớt số lượt gọi tuần tự trong chính trang đó.
const clientCache = {
  staleTimes: { dynamic: 10, static: 180 },
};

// Local scripts open 127.0.0.1; allow that loopback origin for dev HMR.
// Next defaults to localhost, so its WebSocket guard otherwise rejects it.
const localDev = { allowedDevOrigins: ["127.0.0.1"] };
const nextConfig: NextConfig = standalone
  ? { ...localDev, output: "standalone", experimental: clientCache }
  : { ...localDev, experimental: clientCache };

export default nextConfig;
