// Kiểm phiên tại chỗ (30/09/2026): phiên còn hạn thì KHÔNG hỏi GoTrue; mọi thứ
// khả nghi thì rơi về getUser() gốc. Xem lib/kiem-phien-tai-cho.ts.
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  DU_PHONG_HET_HAN_GIAY,
  ganKiemPhienTaiCho,
  kiemToken,
} from "../lib/kiem-phien-tai-cho.ts";

const BI_MAT = "khoa-thu-chi-dung-trong-test-0123456789";
const b64 = (o: unknown) => Buffer.from(JSON.stringify(o)).toString("base64url");
const bayGio = () => Math.floor(Date.now() / 1000);

function kyToken(
  than: Record<string, unknown>,
  { khoa = BI_MAT, alg = "HS256" }: { khoa?: string; alg?: string } = {},
): string {
  const dau = b64({ alg, typ: "JWT" });
  const t = b64(than);
  const chuKy = createHmac("sha256", khoa).update(`${dau}.${t}`).digest("base64url");
  return `${dau}.${t}.${chuKy}`;
}

const HOP_LE = { sub: "u-1", aud: "authenticated", role: "authenticated", email: "a@b.vn" };

test("token đúng khoá, đúng audience, còn hạn → trả claims", async () => {
  const c = await kiemToken(kyToken({ ...HOP_LE, exp: bayGio() + 3600 }), BI_MAT);
  assert.equal(c?.sub, "u-1");
});

test("mọi token khả nghi → null (để GoTrue quyết)", async () => {
  const exp = bayGio() + 3600;
  const cases: [string, string][] = [
    ["sai khoá", kyToken({ ...HOP_LE, exp }, { khoa: "khoa-khac" })],
    ["alg none", kyToken({ ...HOP_LE, exp }, { alg: "none" })],
    ["sai audience", kyToken({ ...HOP_LE, aud: "anon", exp })],
    ["thiếu sub", kyToken({ aud: "authenticated", exp })],
    ["thiếu exp", kyToken({ ...HOP_LE })],
    ["đã hết hạn", kyToken({ ...HOP_LE, exp: bayGio() - 5 })],
    ["sắp hết hạn", kyToken({ ...HOP_LE, exp: bayGio() + DU_PHONG_HET_HAN_GIAY - 1 })],
    ["chuỗi rác", "khong.phai.jwt"],
    ["rỗng", ""],
  ];
  for (const [ten, tok] of cases) {
    assert.equal(await kiemToken(tok, BI_MAT), null, ten);
  }
  // Sửa thân token mà giữ chữ ký cũ → chữ ký không còn khớp.
  const [d, , k] = kyToken({ ...HOP_LE, exp }).split(".");
  const gia = `${d}.${b64({ ...HOP_LE, sub: "ke-gia", exp })}.${k}`;
  assert.equal(await kiemToken(gia, BI_MAT), null, "thân bị sửa");
});

function clientGia(token: string | null) {
  let goiGoTrue = 0;
  const client = {
    auth: {
      getSession: async () => ({
        data: { session: token ? { access_token: token } : null },
        error: null,
      }),
      getUser: async () => {
        goiGoTrue += 1;
        return { data: { user: { id: "tu-gotrue" } }, error: null };
      },
    },
  };
  return { client, dem: () => goiGoTrue };
}

test("phiên còn hạn → getUser() KHÔNG gọi GoTrue", async () => {
  const { client, dem } = clientGia(kyToken({ ...HOP_LE, exp: bayGio() + 3600 }));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const c = ganKiemPhienTaiCho(client as any, BI_MAT);
  for (let i = 0; i < 5; i++) {
    const { data } = await c.auth.getUser();
    assert.equal(data.user?.id, "u-1");
  }
  assert.equal(dem(), 0);
});

test("hết hạn / không có phiên / truyền jwt → đi đường GoTrue gốc", async () => {
  for (const tok of [kyToken({ ...HOP_LE, exp: bayGio() - 1 }), null]) {
    const { client, dem } = clientGia(tok);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const c = ganKiemPhienTaiCho(client as any, BI_MAT);
    const { data } = await c.auth.getUser();
    assert.equal(data.user?.id, "tu-gotrue");
    assert.equal(dem(), 1);
  }
  const { client, dem } = clientGia(kyToken({ ...HOP_LE, exp: bayGio() + 3600 }));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await ganKiemPhienTaiCho(client as any, BI_MAT).auth.getUser("jwt-truyen-vao");
  assert.equal(dem(), 1);
});

test("thiếu SUPABASE_JWT_SECRET → giữ nguyên hành vi cũ", async () => {
  const { client, dem } = clientGia(kyToken({ ...HOP_LE, exp: bayGio() + 3600 }));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await ganKiemPhienTaiCho(client as any, "").auth.getUser();
  assert.equal(dem(), 1);
});

test("cả hai nơi tạo client phía server đều gắn kiểm tại chỗ", () => {
  for (const f of ["../proxy.ts", "../lib/supabase-server.ts"]) {
    const src = readFileSync(new URL(f, import.meta.url), "utf8");
    assert.match(src, /ganKiemPhienTaiCho\(createServerClient\(/, f);
  }
});
