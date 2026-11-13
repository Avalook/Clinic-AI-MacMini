// Lớp vẽ TRONG TRANG khi quay video hướng dẫn (nạp bằng `addInitScript`).
// Không đụng code app: mọi thứ gắn vào <html> (anh em của <body>), nên khi phóng to
// <body> bằng CSS transform thì con trỏ, phụ đề, khung đỏ không bị phóng theo.
// Node gọi qua `window.__vd.<lệnh>(…)` — lệnh có hiệu ứng trả Promise xong khi xong.
//
// Vì sao phụ đề vẽ ở đây thay vì in cứng bằng ffmpeg: bản ffmpeg của Homebrew trên máy
// này không có bộ lọc `subtitles`/`drawtext` (thiếu libass/freetype). Chrome vẽ chữ
// Việt có dấu nét hơn, và biết vị trí nút để đẩy phụ đề lên khi đè (giao việc mục 6.3).
(() => {
  if (window.__vd) return;
  const Z = 2147483000;
  const css = `
  #vd-tro{position:fixed;left:0;top:0;width:30px;height:30px;z-index:${Z + 5};pointer-events:none;
    transform:translate(-100px,-100px);will-change:transform}
  #vd-tro svg{filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
  .vd-gon{position:fixed;width:20px;height:20px;margin:-10px 0 0 -10px;border-radius:50%;z-index:${Z + 4};
    pointer-events:none;border:3px solid rgba(220,38,38,.9);animation:vd-gon .55s ease-out forwards}
  @keyframes vd-gon{from{transform:scale(.4);opacity:1}to{transform:scale(3.2);opacity:0}}
  #vd-khung{position:fixed;z-index:${Z + 2};pointer-events:none;border:3px solid #dc2626;border-radius:12px;
    box-shadow:0 0 0 9999px rgba(0,0,0,.30);opacity:0;transition:opacity .25s}
  #vd-pd{position:fixed;left:50%;transform:translateX(-50%);bottom:44px;z-index:${Z + 3};pointer-events:none;
    max-width:1500px;text-align:center;font:600 36px/1.35 Inter,"Segoe UI",Arial,sans-serif;color:#fff;
    background:rgba(10,14,18,.78);border-radius:10px;padding:10px 26px;
    text-shadow:0 1px 2px rgba(0,0,0,.6);white-space:pre-line;opacity:0;transition:opacity .12s}
  #vd-pd.tren{bottom:auto;top:72px}
  #vd-the{position:fixed;inset:0;z-index:${Z + 6};display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:28px;background:#0f3d3e;color:#fff;font-family:Inter,"Segoe UI",Arial,sans-serif;
    opacity:0;transition:opacity .35s;pointer-events:none}
  #vd-the.hien{opacity:1}
  #vd-the .so{font-size:30px;letter-spacing:.2em;text-transform:uppercase;opacity:.75}
  #vd-the .ten{font-size:80px;font-weight:700;max-width:1500px;text-align:center;line-height:1.15}
  #vd-the .phu{font-size:36px;opacity:.92;max-width:1400px;text-align:center;line-height:1.35}
  body.vd-phong{transition:transform .6s cubic-bezier(.4,0,.2,1)}
  nextjs-portal{display:none!important}
  `;
  // ↑ nút báo "N" của Next.js chế độ dev (scripts/dev-giao-dien.sh) — không phải giao diện app.
  const cho = (ms) => new Promise((r) => setTimeout(r, ms));
  let x = -100;
  let y = -100;
  let pdTimer = [];

  function gan() {
    if (document.getElementById("vd-tro")) return;
    const st = document.createElement("style");
    st.textContent = css;
    document.documentElement.appendChild(st);
    const tro = document.createElement("div");
    tro.id = "vd-tro";
    tro.innerHTML =
      '<svg width="30" height="30" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8 16.5 L11.5 24 L15 22.5 L11.5 15 L18 15 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    const khung = document.createElement("div");
    khung.id = "vd-khung";
    const pd = document.createElement("div");
    pd.id = "vd-pd";
    const the = document.createElement("div");
    the.id = "vd-the";
    document.documentElement.append(tro, khung, pd, the);
    if (x >= 0) datTro(x, y);
  }

  function datTro(nx, ny) {
    x = nx;
    y = ny;
    const t = document.getElementById("vd-tro");
    if (t) t.style.transform = `translate(${nx - 3}px,${ny - 2}px)`;
  }

  // Lướt cong (bezier bậc 2) tới (tx,ty) trong `ms`, nhanh giữa — chậm hai đầu.
  async function luot(tx, ty, ms) {
    gan();
    if (x < 0) datTro(window.innerWidth * 0.55, window.innerHeight * 0.6);
    const sx = x;
    const sy = y;
    const cx = (sx + tx) / 2 + (ty - sy) * 0.2;
    const cy = (sy + ty) / 2 - (tx - sx) * 0.2;
    const t0 = performance.now();
    await new Promise((xong) => {
      const buoc = (now) => {
        const t = Math.min(1, (now - t0) / ms);
        const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        const px = (1 - e) * (1 - e) * sx + 2 * (1 - e) * e * cx + e * e * tx;
        const py = (1 - e) * (1 - e) * sy + 2 * (1 - e) * e * cy + e * e * ty;
        datTro(px, py);
        if (t < 1) requestAnimationFrame(buoc);
        else xong();
      };
      requestAnimationFrame(buoc);
    });
  }

  window.__vd = {
    gan,
    // Vị trí con trỏ (giữ qua lần tải trang: Node đặt lại sau `goto`).
    viTri: () => ({ x, y }),
    datViTri: (nx, ny) => {
      gan();
      datTro(nx, ny);
    },
    async luotToi(tx, ty, ms = 600) {
      await luot(tx, ty, ms);
    },
    gon() {
      const g = document.createElement("div");
      g.className = "vd-gon";
      g.style.left = `${x}px`;
      g.style.top = `${y}px`;
      document.documentElement.appendChild(g);
      setTimeout(() => g.remove(), 700);
    },
    async nhanManh(r, ms = 1200) {
      gan();
      const k = document.getElementById("vd-khung");
      const p = 8;
      Object.assign(k.style, {
        left: `${r.x - p}px`,
        top: `${r.y - p}px`,
        width: `${r.width + 2 * p}px`,
        height: `${r.height + 2 * p}px`,
      });
      k.style.opacity = "1";
      await cho(ms);
    },
    boNhanManh() {
      const k = document.getElementById("vd-khung");
      if (k) k.style.opacity = "0";
    },
    async phongTo(r, he = 1.6, giu = 1400) {
      const b = document.body;
      b.classList.add("vd-phong");
      b.style.transformOrigin = `${r.x + r.width / 2 + window.scrollX}px ${r.y + r.height / 2 + window.scrollY}px`;
      await cho(30);
      b.style.transform = `scale(${he})`;
      await cho(600 + giu);
      b.style.transform = "";
      await cho(650);
      b.classList.remove("vd-phong");
      b.style.transformOrigin = "";
    },
    // Phụ đề: [{chu, sau_ms}] — đổi đoạn theo mốc tính từ lúc gọi.
    phuDe(doan) {
      gan();
      pdTimer.forEach(clearTimeout);
      pdTimer = [];
      const pd = document.getElementById("vd-pd");
      for (const d of doan) {
        pdTimer.push(
          setTimeout(() => {
            pd.textContent = d.chu;
            pd.style.opacity = d.chu ? "1" : "0";
          }, d.sau_ms),
        );
      }
    },
    // Phần tử sắp bấm nằm trong vùng phụ đề ⇒ đẩy phụ đề lên đỉnh (cho cảnh này).
    tranhPhuDe(r) {
      gan();
      const pd = document.getElementById("vd-pd");
      const vung = window.innerHeight - 44 - 2 * 49 - 20 - 24;
      pd.classList.toggle("tren", !!r && r.y + r.height > vung);
    },
    the(so, ten, phu) {
      gan();
      const t = document.getElementById("vd-the");
      t.replaceChildren();
      for (const [lop, chu] of [
        ["so", so],
        ["ten", ten],
        ["phu", phu],
      ]) {
        if (!chu) continue;
        const d = document.createElement("div");
        d.className = lop;
        d.textContent = chu;
        t.appendChild(d);
      }
      t.classList.add("hien");
    },
    anThe() {
      document.getElementById("vd-the")?.classList.remove("hien");
    },
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", gan);
  else gan();
})();
