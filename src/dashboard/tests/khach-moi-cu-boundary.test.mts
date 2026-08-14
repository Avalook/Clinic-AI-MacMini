// Cột "Mới / cũ" — tách khỏi cột trạng thái (Tuyền, 13/08/2026).
//
// Hai thứ trả lời hai câu khác nhau: trạng thái là VIỆC PHẢI LÀM bây giờ, còn
// mới/cũ là NGƯỜI NÀY LÀ AI — thứ quyết định cách mở lời khi gọi. Nằm chung một
// ô thì cả hai bị đọc lướt.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { nhanKhachMoiCu } from "../lib/khach-moi-cu.ts";

const view = readFileSync(
  new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
  "utf8",
);

test("chưa khám lần nào → 'Khách mới', không có dòng phụ", () => {
  assert.deepEqual(nhanKhachMoiCu(undefined), { dong1: "Khách mới", dong2: null });
  assert.deepEqual(
    nhanKhachMoiCu({ soLanKham: 0 } as never),
    { dong1: "Khách mới", dong2: null },
  );
});

test("đã khám → 'Khách cũ' + số lần ở dòng dưới", () => {
  assert.deepEqual(
    nhanKhachMoiCu({ soLanKham: 1 } as never),
    { dong1: "Khách cũ", dong2: "đã khám 1 lần" },
  );
  assert.deepEqual(
    nhanKhachMoiCu({ soLanKham: 2 } as never),
    { dong1: "Khách cũ", dong2: "đã khám 2 lần" },
  );
  assert.deepEqual(
    nhanKhachMoiCu({ soLanKham: 12 } as never),
    { dong1: "Khách cũ", dong2: "đã khám 12 lần" },
  );
});

test("KHÁCH ĐÃ KHÁM 1 LẦN VẪN LÀ KHÁCH CŨ", () => {
  // Ranh giới dễ đặt sai nhất. Nhãn cũ "khám lần N" cố ý im lặng ở lần 1 vì
  // "lần 1" đúng với mọi khách nên không nói thêm được gì. Nhưng cột này hỏi
  // câu KHÁC: người này đã từng tới chưa. Đã tới một lần là đã từng tới — và
  // người trực mở lời với họ khác hẳn với người chưa gặp bao giờ.
  const { dong1 } = nhanKhachMoiCu({ soLanKham: 1 } as never);
  assert.equal(dong1, "Khách cũ", "khám 1 lần rồi thì không còn là khách mới");
});

test("chỉ có MỘT chỗ dựng nhãn mới/cũ trong màn này", () => {
  // Nhãn cũ "khám lần N" / "tái khám" đã bỏ khỏi màn này cùng lúc: nó kể cùng
  // một chuyện bằng chữ khác, và để hai chỗ cùng kể một điều là hẹn ngày chúng
  // lệch nhau — đúng cái đã xảy ra với danh mục lý do huỷ (bốn bản, lệch sẵn).
  const ma = view.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
  assert.doesNotMatch(
    ma,
    /nhanLanKham/,
    "màn này không còn được có nhãn 'khám lần N' song song với cột mới/cũ",
  );
  const lib = readFileSync(new URL("../lib/khach-moi-cu.ts", import.meta.url), "utf8");
  const soLanDinhNghia = (lib.match(/function nhanKhachMoiCu/g) ?? []).length;
  assert.equal(soLanDinhNghia, 1, "chỉ một nơi dựng nhãn này");
});

test("cột 'Mới / cũ' có mặt trong tiêu đề bảng", () => {
  assert.match(view, /<span>Mới \/ cũ<\/span>/, "thiếu tiêu đề cột");
  // Lưới cột của tiêu đề và của hàng dữ liệu phải khớp nhau, nếu không thì chữ
  // nằm lệch khỏi cột của nó — lỗi chỉ thấy bằng mắt, không bài kiểm nào khác bắt.
  //
  // BẮT THEO SỐ CỘT, KHÔNG THEO CON SỐ CỤ THỂ. Bản trước ghim cứng
  // `minmax(180px,1.2fr)` ở đầu chuỗi, nên chỉnh lại độ rộng cột (14/08/2026)
  // là biểu thức không khớp gì nữa — và bài kiểm KHÔNG đỏ, nó chỉ lặng lẽ
  // không tìm thấy lưới nào để so. Một bài kiểm ngừng kiểm mà vẫn xanh còn tệ
  // hơn không có bài kiểm. Nay khớp mọi lưới tám cột và so chúng với nhau.
  const luoi = (view.match(/grid-cols-\[[^\]]+\]/g) ?? []).filter(
    (g) => g.split("_").length === 8,
  );
  assert.ok(luoi.length >= 2, "không tìm thấy đủ hai lưới cột tám cột");
  assert.equal(
    new Set(luoi).size,
    1,
    "tiêu đề và hàng dữ liệu phải dùng CÙNG một lưới cột",
  );
});

test("khe giữa các cột của tiêu đề và của hàng bằng nhau", () => {
  // Lưới giống nhau mà khe khác nhau thì cột vẫn lệch: `gap` ăn vào chiều rộng
  // trước khi `fr` được chia. Đúng thứ vừa suýt xảy ra khi thu khe từ 12px
  // xuống 8px cho bảng đỡ thưa — đổi một chỗ, quên chỗ kia.
  // Chỉ đọc khe của HAI khối có lưới tám cột — file này còn nhiều `grid gap-*`
  // khác (thẻ hai cột, khối chi tiết), và vơ hết vào là so nhầm hai chỗ không
  // liên quan rồi báo xanh. Đó đúng là điều đã xảy ra ở bản đầu của bài kiểm.
  //
  // Tìm `gap-*` GẦN NHẤT quanh mỗi lưới tám cột, không dùng một biểu thức
  // xuyên suốt: hai chỗ viết khác nhau (tiêu đề để `grid-cols` trước `gap`,
  // hàng thì ngược lại và còn nằm trong một chuỗi lồng trong template) nên mọi
  // biểu thức "một phát ăn cả hai" đều bắt hụt một bên.
  const khe: string[] = [];
  for (const m of view.matchAll(/grid-cols-\[[^\]]+\]/g)) {
    if ((m[0].match(/_/g) ?? []).length !== 7) continue;
    const quanh = view.slice(Math.max(0, m.index! - 260), m.index! + 260);
    const g = [...quanh.matchAll(/\bgap-(\d)\b/g)].map((x) => x[1]);
    if (g.length) khe.push(g[0]);
  }
  assert.ok(khe.length >= 2, `chỉ đọc được ${khe.length} khe cột, cần 2`);
  assert.equal(
    new Set(khe).size,
    1,
    `tiêu đề và hàng dùng hai khe khác nhau: ${khe.map((k) => `gap-${k}`).join(" vs ")}`,
  );
});
