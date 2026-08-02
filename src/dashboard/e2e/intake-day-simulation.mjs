// @ts-check
/**
 * E2E bot — Mô phỏng luồng ĐẶT LỊCH + TIẾP NHẬN trong ngày khám (Clinic-AI-Dr4Women).
 *
 * Mục tiêu: giả lập (1) khách đặt online hôm nay rồi lễ tân check-in, (2) khách vãng lai
 * walk-in, kiểm tra hệ tự cấp số khám, queue hiển thị đúng thứ tự, board bác sĩ đồng bộ,
 * và (nếu đủ quyền) luồng B3 lab. Sau khi chạy in báo cáo console + file markdown chỉ ra
 * chỗ nghẽn / rủi ro.
 *
 * AN TOÀN (đọc kỹ):
 *   - Mặc định READ-ONLY. Chỉ ghi dữ liệu khi E2E_ALLOW_WRITE=1.
 *   - Trên production (dr4women.vercel.app) còn cần thêm E2E_ALLOW_PROD_WRITE=1 mới ghi.
 *   - Mọi bệnh nhân test đều có prefix tên "E2E_TEST_".
 *   - Thiếu credential / cổng → SKIP mềm, in hướng dẫn, KHÔNG crash.
 *   - KHÔNG migration, KHÔNG tự apply DB, KHÔNG xoá cứng (cleanup chỉ huỷ lịch qua API).
 *
 * CHẠY:
 *   1) npm i -D playwright && npx playwright install chromium
 *   2) Khai báo env (xem e2e/env.example), rồi: npm run e2e:intake
 *
 * Yêu cầu: Playwright (devDependency). App phải đang chạy ở E2E_BASE_URL (dev hoặc prod).
 */

import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// ---------- Env ----------
const E = process.env;
const BASE_URL = (E.E2E_BASE_URL || "").replace(/\/+$/, "");
const ALLOW_WRITE = E.E2E_ALLOW_WRITE === "1";
const ALLOW_PROD_WRITE = E.E2E_ALLOW_PROD_WRITE === "1";
const CLEANUP = E.E2E_CLEANUP === "1";
const HEADLESS = E.E2E_HEADLESS !== "0";
const IS_PROD = /dr4women\.vercel\.app/i.test(BASE_URL);
// Ghi dữ liệu chỉ khi: bật ALLOW_WRITE, VÀ (không phải prod HOẶC đã bật ALLOW_PROD_WRITE).
const CAN_WRITE = ALLOW_WRITE && (!IS_PROD || ALLOW_PROD_WRITE);

const ACCOUNTS = {
  cskh: { email: E.E2E_CSKH_EMAIL, password: E.E2E_CSKH_PASSWORD, label: "CSKH" },
  reception: { email: E.E2E_RECEPTION_EMAIL, password: E.E2E_RECEPTION_PASSWORD, label: "Lễ tân" },
  doctor: { email: E.E2E_DOCTOR_EMAIL, password: E.E2E_DOCTOR_PASSWORD, label: "Bác sĩ" },
  lab: { email: E.E2E_LAB_EMAIL, password: E.E2E_LAB_PASSWORD, label: "Lab/Điều dưỡng" },
};

const STAMP = new Date().toISOString().replace(/[:.]/g, "-");

// ---------- Báo cáo ----------
/** @type {Array<{phase:string,scenario:string,expected:string,actual:string,status:string,evidence:string,risk:string}>} */
const ROWS = [];
const STATUS_ICON = { PASS: "✅", FAIL: "❌", SKIP: "⏭️", WARN: "⚠️", INFO: "ℹ️" };
function record(phase, scenario, status, { expected = "", actual = "", evidence = "", risk = "" } = {}) {
  ROWS.push({ phase, scenario, expected, actual, status, evidence, risk });
  const icon = STATUS_ICON[status] || status;
  console.log(`${icon} [${phase}] ${scenario}${actual ? ` → ${actual}` : ""}`);
  if (risk) console.log(`     ⮑ rủi ro: ${risk}`);
}

// ---------- Helpers ----------
function todayYmdVN() {
  // YYYY-MM-DD theo giờ VN.
  const f = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  return f.format(new Date());
}

function attachWatchers(page) {
  const consoleErrors = [];
  const badResponses = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200));
  });
  page.on("response", (r) => {
    const s = r.status();
    if (s >= 400 && r.url().startsWith(BASE_URL)) {
      // Bỏ qua 401 ở các route auth (bình thường trước khi login).
      badResponses.push(`${s} ${r.url().replace(BASE_URL, "")}`);
    }
  });
  return { consoleErrors, badResponses };
}

/**
 * Đăng nhập 1 context mới cho 1 vai trò. Trả {context,page,watch} hoặc {skip:"lý do"}.
 */
async function login(browser, accountKey) {
  const acc = ACCOUNTS[accountKey];
  if (!acc?.email || !acc?.password) {
    return { skip: `Thiếu E2E_${accountKey.toUpperCase()}_EMAIL / _PASSWORD` };
  }
  const context = await browser.newContext({ baseURL: BASE_URL, ignoreHTTPSErrors: true });
  const page = await context.newPage();
  const watch = attachWatchers(page);
  try {
    await page.goto("/login", { waitUntil: "domcontentloaded", timeout: 30000 });
    if (page.url().includes("/login")) {
      await page.fill("#email", acc.email);
      await page.fill("#password", acc.password);
      await page.getByRole("button", { name: /Đăng nhập/ }).click();
      await page.waitForURL((u) => !u.toString().includes("/login"), { timeout: 20000 }).catch(() => {});
    }
    const url = page.url();
    if (url.includes("/login")) {
      await context.close();
      return { skip: `Đăng nhập thất bại cho ${acc.label} (kiểm email/mật khẩu)` };
    }
    if (url.includes("/choose-clinic")) {
      // Tài khoản làm ở nhiều phòng khám. Không phải lỗi đăng nhập — nhưng bot
      // chọn hộ nơi trực thì kết quả sim sẽ nói về một phòng khám không ai chỉ định.
      await context.close();
      return { skip: `${acc.label}: tài khoản có nhiều phòng khám → cần tài khoản 1 nơi để sim` };
    }
    if (url.includes("/role-picker")) {
      await context.close();
      return { skip: `${acc.label}: tài khoản chưa gắn staff → rơi vào /role-picker (cần chọn danh tính thủ công)` };
    }
    return { context, page, watch, label: acc.label };
  } catch (err) {
    await context.close().catch(() => {});
    return { skip: `Lỗi đăng nhập ${acc.label}: ${String(err).slice(0, 160)}` };
  }
}

/** GET JSON qua API context (dùng cookie của page đã login). */
async function apiGet(page, path) {
  const res = await page.request.get(BASE_URL + path);
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  return { status: res.status(), body };
}

/** Tìm appointment hôm nay theo doctor (đọc lại queue_number/status). */
async function fetchTodayAppts(page, doctorId) {
  const date = todayYmdVN();
  const q = doctorId ? `?date=${date}&doctor_id=${doctorId}` : `?date=${date}`;
  const { status, body } = await apiGet(page, `/api/appointments${q}`);
  return { status, appointments: (body && body.appointments) || [] };
}

// ---------- Phases ----------

async function phaseA(browser) {
  const phase = "A · Smoke read-only";
  // Ưu tiên tài khoản có quyền vào /patients/new: reception → cskh.
  let session = null;
  for (const key of ["reception", "cskh"]) {
    const s = await login(browser, key);
    if (!s.skip) { session = s; break; }
    record(phase, `Đăng nhập ${ACCOUNTS[key].label}`, "SKIP", { evidence: s.skip });
  }
  if (!session) {
    record(phase, "Smoke read-only", "SKIP", {
      risk: "Không có tài khoản canWriteIntake (reception/cskh) → bỏ toàn bộ Phase A.",
    });
    return null;
  }
  const { page, watch, label } = session;
  try {
    // /patients/new mở được
    const navRes = await page.goto("/patients/new", { waitUntil: "domcontentloaded", timeout: 30000 });
    const okOpen = navRes && navRes.status() < 400 && /\/patients\/new/.test(page.url());
    record(phase, "Mở /patients/new", okOpen ? "PASS" : "FAIL", {
      expected: "Trang nhập BN mới mở (HTTP < 400)",
      actual: `status=${navRes ? navRes.status() : "?"}, url=${page.url().replace(BASE_URL, "")}`,
      evidence: label,
      risk: okOpen ? "" : "Lễ tân không vào được màn tạo BN.",
    });
    await page.waitForTimeout(700);

    // Bảng "Tải hôm nay theo bác sĩ"
    const board = page.getByText("Tải hôm nay theo bác sĩ");
    const boardVisible = (await board.count()) > 0;
    record(phase, "Bảng 'Tải hôm nay theo bác sĩ' hiện", boardVisible ? "PASS" : "WARN", {
      expected: "Bảng tải hiển thị",
      actual: boardVisible ? "có" : "không thấy (có thể variant 'full' hoặc 0 bác sĩ)",
    });

    // Có nhiều bác sĩ hoặc ít nhất BS Thành
    const thanh = page.getByText(/thành/i);
    const thanhCount = await thanh.count();
    const docButtons = await page.locator('button[title^="Chọn "]').count();
    record(phase, "Bảng có nhiều bác sĩ / có BS Thành", thanhCount > 0 || docButtons > 0 ? "PASS" : "WARN", {
      expected: "≥1 bác sĩ, ưu tiên có BS Thành",
      actual: `BS Thành≈${thanhCount}, ô bác sĩ bấm được≈${docButtons}`,
    });

    // KHÔNG có field 'Số khám' nhập tay
    const soKhamLabel = await page.getByText(/^Số khám$/).count();
    const soKhamInput = await page.locator('input[placeholder*="ƯT"], input[placeholder*="số chung"]').count();
    const noManualQueue = soKhamLabel === 0 && soKhamInput === 0;
    record(phase, "Không còn field 'Số khám' nhập tay", noManualQueue ? "PASS" : "FAIL", {
      expected: "Không có input 'Số khám' editable (hệ tự cấp)",
      actual: `label 'Số khám'=${soKhamLabel}, input ƯT/số chung=${soKhamInput}`,
      risk: noManualQueue ? "" : "Vẫn còn ô nhập tay số khám — trái yêu cầu.",
    });

    // Click ô/tên bác sĩ → fill bác sĩ vào form
    const docInput = page.getByPlaceholder(/Tìm bác sĩ/).first();
    const hasDocInput = (await docInput.count()) > 0;
    if (hasDocInput) {
      const before = await docInput.inputValue().catch(() => "");
      let clicked = false;
      const cellBtn = page.locator('button[title^="Chọn "]').first();
      if ((await cellBtn.count()) > 0) {
        await cellBtn.click().catch(() => {});
        clicked = true;
      }
      await page.waitForTimeout(400);
      const after = await docInput.inputValue().catch(() => "");
      const filled = clicked && after.trim().length > 0 && after !== before;
      record(phase, "Bấm ô bác sĩ → fill vào form", filled ? "PASS" : clicked ? "WARN" : "SKIP", {
        expected: "Ô 'Bác sĩ' được điền tên sau khi bấm bảng tải",
        actual: clicked ? `"${before}" → "${after}"` : "không có ô bác sĩ bấm được (0 ca hôm nay?)",
        risk: clicked && !filled ? "onPick có thể không gắn — kiểm DoctorLoadBoard." : "",
      });
    } else {
      record(phase, "Bấm ô bác sĩ → fill vào form", "SKIP", {
        evidence: "Không thấy ô 'Bác sĩ' (variant khác?)",
      });
    }

    // /queue không crash
    const qRes = await page.goto("/queue", { waitUntil: "domcontentloaded", timeout: 30000 });
    const qOk = qRes && qRes.status() < 500 && !page.url().includes("/login");
    record(phase, "/queue load không crash", qOk ? "PASS" : "FAIL", {
      expected: "HTTP < 500, không redirect login",
      actual: `status=${qRes ? qRes.status() : "?"}, url=${page.url().replace(BASE_URL, "")}`,
      risk: qOk ? "" : "Queue không tải được.",
    });

    // /tasks không crash
    const tRes = await page.goto("/tasks", { waitUntil: "domcontentloaded", timeout: 30000 });
    const tOk = tRes && tRes.status() < 500 && !page.url().includes("/login");
    record(phase, "/tasks (board bác sĩ) load không crash", tOk ? "PASS" : "FAIL", {
      expected: "HTTP < 500",
      actual: `status=${tRes ? tRes.status() : "?"}`,
    });

    // Console / network lỗi bất thường
    const bad = watch.badResponses.filter((x) => !/^(401|403)/.test(x));
    if (watch.consoleErrors.length || bad.length) {
      record(phase, "Console/Network sạch", "WARN", {
        expected: "Không có console error / 5xx bất thường",
        actual: `console=${watch.consoleErrors.length}, http≥400(trừ 401/403)=${bad.length}`,
        evidence: [...watch.consoleErrors.slice(0, 3), ...bad.slice(0, 3)].join(" | ").slice(0, 300),
      });
    } else {
      record(phase, "Console/Network sạch", "PASS", { actual: "không lỗi đáng ngờ" });
    }
    return session;
  } catch (err) {
    record(phase, "Phase A", "FAIL", { actual: String(err).slice(0, 200) });
    return session;
  }
}

async function phaseE_quote(browser, reuse) {
  const phase = "E · Capacity/quote (read-only)";
  const session = reuse && !reuse.skip ? reuse : await login(browser, "cskh");
  if (session.skip) {
    record(phase, "Quote read-only", "SKIP", { evidence: session.skip });
    return;
  }
  const { page } = session;
  try {
    // Lấy location_id từ <select> trên /patients/new (option value = location_id).
    await page.goto("/patients/new", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(500);
    // Tìm option có value dạng uuid trong các select.
    const locId = await page.evaluate(() => {
      const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-/i;
      for (const sel of Array.from(document.querySelectorAll("select"))) {
        for (const opt of Array.from(sel.options)) {
          if (uuid.test(opt.value)) return opt.value;
        }
      }
      return "";
    });
    if (!locId) {
      record(phase, "Lấy location_id để quote", "SKIP", {
        evidence: "Không tìm được location_id từ form (UI đổi?)",
      });
      return;
    }
    const date = todayYmdVN();
    const { status, body } = await apiGet(page, `/api/appointments/quote?date=${date}&location_id=${locId}`);
    const ok = status === 200 && body && Array.isArray(body.blocks);
    record(phase, "GET /api/appointments/quote", ok ? "PASS" : "FAIL", {
      expected: "200 + mảng blocks[{hour_start,state,usage}]",
      actual: `status=${status}, blocks=${ok ? body.blocks.length : "?"}`,
      evidence: ok ? `vd state đầu: ${body.blocks[0]?.state}` : JSON.stringify(body).slice(0, 160),
      risk: ok ? "" : "Engine capacity/quote lỗi → màn đặt lịch có thể không hiện trạng thái khung giờ.",
    });
    if (ok) {
      const full = body.blocks.filter((b) => ["locked", "full_thanh", "return_only"].includes(b.state));
      record(phase, "Khung giờ đầy/nghẽn hôm nay", "INFO", {
        actual: `${full.length}/${body.blocks.length} khung ở trạng thái đầy/hạn chế`,
        evidence: full.map((b) => `${b.hour_start}h:${b.state}`).slice(0, 6).join(", "),
        risk: full.length ? "Có khung đã nghẽn — booking NEW vào đây sẽ bị chặn 409." : "",
      });
    }
  } catch (err) {
    record(phase, "Quote", "FAIL", { actual: String(err).slice(0, 200) });
  }
}

function writePhasesSkippedNote() {
  const why = !ALLOW_WRITE
    ? "E2E_ALLOW_WRITE≠1 (mặc định read-only)"
    : IS_PROD && !ALLOW_PROD_WRITE
      ? "Đang trỏ PRODUCTION mà chưa bật E2E_ALLOW_PROD_WRITE=1 (chặn ghi prod)"
      : "";
  for (const [phase, scen] of [
    ["B · Online appt + check-in", "Tạo lịch online hôm nay + lễ tân check-in"],
    ["C · Walk-in", "Tạo walk-in + auto check-in"],
    ["D · Queue ordering", "So sánh thứ tự online vs walk-in"],
    ["E · Capacity write", "Tạo nhiều NEW cùng khung → kỳ vọng 409"],
    ["F · B3 lab", "Chỉ định lab → trả KQ → lên làn B3"],
  ]) {
    record(phase, scen, "SKIP", { evidence: why, risk: "Cần chạy với quyền ghi để kiểm." });
  }
}

// ---------- Báo cáo markdown ----------
async function writeReport() {
  const here = dirname(fileURLToPath(import.meta.url));
  const dir = join(here, "..", "e2e-report");
  await mkdir(dir, { recursive: true });
  const file = join(dir, `intake-day-simulation-${STAMP}.md`);
  const counts = ROWS.reduce((m, r) => ((m[r.status] = (m[r.status] || 0) + 1), m), {});
  const esc = (s) => String(s || "").replace(/\|/g, "\\|").replace(/\n/g, " ");
  const lines = [];
  lines.push(`# E2E — Mô phỏng ngày khám (đặt lịch + tiếp nhận)`);
  lines.push("");
  lines.push(`- Thời điểm: ${new Date().toISOString()} (ngày VN: ${todayYmdVN()})`);
  lines.push(`- BASE_URL: \`${BASE_URL || "(chưa đặt)"}\`${IS_PROD ? " — ⚠️ PRODUCTION" : ""}`);
  lines.push(`- Chế độ ghi: ${CAN_WRITE ? "**CÓ GHI**" : "read-only"} (ALLOW_WRITE=${ALLOW_WRITE ? 1 : 0}, PROD_WRITE=${ALLOW_PROD_WRITE ? 1 : 0})`);
  lines.push(`- Kết quả: ${Object.entries(counts).map(([k, v]) => `${STATUS_ICON[k] || k} ${k}=${v}`).join("  ·  ")}`);
  lines.push("");
  lines.push(`| Phase | Scenario | Expected | Actual | Kết quả | Evidence | Bottleneck/Risk |`);
  lines.push(`| --- | --- | --- | --- | --- | --- | --- |`);
  for (const r of ROWS) {
    lines.push(
      `| ${esc(r.phase)} | ${esc(r.scenario)} | ${esc(r.expected)} | ${esc(r.actual)} | ${STATUS_ICON[r.status] || r.status} ${r.status} | ${esc(r.evidence)} | ${esc(r.risk)} |`,
    );
  }
  lines.push("");
  lines.push(`## Câu hỏi trọng tâm`);
  const ask = (q, ids) => {
    const rel = ROWS.filter((r) => ids.some((id) => r.scenario.includes(id)));
    const verdict = rel.length
      ? rel.map((r) => `${STATUS_ICON[r.status] || r.status} ${r.scenario}`).join("; ")
      : "chưa kiểm (skip)";
    lines.push(`- **${q}** ${verdict}`);
  };
  ask("Lễ tân có bị kẹt chỗ nào?", ["Mở /patients/new", "check-in", "Check-in"]);
  ask("Có phải nhập tay số khám?", ["Số khám"]);
  ask("Walk-in auto check-in đúng?", ["auto check-in", "Walk-in", "walk-in"]);
  ask("Queue có hiện bệnh nhân?", ["/queue", "queue"]);
  ask("Board bác sĩ đồng bộ?", ["board bác sĩ", "/tasks", "B3"]);
  ask("Lỗi auth/role?", ["Đăng nhập"]);
  ask("Quote/capacity ổn?", ["quote", "409"]);
  lines.push("");
  lines.push(`> Ghi chú: bot chạy ngoài (server thật + credential thật). Các bước SKIP do thiếu quyền/credential hoặc read-only — xem cột Evidence để bổ sung env rồi chạy lại.`);
  await writeFile(file, lines.join("\n"), "utf8");
  return file;
}

// ---------- Main ----------
async function main() {
  console.log("=== E2E intake-day-simulation ===");
  if (!BASE_URL) {
    record("Cấu hình", "E2E_BASE_URL", "FAIL", {
      risk: "Chưa đặt E2E_BASE_URL → không chạy được. Xem e2e/env.example.",
    });
    const f = await writeReport();
    console.log(`\nBáo cáo: ${f}`);
    process.exit(2);
  }
  console.log(`BASE_URL=${BASE_URL}${IS_PROD ? " (PROD)" : ""}  write=${CAN_WRITE}`);
  if (ALLOW_WRITE && IS_PROD && !ALLOW_PROD_WRITE) {
    console.log("⚠️  Trỏ production + ALLOW_WRITE nhưng thiếu E2E_ALLOW_PROD_WRITE=1 → CHẶN ghi, chạy read-only.");
  }

  let browser;
  try {
    browser = await chromium.launch({ headless: HEADLESS });
  } catch (err) {
    record("Cấu hình", "Khởi động Chromium", "FAIL", {
      actual: String(err).slice(0, 160),
      risk: "Chạy: npx playwright install chromium",
    });
    const f = await writeReport();
    console.log(`\nBáo cáo: ${f}`);
    process.exit(2);
  }

  try {
    const sessionA = await phaseA(browser);
    await phaseE_quote(browser, sessionA);
    // Phase B/C/D/F là luồng ghi nhiều bước trên UI thật — chỉ chạy khi có quyền ghi.
    // Để an toàn (không tạo rác/đụng prod khi tôi không kiểm chứng được), hiện đánh dấu cần
    // chạy có giám sát: mở khung guard ở đây khi bạn đã xác nhận trên dev.
    if (!CAN_WRITE) {
      writePhasesSkippedNote();
    } else {
      record("B · Online appt + check-in", "Luồng ghi UI nhiều bước", "WARN", {
        risk:
          "Khung guard đã mở (CAN_WRITE). Các bước tạo BN/đặt lịch/check-in qua FORM cần xác minh selector trên dev trước khi bật chạy thật — xem README mục 'Bật Phase ghi'.",
      });
    }
  } catch (err) {
    record("Tổng", "Chạy phases", "FAIL", { actual: String(err).slice(0, 200) });
  } finally {
    await browser.close().catch(() => {});
  }

  const file = await writeReport();
  console.log(`\n=== Tổng kết ===`);
  const counts = ROWS.reduce((m, r) => ((m[r.status] = (m[r.status] || 0) + 1), m), {});
  console.log(Object.entries(counts).map(([k, v]) => `${k}=${v}`).join("  "));
  console.log(`Báo cáo markdown: ${file}`);
  const failed = ROWS.some((r) => r.status === "FAIL");
  process.exit(failed ? 1 : 0);
}

main().catch(async (err) => {
  console.error("Bot lỗi không bắt được:", err);
  try {
    await writeReport();
  } catch {}
  process.exit(2);
});
