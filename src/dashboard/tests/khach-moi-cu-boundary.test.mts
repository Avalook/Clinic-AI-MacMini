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
  const luoi = view.match(/grid-cols-\[minmax\(180px,1\.2fr\)[^\]]+\]/g) ?? [];
  assert.ok(luoi.length >= 2, "không tìm thấy đủ hai lưới cột");
  assert.equal(
    new Set(luoi).size,
    1,
    "tiêu đề và hàng dữ liệu phải dùng CÙNG một lưới cột",
  );
});
