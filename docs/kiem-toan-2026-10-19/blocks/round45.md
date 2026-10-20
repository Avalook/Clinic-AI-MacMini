# Round 45 — quyền đối tượng, tài chính, lưu trữ và vận hành

Nguồn: Git SHA ghim `956ba4f236b1c92f1280d2097018c199e90ce8c7`, đọc bằng `git show`. Static review; tests chỉ đọc, không chạy; không truy cập app/API/DB/provider/VPS/production/secrets/PHI. Hash/ranges trong `round45.coverage.json`.

Thêm **FIN-019**, **INF-027**, **INF-028**, **OPS-012**, **SEC-037**; mở rộng **INF-006**, **SEC-011**, **SEC-016**, **SEC-018**, **SEC-027**.

- FIN-019: tab tồn lấy backlog mọi ngày trong khi quyền phiếu bị giới hạn ngày/ca/cơ sở; UI hiện ngày, tên/mã và tiền. Cùng clinic/location; cần xác nhận policy trưởng ca.
- INF-027: collector coi `su-kien`/`day-tep` là core; headline overall chỉ gate API/dashboard/Caddy nên có thể xanh khi worker card báo down.
- INF-028: timeout `asyncio.to_thread` không dừng thread; transfer CFS có thể hoàn tất sau purge row VPS đã đánh dấu dọn. Race tĩnh, chưa fault-inject.
- OPS-012: filter khách/cap 2.000 event đổi tập median nhưng UI vẫn ghi “Trung vị cả ngày” và dùng làm ngưỡng tô màu.
- SEC-037: service-order write kiểm capability/clinic/state nhưng thiếu phạm vi bác sĩ/TKYK; luồng cũ có guard ê-kíp.
- SEC-011/016/018/027 thêm evidence lịch sử Notion, PATCH hồ sơ, RLS patient-link/consent và metadata APIs. INF-006 thêm gap giữa drill restore và headline; UI có badge/caveat.

Canh gác im lặng sau exception và TKYK upload ngoài assignment còn held do policy/ownership chưa rõ. Worker retry/fairness/POS dedupe với INF-004/005/011/018/022.

**Full source audit vẫn chưa hoàn tất.** Path counts không đo semantic/behavioral coverage.
