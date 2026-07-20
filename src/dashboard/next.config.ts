import type { NextConfig } from "next";

// ``output: "standalone"`` (server tự đóng gói) CHỈ cho Docker/Render — bật bằng
// cờ TƯỜNG MINH BUILD_STANDALONE=1 (Dockerfile.dashboard đặt). Trên Vercel TUYỆT
// ĐỐI KHÔNG standalone: nó làm Vercel 404 mọi route. Mặc định Vercel-safe, KHÔNG
// phụ thuộc dò process.env.VERCEL (project Vercel mới có thể không expose biến đó
// lúc build → standalone lọt → 404).
const standalone = process.env.BUILD_STANDALONE === "1";

const nextConfig: NextConfig = standalone ? { output: "standalone" } : {};

export default nextConfig;
