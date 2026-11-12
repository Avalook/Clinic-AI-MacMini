# GIAO VIỆC — Tạm ẩn mã ống ở bàn "Việc của đối tác"

> Soạn 09/11/2026. Làm **trước** việc quay video (`docs/GIAO-VIEC-VIDEO-HUONG-DAN.md`).
> Bảo Claude Code: "Đọc CLAUDE.md, rồi làm theo docs/GIAO-VIEC-AN-MA-ONG.md."

```text
Đọc CLAUDE.md, rồi .claude/rules/xet-nghiem-doi-tac.md và docs/KE-HOACH-XET-NGHIEM-DOI-TAC.md
mục 2 câu A, mục 4.5, mục 5d.

VIỆC (lời Tuyền, 09/11):
  "Tôi và phòng khám chưa bàn gì về mã xét nghiệm, mã ống mới là giả định. Tạm ẩn
  cái sinh mã đi; chờ bên đối tác báo cách tự động lấy kết quả rồi mới làm bản sau."

QUYẾT ĐỊNH (đã chốt, không hỏi lại):
  - ẨN Ở MÀN, KHÔNG GỠ Ở DB. Postgres vẫn cấp mã (`cap_ma_mau`, Damm) như cũ — ràng buộc
    `mau_xet_nghiem.ma_mau`, FK ghép, sự kiện `lab.sample_collected`, ghép Drive theo mã
    trong tên tệp đều GIỮ NGUYÊN. Lý do: gỡ cột/hàm là đổi lược đồ, mở lại tốn hơn nhiều;
    ẩn thì bật lại bằng một công tắc.
  - Một công tắc theo phòng khám: cột `xet_nghiem_cai_dat.hien_ma_ong boolean NOT NULL
    DEFAULT false` (migration MỚI). Mặc định TẮT ⇒ mọi phòng khám đang thấy mã sẽ thôi thấy.
  - Ẩn TỪ MÁY CHỦ: khi tắt, mọi cửa đọc trả `ma_mau = null` và câu "Xem quá trình" không kèm
    mã. Màn không tự suy (luật: không luật nghiệp vụ trong TSX) — chỉ đọc cờ `hien_ma_ong`
    máy chủ trả trong `GET /ban`.

Ở ĐÂU:
  Máy chủ:
    src/clinicai/services/xet_nghiem/doi_tac.py  luu_nguong → thêm lưu `hien_ma_ong`
      (cùng dòng `xet_nghiem_cai_dat`, cùng sự kiện `lab.settings_saved`)
    src/clinicai/services/xet_nghiem/cai_dat.py  lệnh mới gọi sang doi_tac.py
    src/clinicai/services/xet_nghiem/ban.py:60,154  ma_mau → null khi tắt; trả cờ `hien_ma_ong`
    src/clinicai/services/xet_nghiem/mau.py:156  kết quả lấy mẫu: ma_mau null khi tắt
    src/clinicai/services/xet_nghiem/qua_trinh.py:64,70,86  "Lấy mẫu" / "Huỷ mẫu: <lý do>" /
      "Gỡ việc khỏi ống" — bỏ mã khi tắt
    src/clinicai/api/v1/routers/xet_nghiem_ban.py:97,175  response_model thêm cờ
  Màn (src/dashboard/app/(dashboard)/ban-xet-nghiem/):
    BanXetNghiem.tsx:164-171  lấy mẫu thành công xét theo `r.ok`, KHÔNG theo `d.ma_mau`
      (hiện tại thiếu mã ⇒ báo lỗi — chỗ này sẽ vỡ nếu quên)
    BanXetNghiem.tsx:386-390  khung sau lấy mẫu: tắt ⇒ "Đã lấy mẫu · Hẹn trả <ngày>", không có
      dòng "Mã ống — viết / dán lên ống"
    BanXetNghiem.tsx:171  câu báo: tắt ⇒ "Đã lấy mẫu."
    BanXetNghiem.tsx:208  ô tìm: tắt ⇒ "Tìm tên khách, mã khách"
    TheViec.tsx:158 · KetQuaKhach.tsx:135,254 · PopupKhach.tsx:47 — đã tự ẩn khi ma_mau null;
      PopupKhach "chưa lấy" phải đổi theo trạng thái (đã lấy mẫu mà không có mã ⇒ "Đã lấy mẫu")
    CaiDat.tsx  thêm công tắc "Hiện mã ống" cạnh ô số ngày cảnh báo, chữ phụ:
      "Tắt: mẫu vẫn được đánh số trong hệ thống nhưng không hiện ra màn. Bật khi phòng khám
       đã thống nhất cách ghi mã lên ống với đối tác."
  Giữ nguyên chữ "Lấy mẫu chung một ống" (ống là vật thật, không phải mã).

KẾT QUẢ CẦN ĐẠT:
  - Công tắc TẮT (mặc định): nhân viên bấm Lấy mẫu ⇒ việc sang "Đã lấy mẫu", thấy hẹn trả,
    KHÔNG thấy mã ở bất kỳ chỗ nào của bàn (thẻ việc, khung sau lấy mẫu, tab Kết quả, popup
    khách, Xem quá trình, câu báo). Tìm theo mã không ra gì.
  - Công tắc BẬT: mọi thứ như hôm nay (mã cũ của mẫu đã lấy lúc tắt cũng hiện ra — mã vẫn có
    trong DB).
  - Chỉ Quản lý thấy và đổi được công tắc (cùng quyền `config.clinic.manage` với ô số ngày).
  - Hoàn tác bước trước (huỷ mẫu) và lấy lại mẫu vẫn chạy khi tắt.
  - Chỉ màn bàn XN này. Màn khác không hiện mã ống (đã kiểm 09/11: grep không thấy) — nếu
    tìm thấy chỗ nào khác thì ẩn luôn theo cùng cờ và ghi vào báo cáo.

CÁCH KIỂM:
  - Test: test_xet_nghiem_* hiện có phải xanh + test mới: (1) tắt ⇒ GET /ban không có chuỗi
    mã nào (quét cả JSON), (2) tắt ⇒ lấy mẫu trả 200, ma_mau null, DB vẫn có ma_mau đúng Damm,
    (3) bật ⇒ như cũ, (4) quá trình khi tắt không chứa mã, (5) người không phải Quản lý đổi
    công tắc ⇒ 403. Thử ngược: bỏ chỗ che ở ban.py ⇒ test (1) đỏ.
  - Bấm thật local 1280 và 375, vai Quản lý + nhân viên: tắt → lấy mẫu → xem đủ 5 chỗ ở trên →
    bật → mã hiện lại → tắt lại.
  - SQL: SELECT ma_mau FROM mau_xet_nghiem ORDER BY lay_luc DESC LIMIT 3;  -- vẫn có mã

KHÔNG ĐƯỢC ĐỤNG:
  cap_ma_mau, ma_mau.py, cột/ràng buộc mau_xet_nghiem, ghép Drive, sự kiện · không xoá test
  Damm · `doi_tac_service.py` / router `doi_tac.py` đóng băng · không deploy, không đụng prod.

ĐẦU RA:
  Nhánh `claude/an-ma-ong` từ origin/main → PR. ./scripts/ci-may.sh --bao-github xanh.
  Sửa docs/KE-HOACH-XET-NGHIEM-DOI-TAC.md mục 2 câu A: "09/11: tạm ẩn mã ở màn (công tắc
  hien_ma_ong, mặc định tắt); chờ cách lấy kết quả tự động của đối tác rồi mới chốt mã."
  Báo cáo 4 mục SO-LUAT 12.4 + bảng nút đã đụng.
```
