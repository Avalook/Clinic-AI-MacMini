// Bàn làm việc CSKH là màn duy nhất mà "đã xử lý" từng chỉ là một Set trong
// trình duyệt: bấm xong dòng biến mất, F5 là việc quay lại, và hai người gọi
// cùng một bệnh nhân mà không ai biết. B.4 nối ba nút đó vào đường ghi thật.
//
// Ba cách để nó lặng lẽ trở lại như cũ:
//
//  1. Nút chỉ đổi state cục bộ (setDone…, filter theo Set) → màn hình nói dối.
//  2. Ghi thẳng vào Supabase từ trình duyệt → không audit; và cskh_action chỉ có
//     policy SELECT nên nó sẽ hỏng ở màn hình chứ không hỏng ở CI.
//  3. Từ vựng kết quả xử lý lệch giữa hai đầu → backend trả 422, hoặc tệ hơn,
//     ghi được một trạng thái thứ ba mà bộ lọc của bảng không biết tới.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const BACKEND = join(ROOT, "..", "clinicai");
const read = (path: string) => readFileSync(join(ROOT, path), "utf8");

const board = read("app/(dashboard)/cskh/board/CskhBoard.tsx");
const page = read("app/(dashboard)/cskh/board/page.tsx");
const resolveProxy = read("app/api/cskh-action/[id]/resolve/route.ts");
const apptRoute = read("app/api/appointments/route.ts");
const rolesSource = read("lib/roles.ts");
const cskhService = readFileSync(
  join(BACKEND, "services", "cskh_service.py"),
  "utf8",
);
const cskhRouter = readFileSync(
  join(BACKEND, "api", "v1", "routers", "cskh.py"),
  "utf8",
);
const bookingService = readFileSync(
  join(BACKEND, "services", "booking_service.py"),
  "utf8",
);

test("every button on the board writes to the server", () => {
  // Bản cũ giữ việc đã xử lý trong hai Set và lọc dòng theo đó. Nếu nó quay
  // lại, mọi assertion còn lại vẫn xanh — nút vẫn tồn tại, chỉ là không ghi.
  assert.doesNotMatch(
    board,
    /new Set<string>\(\)|setDoneAppts|setDoneFus/,
    "Bảng CSKH đang giấu dòng bằng state cục bộ thay vì ghi kết quả xuống.",
  );
  assert.match(board, /fetch\(path, \{/);
  assert.match(board, /router\.refresh\(\)/);
  // Bấm đúp trong lúc request đang bay = hai lần ghi. busyId chặn ở cửa vào.
  assert.match(board, /if \(busyId\) return;/);
  assert.match(board, /disabled=\{busyId !== null\}/);
});

test("the board never touches Supabase directly", () => {
  assert.doesNotMatch(
    board,
    /\.from\(|getSupabaseService|createClient|SUPABASE_SERVICE_ROLE_KEY/,
    "cskh_action chỉ có policy SELECT (ADR-0012) — ghi phải đi qua FastAPI.",
  );
  assert.doesNotMatch(resolveProxy, /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/);
  assert.match(
    resolveProxy,
    /proxyJsonToBackend\("POST", `\/api\/v1\/cskh\/actions\/\$\{id\}\/resolve`/,
  );
});

test("confirming an appointment reuses the existing state machine", () => {
  // Lịch hẹn đã có máy trạng thái ở booking_service.py, với đúng một đường vào
  // là PATCH /api/appointments. Mở đường ghi thứ hai cho riêng màn này nghĩa là
  // hai bộ luật chuyển trạng thái, và bộ thứ hai không ai kiểm.
  assert.match(board, /"PATCH",\s*\n?\s*"\/api\/appointments"/);
  assert.match(board, /action: "cskh_confirm"/);
  assert.doesNotMatch(board, /\/api\/v1\//);

  assert.match(apptRoute, /"cskh_confirm"/);
  assert.match(
    bookingService,
    /"cskh_confirm": Transition\(\s*\n\s*"CSKH_CONFIRMED",/,
    "cskh_confirm không còn dẫn tới CSKH_CONFIRMED trong booking_service.py.",
  );
  // Bảng lọc dòng theo đúng trạng thái mà transition ghi ra.
  assert.match(board, /a\.status !== "CSKH_CONFIRMED"/);
});

test("frontend and backend share one vocabulary for closing care work", () => {
  const resolutions = cskhService.match(
    /^RESOLUTIONS: dict\[str, str\] = \{([\s\S]*?)^\}/m,
  );
  assert.ok(resolutions, "RESOLUTIONS không còn ở cskh_service.py");
  const keys = [...resolutions[1].matchAll(/"([a-z_]+)":/g)]
    .map((m) => m[1])
    .sort();
  const labels = [...resolutions[1].matchAll(/:\s*"([^"]+)"/g)]
    .map((m) => m[1])
    .sort();

  const proxyKeys = resolveProxy.match(/const OUTCOMES = new Set\(\[(.*?)\]\)/);
  assert.ok(proxyKeys, "resolve route không còn danh sách OUTCOMES");
  assert.deepEqual(
    [...proxyKeys[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]).sort(),
    keys,
    "Danh sách kết quả xử lý ở proxy phải trùng RESOLUTIONS của backend.",
  );

  // Bảng lọc việc đã đóng theo NHÃN mà backend ghi vào cskh_action.status —
  // không phải theo khoá. Lệch một dấu cách là việc đã gọi vẫn nằm trong danh
  // sách chờ gọi.
  const resolved = board.match(/const RESOLVED = new Set\(\[(.*?)\]\)/);
  assert.ok(resolved, "CskhBoard không còn danh sách trạng thái đã đóng");
  assert.deepEqual(
    [...resolved[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]).sort(),
    labels,
    "Nhãn trạng thái ở bảng phải trùng giá trị RESOLUTIONS ghi xuống DB.",
  );

  const outcomes = board.match(/outcome: "called" \| "closed"/);
  assert.ok(outcomes, "CskhBoard không còn ràng kiểu cho kết quả xử lý");
});

test("closing care work is gated by the same role guard on both sides", () => {
  const backendGuard = cskhService.match(
    /^INTAKE_ROLES: frozenset\[ClinicRole\] = frozenset\(([\s\S]*?)^\)/m,
  );
  assert.ok(backendGuard, "INTAKE_ROLES không còn ở cskh_service.py");
  const backendRoles = [...backendGuard[1].matchAll(/ClinicRole\.([A-Z_]+)/g)]
    .map((m) => m[1])
    .sort();

  const helper = rolesSource.match(/export function canWriteIntake\([\s\S]*?\n\}/);
  assert.ok(helper, "roles.ts không còn canWriteIntake");
  const frontendRoles = [...helper[0].matchAll(/role === "([A-Z_]+)"/g)]
    .map((m) => m[1])
    .sort();

  assert.ok(backendRoles.length > 0, "Không đọc được vai nào từ INTAKE_ROLES.");
  assert.deepEqual(frontendRoles, backendRoles);

  assert.match(resolveProxy, /canWriteIntake\(role\)/);
  assert.match(resolveProxy, /status:\s*403/);
  assert.match(cskhRouter, /_INTAKE_GUARD/);

  // Cờ canWrite hôm nay chưa giấu nút của ai (cả ba vai mở được màn đều ghi
  // được), nhưng nó phải đi theo hàng rào backend chứ không theo NAV_ROLES.
  assert.match(page, /canWriteIntake\(await getClinicRole\(\)\)/);
  assert.match(page, /canWrite=\{canWrite\}/);
  assert.match(board, /canWrite \?/);
});

test("a failed write is shown, not swallowed", () => {
  // Nút cũ không bao giờ hỏng vì nó không làm gì. Nút mới hỏng được — 403, mất
  // mạng, lịch đã bị người khác đổi trạng thái — và im lặng ở đây trông giống
  // hệt thành công.
  assert.match(board, /if \(!response\.ok\)/);
  assert.match(board, /setError\(await errorOf\(response\)\)/);
  assert.match(board, /catch \{\s*\n\s*setError\(/);
});
