// Bước 3 đại tu giao diện — ratchet giá trị kích thước tự chế (DESIGN.md,
// Kỷ luật thi hành, điều 2).
//
// `w-[86px]`, `text-[10px]`, `grid-cols-[minmax(170px,…)]` — mỗi ngoặc vuông
// có px bên trong là một quyết định kích thước đặt NGOÀI thang. Ngày chốt
// DESIGN.md repo có 463 cái; hai bước đại tu đầu tiên — do chính người viết
// luật làm — thêm 11 cái nữa. Đó là bằng chứng đủ: không có máy đếm thì con
// số này chỉ đi một chiều, và chiều đó là lên.
//
// LUẬT RATCHET — trần chỉ được vặn XUỐNG:
//   · đếm ra NHIỀU hơn trần  → có người vừa chế thêm kích thước ngoài thang.
//     Dùng token của thang (text-label/meta/body…, w-*, min-w-*) hoặc — hiếm
//     khi thật sự cần — nhận con số mới vào thang qua một PR riêng chỉ đổi
//     DESIGN.md (Kỷ luật, điều 3).
//   · đếm ra ÍT hơn trần     → ai đó vừa dọn được — TỐT. Nhưng phải hạ TRẦN
//     xuống đúng số mới trong file này, không thì khoảng trống vừa dọn sẽ bị
//     lấp lại bằng px mới mà máy đếm không kêu.
//
// Cách đếm cố tình GIỐNG HỆT lệnh đo tay để hai bên đối chiếu được:
//   grep -rEo '\[[^][]*[0-9]px[^][]*\]' app components lib \
//     --include='*.tsx' --include='*.ts' | wc -l
// (đếm cả px nằm trong chú thích — chấp nhận: con số chỉ cần nhất quán với
// chính nó, và px chết trong chú thích cũng đáng bị dọn.)

import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

// ── TRẦN — chỉ được sửa XUỐNG (trừ PR riêng đổi thang theo Kỷ luật điều 3) ──
const TRAN = 474; // đo 15/08/2026, sau Bước 2 (#107)

const GOC = new URL("..", import.meta.url).pathname;
const MAU_PX = /\[[^\][]*\dpx[^\][]*\]/g;

function demTrongThuMuc(thuMuc: string): { tong: number; theoFile: Map<string, number> } {
  const theoFile = new Map<string, number>();
  const duyet = (d: string) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, e.name);
      if (e.isDirectory()) {
        if (e.name !== "node_modules") duyet(p);
        continue;
      }
      // Cùng phạm vi với lệnh grep ở đầu file: *.ts và *.tsx — KHÔNG *.mts,
      // nên chính các bài kiểm không tự đếm mình.
      if (!/\.tsx?$/.test(e.name) || e.name.endsWith(".d.ts")) continue;
      const so = (readFileSync(p, "utf8").match(MAU_PX) ?? []).length;
      if (so > 0) theoFile.set(p.slice(GOC.length), so);
    }
  };
  duyet(join(GOC, thuMuc));
  let tong = 0;
  for (const so of theoFile.values()) tong += so;
  return { tong, theoFile };
}

test(`ratchet: số giá trị [..px] tự chế đúng bằng trần ${TRAN}`, () => {
  const theoFile = new Map<string, number>();
  let tong = 0;
  for (const thuMuc of ["app", "components", "lib"]) {
    const kq = demTrongThuMuc(thuMuc);
    tong += kq.tong;
    for (const [f, so] of kq.theoFile) theoFile.set(f, so);
  }

  // Kèm bảng xếp hạng vào thông điệp lỗi để người vấp bài kiểm này biết
  // dọn ở đâu là lãi nhất — không phải đi grep lại từ đầu.
  const top = [...theoFile.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([f, so]) => `    ${so}\t${f}`)
    .join("\n");

  assert.ok(
    tong <= TRAN,
    `${tong} giá trị [..px] — VƯỢT trần ${TRAN}. Vừa có kích thước mới chế ` +
      `ngoài thang: dùng token của thang thay vì [..px], hoặc nhận số mới vào ` +
      `thang bằng PR riêng chỉ đổi DESIGN.md.\n  Nơi dày đặc nhất:\n${top}`,
  );
  assert.ok(
    tong >= TRAN,
    `${tong} giá trị [..px] — ÍT hơn trần ${TRAN}. Dọn được là tốt! Giờ hạ ` +
      `hằng TRAN trong ${import.meta.url.split("/").pop()} xuống đúng ${tong} ` +
      `để chốt thành quả, không thì chỗ vừa dọn sẽ bị lấp lại trong im lặng.`,
  );
});
