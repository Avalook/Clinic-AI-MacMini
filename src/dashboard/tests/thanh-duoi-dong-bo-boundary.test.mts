// Thanh dưới trên điện thoại phải NÓI CÙNG MỘT CHUYỆN với thanh bên.
//
// Tuyền 14/08/2026: *"cho các nút ở sidebar cũng đồng bộ khi ở giao diện co lại
// như điện thoại… nó phải đúng nút chứ không bịa"*.
//
// HAI KIỂU LỆCH ĐÃ CÓ THẬT, và cả hai đều im lặng:
//
//   1. Thanh bên bỏ các màn lâm sàng khi phòng khám chạy chế độ CSKH_ONLY;
//      thanh dưới KHÔNG lọc theo featureMode, nên điện thoại vẫn hiện lối vào
//      những màn mà máy tính đã giấu.
//
//   2. Thanh dưới lấy "bốn mục ĐẦU TIÊN" của NAV. NAV xếp theo luồng khám bệnh
//      cho thanh bên đọc xuôi, không xếp theo mức hay dùng — nên Quản lý (35
//      mục) nhận Bàn khám · Thu ngân · Chăm sóc, ba màn của NGƯỜI KHÁC, còn Báo
//      cáo/Nhân sự nằm sau nút Menu. Trưởng ca thì thiếu chính "Toàn cảnh điều
//      phối". Nút không sai đường — sai lựa chọn.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { hienTrenThanhBen, ROLE_LABEL, type ClinicRole } from "../lib/roles.ts";

// `nav-items.ts` import "../../lib/roles" KHÔNG kèm đuôi .ts nên node không nạp
// thẳng được module ấy. Đọc thứ tự và danh sách bằng cách phân tích nguồn — đủ
// vì đây là một mảng khai báo phẳng, và nó bắt được đúng thứ bài kiểm cần: mục
// nào có, theo thứ tự nào.
const nguon = readFileSync(
  new URL("../app/(dashboard)/nav-items.ts", import.meta.url),
  "utf8",
);

function docNav(): { href: string }[] {
  const than = nguon.slice(
    nguon.indexOf("export const NAV"),
    nguon.indexOf("// MỘT PHÉP LỌC DUY NHẤT"),
  );
  const moc = [...than.matchAll(/href:\s*"([^"]+)"/g)];
  assert.ok(moc.length > 20, "không đọc được danh sách NAV");
  return moc.map((m) => ({ href: m[1] }));
}

function docNhan(): { href: string; label: string }[] {
  const than = nguon.slice(
    nguon.indexOf("export const NAV"),
    nguon.indexOf("// MỘT PHÉP LỌC DUY NHẤT"),
  );
  const moc = [...than.matchAll(/href:\s*"([^"]+)"/g)];
  return moc.map((m, i) => {
    const d = than.slice(m.index!, moc[i + 1]?.index ?? than.length);
    return { href: m[1], label: /label:\s*"([^"]+)"/.exec(d)?.[1] ?? "" };
  });
}

function docThanhDuoi(): Record<string, string[]> {
  const than = nguon.slice(
    nguon.indexOf("export const THANH_DUOI"),
    nguon.indexOf("/** Bốn nút của thanh dưới"),
  );
  const ra: Record<string, string[]> = {};
  for (const m of than.matchAll(/^\s{2}([A-Z_]+):\s*\[([^\]]*)\]/gm)) {
    ra[m[1]] = [...m[2].matchAll(/"([^"]+)"/g)].map((x) => x[1]);
  }
  assert.ok(Object.keys(ra).length > 0, "không đọc được THANH_DUOI");
  return ra;
}

const NAV = docNav();
const THANH_DUOI = docThanhDuoi();
const VAI = Object.keys(ROLE_LABEL) as ClinicRole[];

test("mọi nút thanh dưới đều là một mục CÓ THẬT trong NAV", () => {
  // Đây là chốt chống "bịa": gõ nhầm một đường dẫn thì nút biến mất lặng lẽ
  // (mucThanhDuoi lọc nó đi) và không ai biết vai ấy đang thiếu một nút.
  const co = new Set(NAV.map((i) => i.href));
  for (const [vai, ds] of Object.entries(THANH_DUOI)) {
    for (const href of ds) {
      assert.ok(co.has(href), `${vai}: "${href}" không có trong NAV`);
    }
  }
});

test("mọi nút thanh dưới đều được vai ấy XEM ĐƯỢC", () => {
  // Khai một màn ngoài quyền của vai thì nút hoặc biến mất, hoặc tệ hơn là hiện
  // ra để người ta bấm vào và nhận 403.
  for (const [vai, ds] of Object.entries(THANH_DUOI)) {
    for (const href of ds) {
      assert.ok(
        hienTrenThanhBen(vai as ClinicRole, href),
        `${vai} không xem được "${href}" — nút này sẽ hụt`,
      );
    }
  }
});

test("không vai nào khai trùng một màn hai lần", () => {
  for (const [vai, ds] of Object.entries(THANH_DUOI)) {
    assert.equal(new Set(ds).size, ds.length, `${vai}: có href khai trùng`);
  }
});

test("mỗi vai được khai ĐỦ bốn nút", () => {
  // Thiếu thì `mucThanhDuoi` bù bằng mục kế tiếp của thanh bên — chạy vẫn đúng,
  // nhưng nút bù ấy lại rơi về "thứ tự cho thanh bên", đúng cái đang muốn tránh.
  for (const [vai, ds] of Object.entries(THANH_DUOI)) {
    assert.equal(ds.length, 4, `${vai}: khai ${ds.length} nút, cần 4`);
  }
});

test("VAI NHIỀU MÀN đều phải được khai — không để rơi về bốn mục đầu", () => {
  // Vai ít màn (CSKH 5, Bác sĩ 6) thì bốn mục đầu vốn đã đúng nên không cần
  // khai. Vai nhiều màn thì KHÔNG được bỏ trống: đó chính là chỗ "bốn mục đầu"
  // cho ra kết quả sai.
  const NGUONG = 8;
  const thieu: string[] = [];
  for (const vai of VAI) {
    const soMan = NAV.filter((i) => hienTrenThanhBen(vai, i.href)).length;
    if (soMan > NGUONG && !THANH_DUOI[vai]) thieu.push(`${vai} (${soMan} màn)`);
  }
  assert.deepEqual(
    thieu,
    [],
    `những vai này có hơn ${NGUONG} màn mà chưa khai thanh dưới: ${thieu.join(", ")}`,
  );
});

test("QUẢN LÝ thấy màn của mình, không phải màn của người khác", () => {
  // Tuyền nêu đích danh vai này. Quản lý không đứng quầy: bốn nút trên điện
  // thoại phải là thứ họ mở, không phải bàn khám hay bàn thu ngân.
  const ds = THANH_DUOI.MANAGEMENT;
  assert.ok(ds, "chưa khai thanh dưới cho Quản lý");
  assert.ok(ds.includes("/reports"), "Quản lý phải có Báo cáo trên thanh dưới");
  for (const cua_nguoi_khac of ["/doctor/board", "/cashier/board"]) {
    assert.ok(
      !ds.includes(cua_nguoi_khac),
      `Quản lý không thao tác "${cua_nguoi_khac}" — đó là màn của vai khác`,
    );
  }
});

test("hai thanh dùng CHUNG một phép lọc, không mỗi bên một bản", () => {
  const nav = readFileSync(
    new URL("../app/(dashboard)/Nav.tsx", import.meta.url),
    "utf8",
  );
  const duoi = readFileSync(
    new URL("../app/(dashboard)/BottomNav.tsx", import.meta.url),
    "utf8",
  );
  for (const [ten, ma] of [
    ["Nav", nav],
    ["BottomNav", duoi],
  ] as const) {
    assert.match(ma, /mucHienRa\(/, `${ten} phải lọc qua mucHienRa`);
    assert.doesNotMatch(
      ma.replace(/\/\/.*$/gm, ""),
      /NAV\.filter\(/,
      `${ten} không được tự lọc NAV — hai bản sao sẽ lệch nhau`,
    );
  }
  // featureMode phải tới được thanh dưới, nếu không thì phép lọc chung vô nghĩa.
  const shell = readFileSync(
    new URL("../app/(dashboard)/Shell.tsx", import.meta.url),
    "utf8",
  );
  assert.match(
    shell,
    /<BottomNav[\s\S]*?featureMode=/,
    "Shell phải truyền featureMode xuống BottomNav",
  );
});

test("MỘT NÚT CHỈ CÓ MỘT TÊN — không còn shortLabel", () => {
  // Cơ chế `shortLabel` cho phép cùng một nút mang hai tên, và ba nút đã trôi
  // thành tên khác hẳn: "Danh sách bệnh nhân" → "BN đã khám", "Lịch làm việc"
  // → "Ca trực", "Command Center" → "Trung tâm". Người dùng học tên trên máy
  // tính rồi tìm mãi không thấy nút ấy trên điện thoại.
  assert.doesNotMatch(
    nguon,
    /shortLabel:/,
    "nav-items không được có shortLabel — một nút, một tên",
  );
  for (const f of [
    "../app/(dashboard)/BottomNav.tsx",
    "../app/(dashboard)/portal/PortalBoard.tsx",
  ]) {
    const ma = readFileSync(new URL(f, import.meta.url), "utf8").replace(
      /\/\/.*$/gm,
      "",
    );
    assert.doesNotMatch(ma, /shortLabel/, `${f} vẫn còn đọc shortLabel`);
  }
});

test("không hai nút nào trùng tên", () => {
  // Trước đây "Hàng đợi" là tên của CẢ /reception/queue lẫn /truong-ca/hang-doi,
  // và "Lịch sử" là tên của cả /audit-log lẫn /pharmacy/history. Trên thanh
  // dưới — nơi chỉ có chữ và một biểu tượng — không cách nào biết mình bấm cái
  // nào.
  const theoNhan = new Map<string, string[]>();
  for (const { href, label } of docNhan()) {
    theoNhan.set(label, [...(theoNhan.get(label) ?? []), href]);
  }
  const trung = [...theoNhan.entries()].filter(([, v]) => v.length > 1);
  assert.deepEqual(
    trung.map(([k, v]) => `"${k}" ← ${v.join(", ")}`),
    [],
    "hai màn khác nhau đang mang cùng một tên",
  );
});
