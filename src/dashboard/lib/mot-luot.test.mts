import assert from "node:assert/strict";
import test from "node:test";

import { taoMotLuot } from "./mot-luot.ts";

function treo() {
  let xong!: () => void;
  const p = new Promise<void>((r) => {
    xong = r;
  });
  return { p, xong };
}

test("gọi chen khi đang tải: không chạy song song, gộp thành đúng một lượt nữa", async () => {
  const motLuot = taoMotLuot();
  let dangChay = 0;
  let caoNhat = 0;
  let soLan = 0;
  const cho: Array<() => void> = [];
  const viec = async () => {
    soLan += 1;
    dangChay += 1;
    caoNhat = Math.max(caoNhat, dangChay);
    const t = treo();
    cho.push(t.xong);
    await t.p;
    dangChay -= 1;
  };

  const a = motLuot(viec);
  const b = motLuot(viec);
  const c = motLuot(viec);
  assert.equal(soLan, 1);
  cho.shift()!();
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(soLan, 2, "ba lần gọi chen gộp thành MỘT lượt tải lại");
  cho.shift()!();
  await Promise.all([a, b, c]);
  assert.equal(soLan, 2);
  assert.equal(caoNhat, 1, "không bao giờ hai lượt cùng chạy");
});

test("lượt tải lại chạy việc ghi SAU CÙNG (đổi ngày giữa chừng)", async () => {
  const motLuot = taoMotLuot();
  const da: string[] = [];
  const viec = (ngay: string) => async () => {
    await new Promise((r) => setTimeout(r, 2));
    da.push(ngay);
  };
  void motLuot(viec("08/10"));
  void motLuot(viec("08/10"));
  await motLuot(viec("09/10"));
  assert.deepEqual(da, ["08/10", "09/10"]);
});

test("người gọi chen vào đợi tới khi lượt tải lại xong", async () => {
  const motLuot = taoMotLuot();
  const thuTu: string[] = [];
  let lan = 0;
  const viec = async () => {
    lan += 1;
    await new Promise((r) => setTimeout(r, 5));
    thuTu.push(`xong ${lan}`);
  };
  void motLuot(viec);
  await motLuot(viec);
  thuTu.push("người gọi thứ hai tiếp tục");
  assert.deepEqual(thuTu, ["xong 1", "xong 2", "người gọi thứ hai tiếp tục"]);
});

test("lượt lỗi không khoá chết: lần gọi sau vẫn chạy", async () => {
  const motLuot = taoMotLuot();
  let lan = 0;
  const viec = async () => {
    lan += 1;
    if (lan === 1) throw new Error("mất mạng");
  };
  await assert.rejects(motLuot(viec));
  await motLuot(viec);
  assert.equal(lan, 2);
});
