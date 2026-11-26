"""Dựng sẵn thuốc trong danh mục cho bài kiểm lưu đơn bằng TÊN (26/11/2026, PR B).

Trước PR B, lưu đơn với tên chưa có trong danh mục tự thêm một thuốc "cần soát"
(không giá, không đơn vị). Đường đó đã bị giết: tên lạ → 422. Bài kiểm cũ vốn
dựa vào dòng tự thêm ấy thì gọi hàm này TRƯỚC khi lưu — dựng đúng dòng mà đường
cũ từng tạo (`needs_review`, không giá, không đơn vị), nên mọi kỳ vọng phía sau
(quầy thu chặn dòng không giá…) giữ nguyên nghĩa. Dữ liệu cũ như vậy vẫn còn
trên prod, nên các kỳ vọng ấy vẫn đáng canh.
"""

from __future__ import annotations

from typing import Any


def ten_go_tay(dong: Any) -> list[str]:
    """Tên của các dòng đơn không gửi mã thuốc kho."""
    return [
        str(d["drug_name"])
        for d in dong
        if d.get("drug_name") and not d.get("drug_catalog_id")
    ]


async def don_co_thuoc(db: Any, clinic_id: str, dong: Any) -> Any:
    """Dựng sẵn thuốc cho mọi tên gõ tay của `dong`, trả lại chính `dong`."""
    await co_thuoc(db, clinic_id, *ten_go_tay(dong))
    return dong


async def co_thuoc(db: Any, clinic_id: str, *ten: str) -> None:
    """`db`: kết nối hoặc pool asyncpg. Có rồi thì bật lại, không nhân đôi."""
    for t in ten:
        gon = " ".join(t.split())
        await db.execute(
            "INSERT INTO public.drug_catalog (clinic_id, name_raw, name_base,"
            " needs_review) VALUES ($1::uuid, $2, $2, true)"
            " ON CONFLICT (clinic_id, name_raw) DO UPDATE SET is_active = true",
            clinic_id,
            gon,
        )
