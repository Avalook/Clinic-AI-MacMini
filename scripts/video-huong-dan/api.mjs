// Gọi API của app trên STACK LOCAL bằng tài khoản thử `*@dr4women.local` — cho script
// dựng dữ liệu video. Chỉ chạy được với địa chỉ loopback (không bao giờ staging/prod).
//
// Khoá Supabase local đọc từ `.env.thu-local` (của cây này, hoặc của bản checkout chính
// khi chạy trong worktree — giống scripts/dev-giao-dien.sh). Mật khẩu chung của tài khoản
// GIẢ và khoá API local lấy đúng mặc định của scripts/dev-up.sh (ghi đè được qua env).

import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";

export const REPO = join(dirname(new URL(import.meta.url).pathname), "..", "..");

function docEnvThu() {
  let tep = join(REPO, ".env.thu-local");
  if (!existsSync(tep)) {
    const chung = execFileSync("git", ["-C", REPO, "rev-parse", "--path-format=absolute", "--git-common-dir"])
      .toString()
      .trim();
    tep = join(dirname(chung), ".env.thu-local");
  }
  if (!existsSync(tep)) throw new Error("Thiếu .env.thu-local — chạy scripts/dev-up.sh trước.");
  const env = {};
  for (const dong of readFileSync(tep, "utf8").split("\n")) {
    const m = dong.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
  return env;
}

export const ENV = docEnvThu();
//: Thư mục tệp kết quả của stack quay video — API và `gmail_gia.py` phải dùng CÙNG nơi
//: (MEDIA_ROOT / MEDIA_LOCAL_ROOT) thì hộp xem mới mở được tờ email giả.
export const THU_MUC_TEP = process.env.VIDEO_MEDIA_DIR ?? join(process.env.HOME ?? "/tmp", "ClinicAI-video", "media");
export const CAU_HINH = {
  web: process.env.VIDEO_WEB_URL ?? "http://127.0.0.1:3100",
  api: process.env.VIDEO_API_URL ?? `http://127.0.0.1:${process.env.API_PORT ?? 8100}`,
  supabase: `http://127.0.0.1:${ENV.SUPABASE_API_PORT ?? 54421}`,
  anon: ENV.SUPABASE_ANON_KEY,
  matKhau: process.env.TEST_PW ?? "clinic-test-pw-123",
  khoaApi: process.env.BACKEND_API_KEY ?? "staging-local-api-key",
};

for (const u of [CAU_HINH.web, CAU_HINH.api, CAU_HINH.supabase]) {
  const h = new URL(u).hostname;
  if (!["127.0.0.1", "localhost", "::1", "[::1]"].includes(h)) {
    throw new Error(`Chỉ quay trên stack local — ${u} không phải loopback.`);
  }
}

export const email = (ten) => `${ten}@dr4women.local`;

const token = new Map();

async function dangNhap(ten) {
  if (token.has(ten)) return token.get(ten);
  const r = await fetch(`${CAU_HINH.supabase}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: CAU_HINH.anon, "Content-Type": "application/json" },
    body: JSON.stringify({ email: email(ten), password: CAU_HINH.matKhau }),
  });
  if (!r.ok) throw new Error(`Đăng nhập ${email(ten)} hỏng (HTTP ${r.status}).`);
  const t = (await r.json()).access_token;
  token.set(ten, t);
  return t;
}

/** Gọi `/api/v1/<duong>` bằng tài khoản `ai`. Lỗi ⇒ ném kèm câu máy chủ trả. */
export async function goi(ai, method, duong, body, { idem = false, choPhep = [] } = {}) {
  const headers = {
    Authorization: `Bearer ${await dangNhap(ai)}`,
    "X-API-Key": CAU_HINH.khoaApi,
    "Content-Type": "application/json",
  };
  if (idem) headers["Idempotency-Key"] = randomUUID();
  const r = await fetch(`${CAU_HINH.api}/api/v1/${duong}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const chu = await r.text();
  let d = null;
  try {
    d = chu ? JSON.parse(chu) : null;
  } catch {
    d = chu;
  }
  if (!r.ok && !choPhep.includes(r.status)) {
    const cau = typeof d === "object" && d ? (d.detail?.message ?? d.detail ?? d.message ?? chu) : chu;
    throw new Error(`${method} /api/v1/${duong} (${ai}) → HTTP ${r.status}: ${JSON.stringify(cau).slice(0, 300)}`);
  }
  return d;
}

export const cho = (ms) => new Promise((r) => setTimeout(r, ms));
