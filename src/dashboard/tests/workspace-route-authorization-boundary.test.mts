import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const protectedWorkspaces = [
  ["../app/(dashboard)/reception/queue/page.tsx", "/reception/queue"],
  ["../app/(dashboard)/ban-kham/page.tsx", "/ban-kham"],
  ["../app/(dashboard)/thu-ngan/dich-vu/page.tsx", "/thu-ngan/dich-vu"],
  ["../app/(dashboard)/thu-ngan/thuoc/page.tsx", "/thu-ngan/thuoc"],
  ["../app/(dashboard)/duyet-ket-qua/page.tsx", "/duyet-ket-qua"],
  ["../app/(dashboard)/do-sinh-hieu/page.tsx", "/do-sinh-hieu"],
] as const;

test("every role-scoped workspace has a server-side navigation guard", () => {
  for (const [path, href] of protectedWorkspaces) {
    const source = page(path);
    assert.match(
      source,
      // CHO PHÉP NHẬP KÈM TÊN KHÁC. Bất biến là "trang có gọi cửa gác
      // requireNavAccess", không phải "trang chỉ nhập đúng một tên từ tệp ấy".
      // Quầy thu ngân nhập thêm `getClinicRole` để biết mình là quầy thuốc hay
      // quầy dịch vụ — bài kiểm cũ đỏ vì dấu phẩy, trong khi cửa gác vẫn nguyên.
      /import \{[^}]*\brequireNavAccess\b[^}]*\} from "@\/lib\/clinic-session"/,
      `${path} must import the server-side guard`,
    );
    assert.match(
      source,
      new RegExp(`await requireNavAccess\\("${href}"\\)`),
      `${path} must authorize before it reads workspace data`,
    );
  }
});

test("trang theo phòng gác bằng đúng đường dẫn của phòng ấy", () => {
  // /ban-kham/KN-NOITIET và /phong/KN-SA1 là đường ĐỘNG — cửa gác phải ghép mã
  // phòng vào, không thì luật vai của từng phòng không bao giờ được hỏi tới.
  assert.match(
    page("../app/(dashboard)/ban-kham/[phong]/page.tsx"),
    /await requireNavAccess\(`\/ban-kham\/\$\{phong\}`\)/,
  );
  assert.match(
    page("../app/(dashboard)/phong/[ma]/page.tsx"),
    /await requireNavAccess\(`\/phong\/\$\{ma\}`\)/,
  );
});
