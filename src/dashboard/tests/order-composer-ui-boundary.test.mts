import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const composer = readFileSync(
  new URL(
    "../app/(dashboard)/doctor/orders/[visitId]/OrderComposer.tsx",
    import.meta.url,
  ),
  "utf8",
);
const page = readFileSync(
  new URL(
    "../app/(dashboard)/doctor/orders/[visitId]/page.tsx",
    import.meta.url,
  ),
  "utf8",
);

test("the order composer keeps the reference design's three working regions", () => {
  assert.match(composer, /aria-label="Bối cảnh lượt khám"/);
  assert.match(composer, /aria-label="Danh mục chỉ định"/);
  assert.match(composer, /aria-label="Trạng thái và tóm tắt chỉ định"/);
  assert.match(
    composer,
    /xl:grid-cols-\[minmax\(180px,0\.65fr\)_minmax\(0,1\.7fr\)_minmax\(250px,0\.85fr\)\]/,
  );
});

test("catalogue controls and room cards are derived from real catalogue data", () => {
  for (const label of [
    "Tìm kiếm dịch vụ",
    "Tất cả phòng thực hiện",
    "Tất cả trạng thái",
    "Phòng thực hiện",
    "Dịch vụ thường dùng",
    "Dịch vụ đã chọn",
  ]) {
    assert.match(composer, new RegExp(label));
  }
  assert.match(composer, /rooms\.entries\(\)/);
  assert.match(composer, /catalogue\.filter/);
});

test("missing clinical and commercial data is explicit instead of fabricated", () => {
  for (const label of [
    "Chưa có dữ liệu từ hồ sơ khám",
    "Chưa cấu hình bộ chỉ định",
    "Chưa đủ dữ liệu để xác định trạng thái chặn",
    "Chưa có giá",
  ]) {
    assert.match(composer, new RegExp(label));
  }
  assert.doesNotMatch(composer, /Bộ khám phụ khoa cơ bản|Pap smear|HPV DNA|2\.950\.000/);
  assert.match(page, /patient=\{patient\}/);
});

test("the composer names the patient it is ordering for", () => {
  // Màn này từng không bao giờ hiện tên: fetchVisitPatient trả một câu về trạng
  // thái ("Lượt khám đang mở") chứ không phải một con người. Chỉ định siêu âm
  // cho một lượt khám vô danh là nhầm người, nên tên đọc từ backend và khi
  // không đọc được thì phải báo động chứ không im lặng để trống.
  assert.match(composer, /patient\?\.full_name/);
  assert.match(composer, /patientLine\(patient\)/);
  assert.match(composer, /Không đọc được người bệnh của lượt khám này/);
  assert.match(composer, /border-danger bg-danger-bg/);
  assert.doesNotMatch(composer, /Lượt khám đang mở|Lượt khám chưa xác định/);
  assert.match(
    composer,
    /anyPriceMissing[\s\S]*?\? "Chưa đủ dữ liệu"[\s\S]*?: money\(subtotal\)/,
  );
  assert.match(composer, /peer-focus-visible:ring-2/);
});

test("the real duplicate and submission boundaries remain intact", () => {
  assert.match(composer, /service-orders\/duplicates/);
  assert.match(composer, /body: JSON\.stringify\(\{ service_codes: codes \}\)/);
  assert.match(composer, /service-orders`,/);
  assert.match(
    composer,
    /body: JSON\.stringify\(\{ service_codes: \[\.\.\.chosen\] \}\)/,
  );
});
