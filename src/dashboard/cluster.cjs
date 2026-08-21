// Chạy Next.js trên NHIỀU tiến trình để dùng hết số nhân CPU của máy.
//
// VÌ SAO CẦN. Bản dựng standalone của Next.js là `node server.js` — MỘT tiến
// trình, tức MỘT nhân. VPS có 4 nhân, nên 3 nhân bỏ không. Dựng một trang ở
// máy chủ tốn ~163ms CPU và là việc TÍNH TOÁN, không phải chờ mạng, nên
// async không cứu được: các lượt dựng nối đuôi nhau trên một nhân. Đo trên
// staging 21/08/2026: một request /home ~200ms, nhưng 12 request song song
// mất 1778ms — trần thực tế ~7 lượt dựng/giây.
//
// ĐIỀU NÀY KHÔNG CHỮA TRIỆU CHỨNG ĐƠ mà người dùng đang gặp. Cơn đơ ấy do
// mỗi tab giữ một kết nối SSE vĩnh viễn, ăn hết hạn mức 6 kết nối/origin của
// trình duyệt (HTTP/1.1) — lúc đó CPU máy chủ đo được 0.03%, tức máy chủ
// RỖNG. Cách chữa nằm ở `RealtimeRefresher.tsx` (bầu tab chủ), làm ở nhánh
// khác. File này chỉ nâng TRẦN THÔNG LƯỢNG, thứ sẽ chạm tới khi đông người.
//
// AN TOÀN KHI NHIỀU TIẾN TRÌNH. Đã rà mã phía máy chủ: mọi biến cấp module
// đều là bảng tra HẰNG SỐ (danh sách vai được ghi, lệnh hợp lệ, khoá nhạy
// cảm) — chỉ đọc. Không có bộ đếm, bộ nhớ đệm, hay chặn tần suất trong tiến
// trình, nên không có trạng thái nào bị chia đôi. Luồng sự kiện SSE chỉ là
// proxy sang FastAPI (`app/api/events/stream/route.ts`), không giữ trạng thái.
//
// Đặt tên `.cjs` để luôn được đọc là CommonJS, bất kể `type` trong
// package.json của bản standalone.

const cluster = require("node:cluster");
const os = require("node:os");
const path = require("node:path");

const MAY_CHU = path.join(__dirname, "server.js");

// Mặc định: dùng hết số nhân, trần 4. Đặt NEXT_WORKERS=1 để về hành vi cũ —
// staging và máy dev không cần chia, và giữ đường lui một biến môi trường.
function soTienTrinh() {
  const khai = Number.parseInt(process.env.NEXT_WORKERS ?? "", 10);
  if (Number.isInteger(khai) && khai > 0) return khai;
  const nhan =
    typeof os.availableParallelism === "function"
      ? os.availableParallelism()
      : os.cpus().length;
  return Math.max(1, Math.min(nhan, 4));
}

const N = soTienTrinh();

if (N === 1 || !cluster.isPrimary) {
  // Một tiến trình thì chạy thẳng, không đẻ thêm tầng nào.
  require(MAY_CHU);
} else {
  cluster.setupPrimary({ exec: MAY_CHU });

  // CHỐNG ĐẺ VÔ HẠN. Nếu server.js chết ngay khi khởi động (cấu hình sai,
  // thiếu biến môi trường), vòng hồi sinh sẽ quay tít và đốt CPU mà không ai
  // biết vì sao. Đếm số lần chết SỚM; quá ngưỡng thì thoát hẳn để Docker
  // restart cả container — hỏng thì phải hỏng TO và rõ.
  // Khai TRƯỚC chỗ dùng: `cluster.on("exit")` bên dưới đọc biến này. Hiện tại
  // nó chỉ chạy khi có tiến trình chết nên không vỡ, nhưng để khai sau là đặt
  // một quả mìn cho lần sửa tới.
  let dangTat = false;

  const CHET_SOM_MS = 10_000;
  const NGUONG_CHET_SOM = 5;
  let chetSom = 0;
  const luc_de = new Map();

  const de = () => {
    const w = cluster.fork();
    luc_de.set(w.process.pid, Date.now());
  };

  for (let i = 0; i < N; i += 1) de();
  console.log(`[cluster] Next.js chạy ${N} tiến trình (${os.cpus().length} nhân)`);

  cluster.on("exit", (w, code, signal) => {
    const sinh = luc_de.get(w.process.pid) ?? 0;
    luc_de.delete(w.process.pid);
    if (dangTat) return;

    if (Date.now() - sinh < CHET_SOM_MS) {
      chetSom += 1;
      console.error(
        `[cluster] tiến trình ${w.process.pid} chết sau ${Date.now() - sinh}ms ` +
          `(mã ${code}, tín hiệu ${signal}) — lần ${chetSom}/${NGUONG_CHET_SOM}`,
      );
      if (chetSom >= NGUONG_CHET_SOM) {
        console.error("[cluster] chết sớm liên tiếp — thoát để Docker dựng lại");
        process.exit(1);
      }
    } else {
      // Chết sau khi đã sống ổn: coi như sự cố lẻ, hồi sinh và reset bộ đếm.
      chetSom = 0;
      console.error(`[cluster] tiến trình ${w.process.pid} chết — dựng lại`);
    }
    de();
  });

  // TẮT ÊM. Docker gửi SIGTERM rồi đợi; không chuyển tiếp thì các tiến trình
  // con bị giết cứng giữa lúc đang trả lời một request.
  for (const tin of ["SIGTERM", "SIGINT"]) {
    process.on(tin, () => {
      if (dangTat) return;
      dangTat = true;
      console.log(`[cluster] nhận ${tin} — tắt êm`);
      for (const w of Object.values(cluster.workers ?? {})) w?.kill(tin);
    });
  }
}
