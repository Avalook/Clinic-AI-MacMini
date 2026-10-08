"""Một dòng lịch trực thuộc cơ sở nào — MỘT điều kiện SQL cho mọi màn.

`work_roster` không có cột cơ sở. Cơ sở của một ca = vị trí (`station`) →
`vi_tri_lam_viec.room_id` → `clinic_room.location_id`. Vị trí không gắn phòng
(`DIEU_PHOI`, mẫu cũ `LICH_KHAM`) hoặc phòng chưa gắn cơ sở thì thuộc MỌI cơ sở.

Vì sao có file này (Tuyền 08/10/2026, mở Hào Nam): màn Đặt lịch ở Hào Nam — nơi
chưa xếp một ca nào — vẫn hiện "Còn 96" cho các bác sĩ có ca ở Kim Ngưu, vì lưới
hỏi lịch trực chỉ theo `clinic_id + ngày`. Lịch làm việc thì đã lọc cơ sở nên hai
màn nói hai điều khác nhau.
"""

from __future__ import annotations


def ca_thuoc_co_so(bang: str, tham_so: str) -> str:
    """Điều kiện SQL: dòng `bang` (bí danh/tên bảng `work_roster`) thuộc cơ sở
    ``tham_so`` (vd ``"$4"``). Tham số NULL ⇒ không lọc (mọi cơ sở).

    Viết bằng NOT EXISTS chứ không JOIN để gắn được vào câu đang GROUP BY /
    array_agg mà không đổi số dòng. ``<> NULL`` là NULL nên tham số NULL tự
    thành "không loại dòng nào" — không cần nhánh riêng.
    """
    return f"""NOT EXISTS (
        SELECT 1 FROM public.vi_tri_lam_viec v_cs
          JOIN public.clinic_room r_cs ON r_cs.id = v_cs.room_id
         WHERE v_cs.clinic_id = {bang}.clinic_id AND v_cs.code = {bang}.station
           AND r_cs.location_id IS NOT NULL
           AND r_cs.location_id <> {tham_so}::uuid)"""
