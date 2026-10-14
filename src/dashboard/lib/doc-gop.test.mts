import assert from "node:assert/strict";
import test from "node:test";

import { CUA_SO_CHUNG_MS, taoGopDoc } from "./doc-gop.ts";

function treo<T>() {
  let xong!: (v: T) => void;
  let loi!: (e: unknown) => void;
  const p = new Promise<T>((res, rej) => {
    xong = res;
    loi = rej;
  });
  return { p, xong, loi };
}

/** Một "máy chủ" giả: mỗi lần gọi mở một lượt treo, ta quyết lúc nào xong. */
function taoMayChu() {
  const luot: Array<{ xong: (v: string) => void; loi: (e: unknown) => void }> = [];
  let dangBay = 0;
  let caoNhat = 0;
  return {
    luot,
    chay: async () => {
      const t = treo<string>();
      luot.push({ xong: t.xong, loi: t.loi });
      dangBay += 1;
      caoNhat = Math.max(caoNhat, dangBay);
      try {
        return await t.p;
      } finally {
        dangBay -= 1;
      }
    },
    caoNhat: () => caoNhat,
  };
}

const choMotNhip = () => new Promise<void>((r) => setImmediate(r));

test("mười lần gọi chen lúc đang bay: đúng HAI lượt, không bao giờ song song quá hai", async () => {
  let gio = 0;
  const gop = taoGopDoc(() => gio);
  const may = taoMayChu();

  const dau = gop("k", may.chay); // lượt 1 bắt đầu
  gio += CUA_SO_CHUNG_MS + 100; // quá cửa sổ chung
  const chen = Array.from({ length: 10 }, () => gop("k", may.chay));
  assert.equal(may.luot.length, 1, "chưa xong lượt 1 thì chưa mở lượt 2");

  may.luot[0]!.xong("cu");
  assert.equal(await dau, "cu");
  await choMotNhip();
  assert.equal(may.luot.length, 2, "lượt nối đuôi mở sau khi lượt 1 xong");

  may.luot[1]!.xong("moi");
  assert.deepEqual(await Promise.all(chen), Array(10).fill("moi"));
  assert.equal(may.luot.length, 2, "mười người chen vào chỉ tốn MỘT lượt");
  assert.ok(may.caoNhat() <= 1, "lượt nối đuôi không chạy chồng lượt đang bay");
});

test("người gọi chen KHÔNG nhận kết quả của lượt đã bay từ trước thay đổi của họ", async () => {
  let gio = 0;
  const gop = taoGopDoc(() => gio);
  const may = taoMayChu();

  const truoc = gop("k", may.chay);
  gio += 500; // thay đổi xảy ra giữa chừng, người ta hỏi lại
  const sau = gop("k", may.chay);

  may.luot[0]!.xong("doc-truoc-thay-doi");
  await truoc;
  await choMotNhip();
  may.luot[1]!.xong("doc-sau-thay-doi");
  assert.equal(await sau, "doc-sau-thay-doi");
});

test("hai chỗ cùng đọc một đường dẫn lúc mở màn (≤ cửa sổ chung): dùng chung MỘT lượt", async () => {
  let gio = 0;
  const gop = taoGopDoc(() => gio);
  const may = taoMayChu();

  const a = gop("k", may.chay);
  gio += CUA_SO_CHUNG_MS; // vẫn cùng một đợt dựng màn
  const b = gop("k", may.chay);
  assert.equal(may.luot.length, 1);

  may.luot[0]!.xong("x");
  assert.deepEqual(await Promise.all([a, b]), ["x", "x"]);
});

test("đường dẫn khác nhau không cản nhau", async () => {
  const gop = taoGopDoc(() => 0);
  const may = taoMayChu();
  void gop("a", may.chay);
  void gop("b", may.chay);
  assert.equal(may.luot.length, 2);
  for (const l of may.luot) l.xong("ok");
});

test("lượt hỏng không làm kẹt sổ: lần gọi sau chạy bình thường", async () => {
  let gio = 0;
  const gop = taoGopDoc(() => gio);
  const may = taoMayChu();

  const hong = gop("k", may.chay);
  may.luot[0]!.loi(new Error("mạng chập"));
  await assert.rejects(hong, /mạng chập/);

  gio += 1000;
  const lai = gop("k", may.chay);
  assert.equal(may.luot.length, 2, "sổ đã sạch, lượt mới chạy ngay");
  may.luot[1]!.xong("ổn");
  assert.equal(await lai, "ổn");
});

test("lượt đang bay hỏng thì lượt nối đuôi vẫn chạy (nó hỏi vì thay đổi của riêng nó)", async () => {
  let gio = 0;
  const gop = taoGopDoc(() => gio);
  const may = taoMayChu();

  const dau = gop("k", may.chay);
  gio += 500;
  const sau = gop("k", may.chay);

  may.luot[0]!.loi(new Error("hỏng"));
  await assert.rejects(dau);
  await choMotNhip();
  assert.equal(may.luot.length, 2);
  may.luot[1]!.xong("ổn");
  assert.equal(await sau, "ổn");
});

test("hàm ném đồng bộ không để lại mục kẹt trong sổ", async () => {
  const gop = taoGopDoc(() => 0);
  await assert.rejects(
    gop("k", () => {
      throw new Error("ném ngay");
    }),
    /ném ngay/,
  );
  await choMotNhip();
  const v = await gop("k", async () => "sau");
  assert.equal(v, "sau");
});
