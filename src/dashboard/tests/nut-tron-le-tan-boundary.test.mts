// HAI NÚT TRÒN CỦA QUẦY LỄ TÂN — bấm là làm, bấm lại là hoàn tác.
//
// Tuyền 20/08/2026: *"click nút tròn được cơ chế như của CSKH, click là làm mà
// click lại là undo"*, kèm hai mốc thời gian TÁCH BIỆT: check-in mở đồng hồ
// CHỜ, gọi vào khám mở đồng hồ KHÁM.
//
// Vì sao canh bằng bài kiểm đọc mã nguồn: cả bốn tính chất dưới đây đều hỏng
// IM LẶNG. Gọi nhầm đường thì nút vẫn bấm được và vẫn quay; quên `?? null` thì
// TypeScript kêu nhưng quên tách đồng hồ thì không ai kêu, chỉ có số liệu sai
// dần cho tới lúc ai đó đi phân tích.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) =>
  readFileSync(new URL(p, import.meta.url), "utf8");

const board = doc("../app/(dashboard)/reception/queue/QueueBoard.tsx");
const boardKhongChuThich = board.replace(/\/\/.*$/gm, "");
const stepper = doc("../components/ui/Stepper.tsx");
const worklist = doc("../lib/worklist.ts");

test("hai nút tròn đều BẤM ĐƯỢC và đều có đường hoàn tác", () => {
  // Đếm đủ BỐN hành động: 2 nút × (làm + hoàn tác). Thiếu một cái là một nút
  // chỉ đi được một chiều — đúng thứ người dùng phàn nàn ở màn CSKH trước đây.
  for (const ten of ["checkIn", "boCheckIn", "goiVao", "boGoiVao"]) {
    assert.match(
      boardKhongChuThich,
      new RegExp(`\\b${ten}\\b`),
      `thiếu hành động ${ten} — nút tròn không đủ hai chiều`,
    );
  }
  // Và cả bốn phải được NỐI vào Stepper, không chỉ khai rồi bỏ đó.
  assert.match(
    boardKhongChuThich,
    /receptionSteps\(item, tay\)/,
    "Stepper phải nhận bộ hành động, nếu không nút tròn vẫn là chỉ-báo",
  );
});

test("đường gọi vào khám dùng ĐÚNG cặp POST / DELETE", () => {
  assert.match(
    boardKhongChuThich,
    /`\/api\/reception\/goi-vao-kham\/\$\{visitId\}`,\s*"POST"/,
    "làm = POST",
  );
  assert.match(
    boardKhongChuThich,
    /`\/api\/reception\/goi-vao-kham\/\$\{visitId\}`,\s*"DELETE"/,
    "hoàn tác = DELETE",
  );
  // Check-in đi đường CŨ đã có sẵn, không được đẻ đường thứ hai làm cùng việc.
  assert.match(boardKhongChuThich, /action:\s*"checkin"/);
  assert.match(boardKhongChuThich, /action:\s*"undo_checkin"/);
});

test("chưa check-in thì KHÔNG gọi vào khám được", () => {
  // Chốt ở giao diện, dù backend cũng từ chối: bắt người dùng học luật bằng
  // câu lỗi là một thiết kế tồi.
  assert.match(
    boardKhongChuThich,
    /onClick:\s*tay && daCheckIn\s*\?/,
    "nút thứ hai phải khoá khi khách chưa check-in",
  );
});

test("HAI đồng hồ tách biệt — chờ dừng khi khám bắt đầu", () => {
  // Đây là yêu cầu nghiệp vụ cốt lõi: "check-in 18h, gọi vào 18h10 thì thời
  // gian khám tính từ 18h10". Nếu đồng hồ chờ vẫn chạy sau khi đã gọi thì hai
  // con số cộng lại lớn hơn thời gian khách thật sự ở phòng khám.
  assert.match(
    worklist,
    /const den = item\.exam_started_at \? new Date\(item\.exam_started_at\) : now;/,
    "waitedMinutes phải DỪNG ở mốc gọi vào khám",
  );
  assert.match(
    worklist,
    /export function examMinutes/,
    "phải có đồng hồ khám riêng",
  );
  assert.match(
    worklist,
    /if \(!item\.exam_started_at\) return null;/,
    "chưa gọi thì trả null, KHÔNG trả 0 — hai chuyện khác nhau",
  );
});

test("Stepper: bấm được là TUỲ CHỌN, ba màn kia không đổi hành vi", () => {
  // Stepper dùng chung ở 4 màn. Không có onClick thì phải render <span> như cũ:
  // một biểu tượng trông bấm được mà không bấm được còn tệ hơn biểu tượng tĩnh.
  assert.match(stepper, /onClick\?: \(\) => void;/, "onClick phải là tuỳ chọn");
  assert.match(
    stepper,
    /if \(!step\.onClick\) \{[\s\S]{0,200}?<span/,
    "không có onClick ⇒ vẫn là span, không phải button",
  );
  assert.match(stepper, /disabled=\{step\.busy\}/, "đang gửi thì khoá, chống bấm đúp");
  // Ba màn kia KHÔNG được truyền onClick — nếu ai đó thêm, bài kiểm này đỏ và
  // người sửa phải cân nhắc lại thay vì đổi hành vi bốn màn cùng lúc.
  for (const p of [
    "../app/(dashboard)/home/VisitStatusBoard.tsx",
    "../app/(dashboard)/home/VisitProgress.tsx",
    "../app/(dashboard)/sono/SonoView.tsx",
  ]) {
    assert.doesNotMatch(
      doc(p).replace(/\/\/.*$/gm, ""),
      /onClick:\s*\(\)\s*=>/,
      `${p} không được biến Stepper thành nút bấm cùng đợt này`,
    );
  }
});
