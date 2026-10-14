import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  CUA_SO_MS,
  khoaLoi,
  TRAN_MOI_PHUT,
  taoBaoLoi,
  type GoiLoi,
} from "../lib/bao-loi-trinh-duyet.ts";

function taoMoiTruong() {
  let bay = 1_000_000;
  const guiRa: GoiLoi[] = [];
  const hens: Array<{ luc: number; fn: () => void }> = [];
  return {
    guiRa,
    cong: {
      gui: async (g: GoiLoi) => {
        guiRa.push(g);
      },
      bayGio: () => bay,
      hen: (fn: () => void, ms: number) => {
        hens.push({ luc: bay + ms, fn });
        return hens.length;
      },
    },
    tien: (ms: number) => {
      bay += ms;
      for (const h of hens.filter((x) => x.luc <= bay)) {
        hens.splice(hens.indexOf(h), 1);
        h.fn();
      }
    },
  };
}

const loi = (thong_diep = "Máy chủ bận", vi_tri = "/ban-kham"): GoiLoi => ({
  vi_tri,
  kieu: "Error",
  thong_diep,
});

test("cùng một lỗi lặp 500 lần: gửi ĐÚNG MỘT lần, 499 lần được đếm", () => {
  const m = taoMoiTruong();
  const bao = taoBaoLoi(m.cong);
  const kq = Array.from({ length: 500 }, () => bao(loi()));
  assert.equal(kq.filter((k) => k === "gui").length, 1);
  assert.equal(kq.filter((k) => k === "trung").length, 499);
  assert.equal(m.guiRa.length, 1);
  assert.equal(m.guiRa[0]!.thong_diep, "Máy chủ bận", "lần đầu gửi nguyên văn");
});

test("KHÔNG nuốt: hết cửa sổ gửi MỘT bản tóm tắt có số lần lặp", () => {
  const m = taoMoiTruong();
  const bao = taoBaoLoi(m.cong);
  for (let i = 0; i < 40; i++) bao(loi());
  m.tien(CUA_SO_MS);
  assert.equal(m.guiRa.length, 2);
  assert.match(m.guiRa[1]!.thong_diep, /lặp thêm 39 lần trong 5 phút/);
  assert.match(m.guiRa[1]!.thong_diep, /^Máy chủ bận/);
});

test("lỗi KHÔNG lặp: không có bản tóm tắt thừa", () => {
  const m = taoMoiTruong();
  const bao = taoBaoLoi(m.cong);
  bao(loi());
  m.tien(CUA_SO_MS * 3);
  assert.equal(m.guiRa.length, 1);
});

test("sau khi hết cửa sổ, lỗi ấy lại được gửi như lỗi mới", () => {
  const m = taoMoiTruong();
  const bao = taoBaoLoi(m.cong);
  assert.equal(bao(loi()), "gui");
  m.tien(CUA_SO_MS + 1);
  assert.equal(bao(loi()), "gui");
  assert.equal(m.guiRa.length, 2);
});

test("lỗi KHÁC nhau không che nhau", () => {
  const m = taoMoiTruong();
  const bao = taoBaoLoi(m.cong);
  assert.equal(bao(loi("Lỗi A")), "gui");
  assert.equal(bao(loi("Lỗi B")), "gui");
  assert.equal(bao(loi("Lỗi A", "/phong/x")), "gui", "cùng thông điệp nhưng khác màn là lỗi khác");
  assert.equal(bao({ ...loi("Lỗi A"), kieu: "TypeError" }), "gui");
});

test("phần đổi theo từng lần (digest, uuid, con số) không làm một lỗi thành nhiều", () => {
  const a = khoaLoi(loi("Không đọc được (digest 1234567890)"));
  const b = khoaLoi(loi("Không đọc được (digest 9876543210)"));
  assert.equal(a, b);
  assert.equal(
    khoaLoi(loi("Khách 3f2c9a10-1111-4222-8333-444455556666 lỗi sau 1532 ms")),
    khoaLoi(loi("Khách aaaaaaaa-1111-4222-8333-444455556666 lỗi sau 87 ms")),
  );
});

test("trần chung: nhiều lỗi KHÁC nhau liên tục cũng không đổ quá mức mỗi phút", () => {
  const m = taoMoiTruong();
  const bao = taoBaoLoi(m.cong);
  const kq = Array.from({ length: 30 }, (_, i) => bao(loi(`Lỗi riêng số lẻ ${"x".repeat(i + 1)}`)));
  assert.equal(m.guiRa.length, TRAN_MOI_PHUT);
  assert.equal(kq.filter((k) => k === "tran").length, 30 - TRAN_MOI_PHUT);
});

test("lượt vượt trần được ĐẾM và cộng vào lần gửi kế tiếp", () => {
  const m = taoMoiTruong();
  const bao = taoBaoLoi(m.cong);
  for (let i = 0; i < TRAN_MOI_PHUT + 4; i++) bao(loi(`khác ${"x".repeat(i + 1)}`));
  m.tien(61_000); // hết cửa sổ trần một phút
  assert.equal(bao(loi("Lỗi mới sau đợt tràn")), "gui");
  assert.match(m.guiRa.at(-1)!.thong_diep, /đã bỏ qua 4 báo vượt trần/);
});

test("đường gửi hỏng (ném đồng bộ hay từ chối) không bao giờ ném ra ngoài", async () => {
  const m = taoMoiTruong();
  const bao1 = taoBaoLoi({
    ...m.cong,
    gui: () => {
      throw new Error("fetch không tồn tại");
    },
  });
  assert.doesNotThrow(() => bao1(loi()));
  const bao2 = taoBaoLoi({ ...m.cong, gui: () => Promise.reject(new Error("429")) });
  assert.doesNotThrow(() => bao2(loi()));
  await new Promise((r) => setImmediate(r));
});

test("thông điệp gửi đi không vượt 1000 ký tự (đúng giới hạn của máy chủ)", () => {
  const m = taoMoiTruong();
  const bao = taoBaoLoi(m.cong);
  bao(loi("x".repeat(990)));
  for (let i = 0; i < 3; i++) bao(loi("x".repeat(990)));
  m.tien(CUA_SO_MS);
  for (const g of m.guiRa) assert.ok(g.thong_diep.length <= 1000);
});

test("cả hai trang lỗi đi qua bộ chặn trùng, không POST thẳng /api/loi", () => {
  for (const f of ["../app/error.tsx", "../app/(dashboard)/error.tsx"]) {
    const ma = readFileSync(new URL(f, import.meta.url), "utf8")
      .replace(/\/\/.*$/gm, "")
      .replace(/\/\*[\s\S]*?\*\//g, "");
    assert.match(ma, /baoLoiTrinhDuyet\(\{/, f);
    assert.doesNotMatch(ma, /fetch\("\/api\/loi"/, `${f}: POST thẳng là tự DoS khi máy chủ bận`);
  }
});
