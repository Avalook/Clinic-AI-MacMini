import assert from "node:assert/strict";
import test, { beforeEach } from "node:test";

import {
  nhoTheoPhongKham,
  quen,
  quenHet,
  soMucDangNho,
} from "./bo-nho-tam.ts";

const A = "a0000000-0000-4000-8000-000000000001";
const B = "b0000000-0000-4000-8000-000000000002";

beforeEach(() => quenHet());

function demLanNap<T>(giaTri: T) {
  let lan = 0;
  return {
    nap: async () => {
      lan += 1;
      return giaTri;
    },
    soLan: () => lan,
  };
}

test("nhớ rồi thì không nạp lại", async () => {
  const n = demLanNap(["Kim Ngưu"]);
  assert.deepEqual(await nhoTheoPhongKham("co-so", A, n.nap), ["Kim Ngưu"]);
  assert.deepEqual(await nhoTheoPhongKham("co-so", A, n.nap), ["Kim Ngưu"]);
  assert.deepEqual(await nhoTheoPhongKham("co-so", A, n.nap), ["Kim Ngưu"]);
  assert.equal(n.soLan(), 1, "ba lượt hỏi, chỉ một lần chạm database");
});

test("HAI PHÒNG KHÁM KHÔNG BAO GIỜ DÙNG CHUNG — luật ①", async () => {
  // Kiểu hỏng nặng nhất của hệ nhiều phòng khám: phòng B nhìn thấy danh mục
  // của phòng A. Bài này là hàng rào duy nhất canh nó ở tầng bộ nhớ tạm.
  const a = demLanNap(["dịch vụ của A"]);
  const b = demLanNap(["dịch vụ của B"]);
  assert.deepEqual(await nhoTheoPhongKham("dich-vu", A, a.nap), [
    "dịch vụ của A",
  ]);
  assert.deepEqual(
    await nhoTheoPhongKham("dich-vu", B, b.nap),
    ["dịch vụ của B"],
    "phòng B phải nạp riêng, KHÔNG được nhận dữ liệu đã nhớ của phòng A",
  );
  assert.equal(a.soLan(), 1);
  assert.equal(b.soLan(), 1);
});

test("hai loại dữ liệu khác nhau không đè nhau", async () => {
  const co = demLanNap(["cơ sở"]);
  const dv = demLanNap(["dịch vụ"]);
  assert.deepEqual(await nhoTheoPhongKham("co-so", A, co.nap), ["cơ sở"]);
  assert.deepEqual(await nhoTheoPhongKham("dich-vu", A, dv.nap), ["dịch vụ"]);
  assert.equal(soMucDangNho(), 2);
});

test("hết hạn thì nạp lại", async () => {
  const n = demLanNap(["cũ"]);
  await nhoTheoPhongKham("co-so", A, n.nap, 1); // hạn 1ms
  await new Promise((r) => setTimeout(r, 5));
  await nhoTheoPhongKham("co-so", A, n.nap, 1);
  assert.equal(n.soLan(), 2, "quá hạn phải hỏi lại");
});

test("KHÔNG nhớ danh sách rỗng — luật ③", async () => {
  // Nhớ một danh sách rỗng suốt 60 giây = cả phòng khám nhìn ô chọn trống mà
  // không hiểu vì sao. Hỏng thì phải hỏng một lần, đừng hỏng kéo dài.
  let lan = 0;
  const nap = async () => {
    lan += 1;
    return lan === 1 ? [] : ["đã có dữ liệu"];
  };
  assert.deepEqual(await nhoTheoPhongKham("dich-vu", A, nap), []);
  assert.deepEqual(
    await nhoTheoPhongKham("dich-vu", A, nap),
    ["đã có dữ liệu"],
    "lượt rỗng không được nhớ, lượt sau phải hỏi lại",
  );
  assert.equal(lan, 2);
});

test("KHÔNG nhớ null/undefined — luật ③", async () => {
  let lan = 0;
  const nap = async () => {
    lan += 1;
    return lan === 1 ? null : { co: true };
  };
  assert.equal(await nhoTheoPhongKham("cau-hinh", A, nap), null);
  assert.deepEqual(await nhoTheoPhongKham("cau-hinh", A, nap), { co: true });
  assert.equal(lan, 2);
});

test("lỗi thì ném ra, KHÔNG nhớ lỗi", async () => {
  let lan = 0;
  const nap = async () => {
    lan += 1;
    if (lan === 1) throw new Error("mạng đứt");
    return ["ổn rồi"];
  };
  await assert.rejects(() => nhoTheoPhongKham("co-so", A, nap), /mạng đứt/);
  assert.deepEqual(await nhoTheoPhongKham("co-so", A, nap), ["ổn rồi"]);
});

test("không có clinic_id thì KHÔNG nhớ, luôn nạp thật", async () => {
  // Khoá rỗng dùng chung là đúng cách để hai phòng khám lẫn nhau.
  const n = demLanNap(["gì đó"]);
  await nhoTheoPhongKham("co-so", "", n.nap);
  await nhoTheoPhongKham("co-so", "", n.nap);
  assert.equal(n.soLan(), 2, "không phòng khám ⇒ không nhớ");
  assert.equal(soMucDangNho(), 0);
});

test("quen() xoá đúng phòng khám, không đụng phòng khác", async () => {
  const a = demLanNap(["A"]);
  const b = demLanNap(["B"]);
  await nhoTheoPhongKham("co-so", A, a.nap);
  await nhoTheoPhongKham("co-so", B, b.nap);
  quen("co-so", A);
  await nhoTheoPhongKham("co-so", A, a.nap);
  await nhoTheoPhongKham("co-so", B, b.nap);
  assert.equal(a.soLan(), 2, "A đã quên nên phải nạp lại");
  assert.equal(b.soLan(), 1, "B không bị đụng tới");
});
