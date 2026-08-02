// Kho thuốc là bảng đầu tiên mà frontend có nút GHI vào (B.3), và nó là một
// cuốn sổ: `inventory_txn` là sổ, `drug_batch.quantity_on_hand` là số dư, trigger
// giữ hai bên khớp. Ba cách làm hỏng cuốn sổ đó đều nằm ở tầng này:
//
//   1. Ghi thẳng vào Supabase từ trình duyệt → không qua audit, và tồn kho đổi
//      mà không có dòng sổ nào. Database chặn (không có policy ghi), nhưng lúc
//      đó lỗi hiện ra là "permission denied" ở màn hình, không phải ở CI.
//   2. Quên Idempotency-Key ở đúng một route → một lần bấm đúp là hai lô hàng.
//   3. Danh sách vai được ghi ở frontend lệch khỏi guard của backend → nút hiện
//      ra cho người bấm vào chỉ nhận 403.
//
// Test này đọc mã nguồn (kể cả mã Python) thay vì gọi API, nên nó chạy được ở
// mọi máy không cần database.

import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const BACKEND = join(ROOT, "..", "clinicai");

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.(ts|tsx|mts)$/.test(entry)) out.push(full);
  }
  return out;
}

const read = (path: string) => readFileSync(path, "utf8");

const pharmacyRoutes = walk(join(ROOT, "app", "api", "pharmacy"))
  .filter((f) => f.endsWith("route.ts"))
  .map((f) => ({ path: relative(ROOT, f), text: read(f) }));

const dashboardSources = [join(ROOT, "app"), join(ROOT, "lib")]
  .flatMap(walk)
  .filter((f) => !f.endsWith(".test.mts") && !f.endsWith(".test.ts"))
  .map((f) => ({ path: relative(ROOT, f), text: read(f) }));

const proxyHelper = read(join(ROOT, "lib", "pharmacy-proxy.ts"));
const rolesSource = read(join(ROOT, "lib", "roles.ts"));
const dialogSource = read(
  join(ROOT, "app", "(dashboard)", "pharmacy", "inventory", "StockDialog.tsx"),
);
const backendRouter = read(join(BACKEND, "api", "v1", "routers", "pharmacy.py"));
const backendService = read(join(BACKEND, "services", "pharmacy_service.py"));

test("there is a write path at all", () => {
  // Trước B.3 thư mục này không tồn tại và màn /pharmacy hứa hẹn trong docstring
  // một thứ không có thật. Nếu ai đó gỡ đi, phần còn lại của file này sẽ xanh
  // một cách vô nghĩa — mọi vòng lặp đều chạy trên danh sách rỗng.
  assert.equal(
    pharmacyRoutes.length,
    4,
    `Kho thuốc có bốn thao tác ghi (nhập, xuất, điều chỉnh, huỷ); tìm thấy ${pharmacyRoutes.length} route.`,
  );
});

test("every pharmacy write goes to FastAPI, never to Supabase", () => {
  const direct = pharmacyRoutes
    .filter((r) => /\.from\(|getSupabaseService|createClient/.test(r.text))
    .map((r) => r.path);

  assert.deepEqual(
    direct,
    [],
    `Route ghi kho phải đi qua backend (ADR-0012). Database không có policy ghi, ` +
      `nên đường này chỉ đổi được số tồn bằng service_role — tức là bỏ qua cả audit:\n  ${direct.join("\n  ")}`,
  );
});

test("every pharmacy write carries an Idempotency-Key", () => {
  const missing = pharmacyRoutes
    .filter((r) => !/forwardPharmacyWrite\(/.test(r.text))
    .map((r) => r.path);

  assert.deepEqual(
    missing,
    [],
    `Route này gửi thẳng qua proxy nên không ai bắt buộc Idempotency-Key. ` +
      `Một lần bấm đúp = hai lô hàng:\n  ${missing.join("\n  ")}`,
  );

  // Và cái helper đó phải thật sự từ chối khi thiếu khoá, chứ không chỉ chuyển tiếp.
  assert.match(proxyHelper, /headers\.get\(["']Idempotency-Key["']\)/);
  assert.match(proxyHelper, /if \(!key\) return badRequest/);
});

test("the browser mints a fresh key whenever the numbers change", () => {
  // Dùng lại khoá cũ sau khi sửa số nghĩa là server trả về kết quả của lần
  // trước: người dùng sửa 50 thành 5, bấm gửi, và được báo "đã nhập 50".
  assert.match(dialogSource, /"Idempotency-Key": idemKey/);
  const setField = dialogSource.match(
    /function setField<[\s\S]*?\n {2}\}/,
  )?.[0];
  assert.ok(setField, "setField không còn tồn tại trong StockDialog");
  assert.match(setField, /setIdemKey\(newKey\(\)\)/);
});

test("the frontend never writes the ledger or the balance itself", () => {
  const writers = dashboardSources
    .filter((f) =>
      /\.from\(["'](drug_batch|inventory_txn)["']\)[\s\S]{0,200}?\.(insert|update|upsert|delete)\(/.test(
        f.text,
      ),
    )
    .map((f) => f.path);

  assert.deepEqual(
    writers,
    [],
    `Số tồn chỉ được đổi bằng một dòng inventory_txn qua backend. Ghi thẳng ` +
      `vào drug_batch làm sổ và số dư lệch nhau vĩnh viễn:\n  ${writers.join("\n  ")}`,
  );
});

test("the backend service never writes quantity_on_hand either", () => {
  // Trigger inventory_txn_apply() là nơi duy nhất cộng trừ số dư. Một câu
  // UPDATE ... SET quantity_on_hand trong service sẽ chạy THÊM vào trigger, và
  // kho lệch đúng gấp đôi lượng vừa ghi — không lỗi, không cảnh báo.
  assert.doesNotMatch(
    backendService,
    /SET\s+quantity_on_hand/i,
    "PharmacyService đang tự ghi số dư thay vì để trigger cộng từ sổ.",
  );
});

test("frontend and backend agree on who may change stock", () => {
  const guard = backendRouter.match(/_PHARMACY_GUARD = require_role\(([^)]*)\)/s);
  assert.ok(guard, "Không tìm thấy _PHARMACY_GUARD trong routers/pharmacy.py");
  const backendRoles = [...guard[1].matchAll(/ClinicRole\.([A-Z_]+)/g)]
    .map((m) => m[1])
    .sort();

  const helper = rolesSource.match(
    /export function canWriteInventory\([\s\S]*?\n\}/,
  );
  assert.ok(helper, "roles.ts không còn canWriteInventory");
  const frontendRoles = [...helper[0].matchAll(/role === "([A-Z_]+)"/g)]
    .map((m) => m[1])
    .sort();

  assert.deepEqual(
    frontendRoles,
    backendRoles,
    `Danh sách vai ở hai đầu lệch nhau. Backend quyết định, nên phía lệch chỉ ` +
      `làm nút hiện ra rồi trả 403 — hoặc giấu nút của người thật sự có quyền.`,
  );
  assert.ok(backendRoles.length > 0, "guard rỗng: mọi vai đều ghi được");
});

test("the inventory screen only offers the buttons to those roles", () => {
  const page = read(
    join(ROOT, "app", "(dashboard)", "pharmacy", "inventory", "page.tsx"),
  );
  assert.match(page, /canWriteInventory\(await getClinicRole\(\)\)/);
  assert.match(page, /canWrite=\{canWrite\}/);

  const board = read(
    join(ROOT, "app", "(dashboard)", "pharmacy", "inventory", "InventoryBoard.tsx"),
  );
  // Nút mở hộp thoại phải nằm sau một điều kiện canWrite, không phải luôn hiện.
  assert.match(board, /canWrite \? \(/);
  assert.match(board, /openDialog\("receive"\)/);
  assert.match(board, /openDialog\("adjust", b\)/);
  assert.match(board, /openDialog\("discard", b\)/);
});
