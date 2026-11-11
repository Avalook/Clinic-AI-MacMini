// Quay MỘT chương một mạch bằng Playwright + Chrome thật, khung 1920×1080.
// Mỗi cảnh: hiện phụ đề → làm các bước (con trỏ lướt tới, khung đỏ, phóng to, bấm, gõ)
// → chờ cho đủ độ dài tiếng (+0,4 giây). Ghi mốc bắt đầu/kết thúc từng cảnh (giây tính
// từ lúc trang được tạo = giây 0 của tệp quay) để ghép tiếng bằng `adelay`.
//
// Phần tử chỉ tìm theo VAI + TÊN, CHỮ TRÊN MÀN hoặc NHÃN Ô (như người dùng thấy) —
// không theo class CSS. Không thấy ⇒ ném LoiCanh nói đúng cảnh nào, tìm gì; không quay tiếp.

import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import { writeFile } from "node:fs/promises";
import { join } from "node:path";

import { CAU_HINH, REPO, email } from "./api.mjs";
import { mocPhuDe } from "./loi.mjs";

const require = createRequire(join(REPO, "src/dashboard/package.json"));
const { chromium } = require("playwright");

export const KHUNG = { width: 1920, height: 1080 };
const NGHI_SAU_TIENG = 0.4;
const LOP = readFileSync(new URL("./lop-trang.js", import.meta.url), "utf8");

export class LoiCanh extends Error {
  constructor(canh, buoc, cau) {
    super(`Cảnh «${canh}», bước ${buoc}: ${cau}`);
  }
}

const cho = (ms) => new Promise((r) => setTimeout(r, ms));
const moTa = (s) => (s.role ? `${s.role} "${s.name}"` : s.label ? `ô "${s.label}"` : `chữ "${s.text}"`);

/** `name: "/…/"` = mẫu (regex, không phân biệt hoa thường) — vd dòng sổ của ĐÚNG khách:
 *  `"/{khach_hoan}.*hoàn tiền/"` (sổ còn dòng hoàn của lần quay trước cùng ngày). */
const tenRole = (n) => (typeof n === "string" && n.length > 2 && n.startsWith("/") && n.endsWith("/") ? new RegExp(n.slice(1, -1), "i") : n);

function timTrong(goc, spec) {
  const exact = spec.exact ?? false;
  if (spec.role) return goc.getByRole(spec.role, { name: tenRole(spec.name), exact });
  // Nhãn / chữ cũng nhận mẫu "/…/" — vd tên tệp email đổi theo mỗi lần dựng dữ liệu.
  if (spec.label) return goc.getByLabel(tenRole(spec.label), { exact });
  if (spec.text) return goc.getByText(tenRole(spec.text), { exact });
  throw new Error(`Bước không có role/label/text: ${JSON.stringify(spec)}`);
}

/** `trong: "<chữ>"` = trong khung NHỎ NHẤT chứa cả chữ đó lẫn phần tử cần tìm (thẻ việc,
 *  thẻ đối tác, form…) — vd hai nút "Lưu" trên một màn: lấy nút ở form "Thêm đối tác". */
function timPhanTu(page, spec, trong) {
  if (!trong) return timTrong(page, spec).first();
  const khung = page
    .locator("article, li, section, form, div")
    .filter({ hasText: trong })
    .filter({ has: timTrong(page, spec) })
    .last();
  return timTrong(khung, spec).first();
}

/** Một khung thử ⇒ kích thước vùng Chrome đang ghi. */
async function doKhung(cdp) {
  const meta = await new Promise((ok) => {
    const nghe = ({ metadata, sessionId }) => {
      cdp.off("Page.screencastFrame", nghe);
      cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
      ok(metadata);
    };
    cdp.on("Page.screencastFrame", nghe);
    cdp.send("Page.startScreencast", { format: "png", everyNthFrame: 1 });
  });
  await cdp.send("Page.stopScreencast");
  return meta;
}

/**
 * Chrome chạy ẩn ghi CẢ CỬA SỔ, mà cửa sổ mặc định thấp hơn khung giả lập: vùng ghi chỉ
 * cao 993 px (09/11) — đáy trang (phụ đề!) không vào hình, ghép lại bị kéo giãn méo chữ.
 * `--window-size` / `screen` không ăn; đặt thẳng cửa sổ qua CDP rồi đo, chỉnh tới khi
 * vùng ghi đúng 1920×1080.
 */
async function chinhCuaSo(cdp) {
  const { windowId } = await cdp.send("Browser.getWindowForTarget");
  let cao = KHUNG.height + 87;
  for (let lan = 0; lan < 5; lan++) {
    await cdp.send("Browser.setWindowBounds", { windowId, bounds: { width: KHUNG.width, height: cao } });
    await cho(250);
    const m = await doKhung(cdp);
    if (m.deviceWidth === KHUNG.width && m.deviceHeight === KHUNG.height) return;
    cao += KHUNG.height - m.deviceHeight;
  }
  throw new Error("Không chỉnh được cửa sổ Chrome về vùng ghi 1920×1080.");
}

/**
 * Ghi hình bằng CDP `Page.startScreencast` (PNG — chữ 13px không nhoè). Chrome chỉ gửi
 * khung khi màn đổi, kèm dấu giờ của chính nó (giây epoch) ⇒ quy về trục `t0` của mốc
 * cảnh, cùng đồng hồ với tiếng. `dung(tu, den)` viết danh sách ffconcat cho [tu, den]:
 * mỗi khung giữ tới khung kế tiếp; ffmpeg dựng lại 30 fps đều.
 * (Không dùng `recordVideo`: cần tải ffmpeg riêng của Playwright, và nó nén VP8 làm mờ chữ.)
 */
async function batDauGhi(ctx, page, thuMuc, t0) {
  const cdp = await ctx.newCDPSession(page);
  await chinhCuaSo(cdp);
  const khung = [];
  const ghiDo = [];
  let saiCo = 0;
  cdp.on("Page.screencastFrame", ({ data, metadata, sessionId }) => {
    cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
    // Khung không đúng 1920×1080 (cửa sổ đang đổi cỡ) ⇒ bỏ, không kéo giãn cho méo chữ.
    if (metadata.deviceWidth !== KHUNG.width || metadata.deviceHeight !== KHUNG.height) {
      saiCo++;
      return;
    }
    const t = metadata.timestamp - t0 / 1000;
    const tep = join(thuMuc, `k${String(khung.length).padStart(6, "0")}.png`);
    khung.push({ t, tep });
    ghiDo.push(writeFile(tep, Buffer.from(data, "base64")));
  });
  await cdp.send("Page.startScreencast", { format: "png", maxWidth: KHUNG.width, maxHeight: KHUNG.height, everyNthFrame: 1 });
  return {
    soKhung: () => khung.length,
    saiCo: () => saiCo,
    /** Trễ lớn nhất giữa mốc đầu cảnh (phụ đề cảnh đó hiện) và khung đầu tiên sau mốc. */
    treKhung: (mocs) =>
      Math.max(0, ...mocs.map((t) => (khung.find((k) => k.t >= t)?.t ?? t) - t)),
    async dung(tu, den) {
      await cdp.send("Page.stopScreencast").catch(() => {});
      await Promise.all(ghiDo);
      // Khung cuối trước `tu` làm khung đầu (màn đứng yên thì Chrome không gửi khung mới).
      let dau = khung.findLastIndex((k) => k.t <= tu);
      if (dau < 0) dau = 0;
      const ds = khung.slice(dau).filter((k) => k.t < den);
      if (!ds.length) throw new Error("Không ghi được khung hình nào.");
      const dong = ["ffconcat version 1.0"];
      for (const [i, k] of ds.entries()) {
        const bat = Math.max(k.t, tu);
        const ket = i + 1 < ds.length ? Math.max(ds[i + 1].t, tu) : den;
        if (ket - bat <= 0) continue;
        dong.push(`file '${k.tep}'`, `duration ${(ket - bat).toFixed(4)}`);
      }
      dong.push(`file '${ds.at(-1).tep}'`);
      const ds_tep = join(thuMuc, "khung.ffconcat");
      writeFileSync(ds_tep, `${dong.join("\n")}\n`);
      return ds_tep;
    },
  };
}

async function dangNhap(browser, ai) {
  const ctx = await browser.newContext({ viewport: KHUNG });
  const page = await ctx.newPage();
  await page.goto(`${CAU_HINH.web}/login`);
  // Email đầy đủ (có "@" thì form giữ nguyên) — nick có dấu chấm như "dd.sa" bị đổi khác.
  await page.getByPlaceholder("tên đăng nhập").fill(email(ai));
  await page.getByPlaceholder("Nhập mật khẩu").fill(CAU_HINH.matKhau);
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 20_000 });
  const trangThai = await ctx.storageState();
  await ctx.close();
  return trangThai;
}

/** Màn đang "Đang tải…" / có thông báo lỗi ⇒ chưa được quay tiếp. */
async function choManYen(page, canh, giay = 10) {
  const het = Date.now() + giay * 1000;
  while (Date.now() < het) {
    const dangTai = await page.getByText("Đang tải…").count();
    if (!dangTai) return;
    await cho(150);
  }
  throw new LoiCanh(canh, "-", `màn vẫn "Đang tải…" sau ${giay} giây.`);
}

async function kiemLoi(page, canh, cam = []) {
  if (cam.length) {
    const chu = await page.evaluate(() => document.body.innerText);
    for (const m of cam) {
      const thay = chu.match(new RegExp(m));
      if (thay) throw new LoiCanh(canh, "-", `trên màn có chữ bị cấm trong chương này: "${thay[0]}".`);
    }
  }
  // Bỏ ô báo đổi trang của Next.js (`next-route-announcer`, cũng role=alert, chứa tiêu đề trang).
  const canhBao = page.locator('[role="alert"]:not(#__next-route-announcer__):not(next-route-announcer *)');
  for (const a of await canhBao.all()) {
    if (await a.isVisible()) {
      const chu = (await a.innerText()).trim();
      if (chu) throw new LoiCanh(canh, "-", `màn hiện thông báo lỗi: "${chu.slice(0, 120)}".`);
    }
  }
}

async function hop(page, el, canh, i, spec) {
  try {
    await el.waitFor({ state: "visible", timeout: 8000 });
  } catch {
    throw new LoiCanh(canh, i + 1, `không tìm thấy ${moTa(spec)} trên màn.`);
  }
  // Cuộn MƯỢT tới phần tử (cuộn tức thì làm hình nhảy).
  const trongKhung = await el.evaluate((n) => {
    const r = n.getBoundingClientRect();
    return r.top >= 80 && r.bottom <= window.innerHeight - 220;
  });
  if (!trongKhung) {
    await el.evaluate((n) => n.scrollIntoView({ behavior: "smooth", block: "center" }));
    await cho(700);
  }
  const b = await el.boundingBox();
  if (!b) throw new LoiCanh(canh, i + 1, `${moTa(spec)} không có vị trí trên màn.`);
  await page.evaluate((r) => window.__vd.tranhPhuDe(r), b);
  return b;
}

async function lamBuoc(page, canh, i, buoc) {
  const [loai, spec] = Object.entries(buoc)[0];
  if (loai === "dung") return cho(Number(spec) * 1000);
  if (loai === "cho") {
    const el = timPhanTu(page, spec, spec.trong);
    try {
      await el.waitFor({ state: "visible", timeout: 10_000 });
    } catch {
      throw new LoiCanh(canh, i + 1, `chờ mãi không thấy ${moTa(spec)}.`);
    }
    return choManYen(page, canh);
  }
  const el = timPhanTu(page, spec, spec.trong);
  const b = await hop(page, el, canh, i, spec);
  const giua = [b.x + b.width / 2, b.y + b.height / 2];
  if (loai === "re") {
    // Rê chuột THẬT vào (vd thanh bên chỉ có biểu tượng ⇒ mở rộng hiện chữ), con trỏ giả theo.
    await page.evaluate(([x, y]) => window.__vd.luotToi(x, y, 650), giua);
    await el.hover();
    await cho(450);
    return;
  }
  if (loai === "nhan_manh") {
    await page.evaluate(([x, y]) => window.__vd.luotToi(x, y, 650), giua);
    await page.evaluate((r) => window.__vd.nhanManh(r, 1200), b);
    await page.evaluate(() => window.__vd.boNhanManh());
    return;
  }
  if (loai === "phong_to") {
    await page.evaluate(([x, y]) => window.__vd.luotToi(x, y, 650), giua);
    await page.evaluate(([r, he]) => window.__vd.phongTo(r, he, 1400), [b, spec.he ?? 1.6]);
    return;
  }
  if (loai === "chon") {
    // Ô thả xuống: con trỏ tới, gợn, chọn đúng mục theo CHỮ (danh mục có tên trùng ⇒ mục đầu).
    await page.evaluate(([x, y]) => window.__vd.luotToi(x, y, 600), giua);
    await page.evaluate(() => window.__vd.gon());
    await cho(150);
    const giaTri = await el.evaluate(
      (s, chu) => [...s.options].find((o) => o.textContent.trim() === chu)?.value ?? null,
      String(spec.chu),
    );
    if (giaTri === null) throw new LoiCanh(canh, i + 1, `ô ${moTa(spec)} không có mục "${spec.chu}".`);
    await el.selectOption(giaTri);
    await page.mouse.move(KHUNG.width - 4, KHUNG.height - 4);
    await cho(400);
    return;
  }
  if (loai === "bam" || loai === "go") {
    await page.evaluate(([x, y]) => window.__vd.luotToi(x, y, 600), giua);
    await page.evaluate(() => window.__vd.gon());
    await cho(150);
    await el.click();
    // Chuột THẬT (vô hình) để lại trên thanh bên ⇒ thanh bên mở rộng do hover, đè nội
    // dung và chặn cú bấm sau. Dời nó ra góc màn; người xem chỉ thấy con trỏ giả.
    await page.mouse.move(KHUNG.width - 4, KHUNG.height - 4);
    if (loai === "go") {
      await el.press("ControlOrMeta+a");
      await el.press("Backspace");
      await el.pressSequentially(String(spec.chu), { delay: 60 });
    }
    await cho(350);
    await choManYen(page, canh);
    return;
  }
  throw new LoiCanh(canh, i + 1, `không biết bước "${loai}".`);
}

/**
 * Quay một chương. `tieng`: [{id, loi, giay}] đã đo — phần tử đầu là lời thẻ mở (`_mo`),
 * cuối là lời thẻ kết (`_ket`), giữa là từng cảnh theo thứ tự `chuong.canh`.
 * Trả { video, moc } — moc.canh[i] = {id, tu, den, giay_tieng, tran} cùng thứ tự `tieng`
 * (giây, gốc = đầu tệp quay); moc.bat_dau = lúc thẻ mở hiện (đầu video ra).
 */
export async function quayChuong(chuong, tieng, { ai, thuMuc, duongDau }) {
  const tMo = tieng[0];
  const tKet = tieng.at(-1);
  const tCanh = tieng.slice(1, -1);
  const cam = chuong.cam_tren_man ?? [];
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  try {
    const trangThai = await dangNhap(browser, ai);
    const ctx = await browser.newContext({
      viewport: KHUNG,
      deviceScaleFactor: 1,
      storageState: trangThai,
      locale: "vi-VN",
      timezoneId: "Asia/Ho_Chi_Minh",
    });
    await ctx.addInitScript(LOP);
    const page = await ctx.newPage();
    const t0 = Date.now();
    const giay = () => (Date.now() - t0) / 1000;

    // Thẻ mở: phủ kín trong lúc trang tải ⇒ không lọt cảnh "Đang tải…" vào hình.
    await page.goto(`${CAU_HINH.web}${duongDau}`, { waitUntil: "domcontentloaded" });
    await page.evaluate(([so, ten, phu]) => window.__vd.the(so, ten, phu), [
      `Chương ${chuong.chuong}`,
      chuong.ten,
      `Dành cho: ${chuong.vai}`,
    ]);
    await cho(400);
    // Bắt đầu ghi SAU khi trang đã vẽ thẻ mở (đo cửa sổ cần một khung thật); đầu video =
    // ngay sau lúc ghi chạy ⇒ tiếng (adelay tính từ mốc này) và hình cùng gốc.
    const ghi = await batDauGhi(ctx, page, thuMuc, t0);
    await cho(150);
    const moDau = giay();
    await choManYen(page, "mở đầu", 20);
    await page.evaluate(() => window.__vd.datViTri(window.innerWidth * 0.6, window.innerHeight * 0.55));
    await cho(Math.max(0, (moDau + Math.max(3, tMo.giay + NGHI_SAU_TIENG) - giay()) * 1000));
    await page.evaluate(() => window.__vd.anThe());
    await cho(450);
    await kiemLoi(page, "mở đầu", cam);
    const canh = [{ id: tMo.id, tu: moDau, den: giay(), giay_tieng: tMo.giay, tran: 0 }];

    for (const [i, c] of chuong.canh.entries()) {
      const t = tCanh[i];
      if (c.mo) {
        // `mo: "/duong"` ở cấp CẢNH: mở thẳng màn không có mục trên thanh bên (vd Hàng chờ
        // xác nhận kết quả) TRƯỚC khi hiện phụ đề — đổi trang giữa cảnh làm mất phụ đề.
        await page.goto(`${CAU_HINH.web}${c.mo}`, { waitUntil: "domcontentloaded" });
        await cho(800);
        await choManYen(page, c.id);
      }
      const tu = giay();
      const pd = mocPhuDe(t.loi, t.giay).map((m) => ({ chu: m.chu, sau_ms: Math.round(m.tu * 1000) }));
      pd.push({ chu: "", sau_ms: Math.round(t.giay * 1000) + 150 });
      await page.evaluate((d) => window.__vd.phuDe(d), pd);
      for (const [j, b] of (c.lam ?? []).entries()) await lamBuoc(page, c.id, j, b);
      const conLai = tu + t.giay + NGHI_SAU_TIENG - giay();
      if (conLai > 0) await cho(conLai * 1000);
      await kiemLoi(page, c.id, cam);
      canh.push({ id: c.id, tu, den: giay(), giay_tieng: t.giay, tran: Math.max(0, -conLai) });
    }

    // Thẻ kết (có lời).
    const ket = giay();
    await page.evaluate((phu) => window.__vd.the("", "Xong.", phu), chuong.ket_thuc ?? "");
    await cho(Math.max(2, tKet.giay + NGHI_SAU_TIENG) * 1000);
    const het = giay();
    canh.push({ id: tKet.id, tu: ket, den: het, giay_tieng: tKet.giay, tran: 0 });
    const video = await ghi.dung(moDau, het);
    await ctx.close();
    const tre = ghi.treKhung(canh.slice(1, -1).map((c) => c.tu));
    return {
      video,
      moc: { bat_dau: moDau, canh, ket, het, so_khung: ghi.soKhung(), khung_bo: ghi.saiCo(), tre_khung: tre },
    };
  } finally {
    await browser.close();
  }
}
