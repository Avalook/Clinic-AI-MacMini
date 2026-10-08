// LIỆU TRÌNH "SẮP HẾT LỘ TRÌNH" (Tuyền 08/10/2026, docs/KE-HOACH-LIEU-TRINH.md):
//   * tab Liệu trình của `/nhac-tai-kham` có danh sách THỨ BA "Sắp hết lộ trình",
//     đặt ĐẦU tab, máy chủ lọc (`?loai=sap_het`), mỗi dòng chip lý do máy chủ trả;
//   * nút [Ghi cuộc gọi] (sổ chạm khách sẵn có) · [Thêm buổi] (đăng ký thêm buổi)
//     · [Đặt lịch buổi kế] · [Kết thúc liệu trình] · [Đã xử lý] — mọi lệnh có Hoàn
//     tác (lệnh hoàn tác của liệu trình, hoặc rút lại dòng sổ chạm khách);
//   * khung khách hiện cùng chip; route Next chỉ chuyển tiếp;
//   * KHÔNG thêm dòng ở phòng / hàng chờ / Hành trình / TV.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { nhanSapHet, soBuoiSauKhiThem } from "../lib/lieu-trinh-cskh.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

const CSKH = read("../app/(dashboard)/nhac-tai-kham/LieuTrinhCskh.tsx");
const DONG = read("../app/(dashboard)/_lam-viec/LieuTrinhKhach.tsx");
const ROUTE = read("../app/api/cskh/lieu-trinh/route.ts");
const ROUTE_ID = read("../app/api/cskh/lieu-trinh/[id]/route.ts");

test("chip lý do: chỉ ghép chữ máy chủ trả, kèm cờ đã xử lý", () => {
  assert.equal(nhanSapHet({ sap_het_ly_do: null }), null);
  assert.equal(nhanSapHet({}), null);
  assert.equal(nhanSapHet({ sap_het_ly_do: "còn 1 buổi" }), "Sắp hết lộ trình · còn 1 buổi");
  assert.equal(
    nhanSapHet({ sap_het_ly_do: "còn 1 buổi", sap_het_da_xu_ly: true }),
    "Sắp hết lộ trình · còn 1 buổi · CSKH đã xử lý",
  );
});

test("[Thêm buổi]: số mới = hiện tại + số gõ; rác / ≤0 / vượt 200 → null, không ném", () => {
  assert.equal(soBuoiSauKhiThem(3, "2"), 5);
  assert.equal(soBuoiSauKhiThem(3, " 1 "), 4);
  for (const rac of ["", "0", "-1", "abc", "1.5", "1e2", "1000"]) {
    assert.equal(soBuoiSauKhiThem(3, rac), null, rac);
  }
  assert.equal(soBuoiSauKhiThem(199, "2"), null);
  assert.equal(soBuoiSauKhiThem(198, "2"), 200);
});

test("tab Liệu trình: danh sách Sắp hết ĐẦU tab, máy chủ lọc, nghe sổ chạm khách", () => {
  assert.match(CSKH, /docDs\("sap_het"/);
  const sapHet = CSKH.indexOf('tieuDe="Sắp hết lộ trình"');
  const deXuat = CSKH.indexOf('tieuDe="Đề xuất chưa đăng ký"');
  assert.ok(sapHet > 0 && sapHet < deXuat, "Sắp hết phải đứng trước Đề xuất");
  assert.match(CSKH, /"tuong_tac_cskh"/);
  // Số đếm của nhóm (chip "{n} khách") dùng chung component Nhom.
  assert.match(CSKH, /ds\.length\} khách/);
});

test("dòng liệu trình: đủ 5 nút sắp hết, mọi lệnh có Hoàn tác", () => {
  for (const nut of ["Ghi cuộc gọi", "Thêm buổi", "Đặt lịch buổi kế", "Kết thúc liệu trình", "Đã xử lý"]) {
    assert.ok(DONG.includes(nut), nut);
  }
  // Đã xử lý → lệnh máy chủ; hoàn tác = rút lại dòng sổ chạm khách SẴN CÓ.
  assert.match(DONG, /thao_tac: "da-xu-ly-sap-het"/);
  assert.match(DONG, /\/api\/cskh\/tuong-tac\/\$\{id\}\/hoan-tac/);
  // Ghi cuộc gọi đi đúng đường sổ chạm khách + khoá chống ghi trùng.
  assert.match(DONG, /"\/api\/cskh\/tuong-tac"/);
  assert.match(DONG, /"Idempotency-Key"/);
  // Thêm buổi = đăng ký (CSKH có quyền), hoàn tác bằng lệnh hoàn tác liệu trình.
  assert.match(DONG, /thao_tac: "dang-ky",\s*so_buoi: soSauThem/);
  assert.match(DONG, /onBao\(\{ cau, goi: hoanTacTuongTac\(id\) \}\)/);
  assert.match(DONG, /onBao\(\{ cau, goi: hoanTacLieuTrinh\(lt\.id\) \}\)/);
  // Chip lý do ở cả khung khách (dòng dùng chung) — chữ máy chủ.
  assert.match(DONG, /nhanSapHet\(lt\)/);
  assert.doesNotMatch(DONG, /so_buoi\s*-\s*lt\.da_lam|lt\.so_buoi - lt\.da_lam/);
});

test("route Next chỉ chuyển tiếp: loai=sap_het + lệnh da-xu-ly-sap-het", () => {
  assert.match(ROUTE, /loai !== "sap_het"/);
  assert.match(ROUTE_ID, /"da-xu-ly-sap-het"/);
  for (const r of [ROUTE, ROUTE_ID]) {
    assert.doesNotMatch(r, /createClient|\.from\(/);
  }
});

test("phạm vi hiển thị: sắp hết KHÔNG vào phòng / hàng chờ / Hành trình / TV", () => {
  const goc = fileURLToPath(new URL("../app/(dashboard)/", import.meta.url));
  const cam = ["phong", "reception", "ban-kham", "hanh-trinh", "tv", "thu-ngan"];
  const quet = (thu: string): string[] =>
    readdirSync(thu).flatMap((f) => {
      const p = join(thu, f);
      return statSync(p).isDirectory() ? quet(p) : /\.tsx?$/.test(f) ? [p] : [];
    });
  for (const vung of cam) {
    let tep: string[] = [];
    try {
      tep = quet(join(goc, vung));
    } catch {
      continue;
    }
    for (const p of tep) {
      const s = readFileSync(p, "utf8");
      assert.ok(!/sap_het|Sắp hết lộ trình/.test(s), `${p} không được hiện "sắp hết"`);
    }
  }
});
