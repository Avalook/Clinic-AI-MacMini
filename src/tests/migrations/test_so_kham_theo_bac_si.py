"""Số khám phải đánh riêng cho từng bác sĩ — ở CẢ HAI nơi cấp số.

VÌ SAO CÓ BÀI NÀY, 12/08/2026:

Cùng một luật đánh số được viết ở hai chỗ trong database:

  · `check_in_appointment(uuid, text[])`     — hàm mà đường check-in thật gọi
  · `assign_appointment_queue_number()`      — trigger đỡ những đường ghi thẳng

Bản sửa đầu chỉ đổi cái trigger. Nó đúng, nó chạy, và nó KHÔNG CÓ TÁC DỤNG GÌ:
đo trên staging sau khi áp, BS Nam vẫn nhận số 3 và 4 thay vì 1 và 2. Vì
`check_in_appointment` tự tính số rồi mới UPDATE, nên tới lượt trigger chạy thì
`queue_number` đã có giá trị và trigger thoát ngay ở dòng đầu.

Đây là hình dạng lỗi mà dự án gặp đi gặp lại — LUẬT ĐÚNG, KHÔNG NỐI VÀO ĐƯỜNG
THẬT — và lần đó nó xuất hiện ngay bên trong chính bản sửa. Hai bản chép của một
luật không có gì giữ cho giống nhau; bài này là thứ giữ.

VÌ SAO PHẢI ĐÁNH THEO BÁC SĨ: bảng đặt lịch Excel mà Dr4Women đang dùng có mỗi
bác sĩ một cột và số chạy riêng trong từng cột (BS Thành 1→18, BS Thiệp 1→13
cùng một buổi tối). Số khám trong hệ thống tồn tại để ĐỐI CHIẾU với phơi giấy
ấy — bảng gọi trên TV gọi TÊN, không gọi số. Một dãy số duy nhất cho cả phòng
khám thì đối chiếu sai: bệnh nhân đầu tiên của một bác sĩ bị gọi là "số 2".

Bài này quét CHUỖI trong file migration, không cần database, nên nó chạy ở mọi
PR. Nó không kiểm số cấp ra đúng hay không — chuyện đó đo bằng tay trên staging
— nó chỉ canh cho hai bản không lệch nhau lần nữa.
"""

from __future__ import annotations

import pathlib
import re

MIGRATIONS = pathlib.Path(__file__).resolve().parents[3] / "supabase" / "migrations"

# Hai hàm cùng cấp số. Sửa phạm vi ở một bên mà quên bên kia là lỗi bài này bắt.
HAM_CAP_SO = ("check_in_appointment", "assign_appointment_queue_number")

# Quy ước so bác sĩ dùng chung với `slot_seats_used` và `enforce_slot_capacity`:
# lịch chưa xếp bác sĩ gom về một khoá riêng thay vì thành NULL (NULL không so
# bằng `=` được, nên thiếu nó thì lịch chưa xếp bác sĩ tuột khỏi mọi phép đếm).
KHOA_CHUA_XEP = "~none~"


def _than_ham_moi_nhat(ten: str) -> tuple[pathlib.Path, str]:
    """Thân của lần định nghĩa SAU CÙNG của một hàm, theo thứ tự migration.

    Đọc bản cuối chứ không phải bản đầu: một hàm có thể được CREATE OR REPLACE
    nhiều lần qua nhiều migration, và chỉ bản cuối là bản đang chạy.
    """
    mo = re.compile(
        r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+(?:public\.)?" + re.escape(ten) + r"\b",
        re.IGNORECASE,
    )
    tim_thay: tuple[pathlib.Path, str] | None = None
    for f in sorted(MIGRATIONS.glob("*.sql"), key=lambda p: p.name):
        if f.name.endswith(".down.sql"):
            continue
        noi_dung = f.read_text(encoding="utf-8")
        for khop in mo.finditer(noi_dung):
            # Thân hàm nằm giữa cặp $function$ ... $function$ ngay sau khai báo.
            phan_sau = noi_dung[khop.end() :]
            cac_moc = re.findall(r"\$(?:function|\w*)\$", phan_sau)
            if len(cac_moc) < 2:
                continue
            moc = cac_moc[0]
            dau = phan_sau.index(moc) + len(moc)
            cuoi = phan_sau.index(moc, dau)
            tim_thay = (f, phan_sau[dau:cuoi])
    assert tim_thay is not None, (
        f"Không tìm thấy định nghĩa nào của `{ten}` trong {MIGRATIONS}. "
        "Hàm bị đổi tên thì sửa luôn danh sách HAM_CAP_SO ở bài này."
    )
    return tim_thay


def test_ca_hai_ham_cap_so_deu_loc_theo_bac_si() -> None:
    for ten in HAM_CAP_SO:
        duong_dan, than = _than_ham_moi_nhat(ten)
        assert "doctor_id" in than, (
            f"`{ten}` (bản mới nhất ở {duong_dan.name}) cấp số khám mà KHÔNG nhắc "
            "tới doctor_id — nghĩa là nó đánh một dãy chung cho cả phòng khám. "
            "Phòng khám khám theo bác sĩ; số phải chạy riêng từng bác sĩ."
        )


def test_ca_hai_ham_deu_gom_lich_chua_xep_bac_si_vao_mot_day_rieng() -> None:
    for ten in HAM_CAP_SO:
        duong_dan, than = _than_ham_moi_nhat(ten)
        assert KHOA_CHUA_XEP in than, (
            f"`{ten}` ({duong_dan.name}) so bác sĩ mà không dùng khoá "
            f"'{KHOA_CHUA_XEP}' cho lịch chưa xếp bác sĩ. Thiếu nó thì `doctor_id "
            "= NULL` không bao giờ so bằng, mọi lịch chưa xếp bác sĩ đều đếm ra 0 "
            "và cùng nhận số 1."
        )


def test_khoa_dong_thoi_hep_dung_bang_pham_vi_danh_so() -> None:
    """Khoá phải gồm cả bác sĩ, không chỉ (phòng khám, ngày).

    Khoá RỘNG hơn phạm vi đánh số thì đúng nhưng chậm: hai bác sĩ check-in cùng
    lúc phải xếp hàng chờ nhau mà chẳng vì lý do gì. Khoá HẸP hơn phạm vi thì
    sai: hai người cùng lúc có thể cùng đọc ra một số.
    """
    for ten in HAM_CAP_SO:
        duong_dan, than = _than_ham_moi_nhat(ten)
        khoa = re.search(r"'clinicai:queue:'[^;]*", than)
        assert khoa is not None, (
            f"`{ten}` ({duong_dan.name}) không còn khoá 'clinicai:queue:...'. "
            "Bỏ khoá đi thì hai lượt check-in cùng lúc cấp trùng số."
        )
        assert "doctor_key" in khoa.group(), (
            f"Khoá đồng thời của `{ten}` ({duong_dan.name}) không gồm bác sĩ, "
            "trong khi phạm vi đánh số thì có. Hai bác sĩ check-in cùng lúc sẽ "
            "phải chờ nhau vô cớ."
        )
