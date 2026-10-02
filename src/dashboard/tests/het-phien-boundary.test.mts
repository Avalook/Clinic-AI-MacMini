// Phiên đăng nhập chết (đêm nạp lại staging xoá auth.sessions) → về /login có
// lời giải thích, không để người dùng kẹt. Xem lib/het-phien.ts.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  cookiePhienCanXoa,
  DUONG_DANG_NHAP_HET_PHIEN,
  nenVeDangNhapKhiGap401,
  phanLoaiKhongCoNguoiDung,
} from "../lib/het-phien.ts";

const doc = (f: string) => readFileSync(new URL(f, import.meta.url), "utf8");

test("có cookie phiên mà không ra người dùng → het_phien (xoá cookie + báo)", () => {
  const refreshMat = { name: "AuthApiError", status: 400 };
  assert.equal(phanLoaiKhongCoNguoiDung(refreshMat, true), "het_phien");
  assert.equal(phanLoaiKhongCoNguoiDung({ name: "AuthSessionMissingError", status: 400 }, true), "het_phien");
  assert.equal(phanLoaiKhongCoNguoiDung(null, true), "het_phien");
});

test("chưa có cookie → chỉ về /login, không báo hết phiên", () => {
  assert.equal(phanLoaiKhongCoNguoiDung({ name: "AuthSessionMissingError" }, false), "chua_dang_nhap");
});

test("lỗi tạm thời (mạng / GoTrue bận) KHÔNG bị coi là phiên chết", () => {
  assert.equal(phanLoaiKhongCoNguoiDung({ name: "AuthRetryableFetchError", status: 0 }, true), "chua_dang_nhap");
  assert.equal(phanLoaiKhongCoNguoiDung({ name: "AuthApiError", status: 503 }, true), "chua_dang_nhap");
});

test("chỉ xoá cookie phiên (kể cả mảnh .0 .1), không đụng cookie khác", () => {
  const ten = ["clinicai-auth", "clinicai-auth.0", "clinicai-auth.1", "clinicai-auth-code-verifier", "clinicai-auth-8080", "khac"];
  assert.deepEqual(cookiePhienCanXoa(ten, "clinicai-auth"), [
    "clinicai-auth", "clinicai-auth.0", "clinicai-auth.1", "clinicai-auth-code-verifier",
  ]);
  // staging đặt tên có hậu tố cổng — không xoá nhầm cookie của môi trường khác
  assert.deepEqual(cookiePhienCanXoa(ten, "clinicai-auth-8080"), ["clinicai-auth-8080"]);
});

const goc = "https://staging.dr4women.io.vn";
test("401 từ /api của mình → về /login; trừ khi đang ở trang công khai", () => {
  const base = { status: 401, origin: goc, pathnameHienTai: "/thu-ngan" };
  assert.equal(nenVeDangNhapKhiGap401({ ...base, url: "/api/luot-kham" }), true);
  assert.equal(nenVeDangNhapKhiGap401({ ...base, url: `${goc}/api/roster?x=1` }), true);
  for (const p of ["/login", "/forgot-password", "/reset-password", "/auth/callback"])
    assert.equal(nenVeDangNhapKhiGap401({ ...base, url: "/api/luot-kham", pathnameHienTai: p }), false, p);
});

test("không phải 401 / không phải /api của mình / url rác → không chuyển", () => {
  const base = { origin: goc, pathnameHienTai: "/thu-ngan" };
  assert.equal(nenVeDangNhapKhiGap401({ ...base, status: 403, url: "/api/x" }), false);
  assert.equal(nenVeDangNhapKhiGap401({ ...base, status: 500, url: "/api/x" }), false);
  assert.equal(nenVeDangNhapKhiGap401({ ...base, status: 401, url: "https://nguoi-la.example/api/x" }), false);
  assert.equal(nenVeDangNhapKhiGap401({ ...base, status: 401, url: "/thu-ngan" }), false);
  assert.equal(nenVeDangNhapKhiGap401({ ...base, status: 401, url: "http://[bad" }), false);
});

test("nối dây: proxy, layout, trang đăng nhập", () => {
  const proxy = doc("../proxy.ts");
  assert.match(proxy, /phanLoaiKhongCoNguoiDung\(/);
  assert.match(proxy, /maxAge: 0/);
  assert.match(doc("../app/layout.tsx"), /<GacHetPhien \/>/);
  assert.match(doc("../app/(auth)/login/LoginForm.tsx"), /Phiên đăng nhập đã hết — vui lòng đăng nhập lại\./);
  assert.equal(DUONG_DANG_NHAP_HET_PHIEN, "/login?het_phien=1");
});
