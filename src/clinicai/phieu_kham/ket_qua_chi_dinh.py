"""Kết quả cận lâm sàng hiện về ĐÚNG chỉ định — gắn bằng `service_order_id`.

Nguồn chốt: *"Result phải gắn bằng service_order_id / execution_id, không dò
theo tên dịch vụ."* Hai chỉ định cùng một dịch vụ (siêu âm vú lần sáng, lần
chiều) là HAI dòng `service_order`; kết quả của lần này không bao giờ được hiện
ở lần kia chỉ vì tên giống nhau. Nên mọi phép nối ở đây đi qua `id`, không qua
`service_code`, càng không qua `service_name` — tên chỉ để hiển thị.

HAI LỚP TRẠNG THÁI, KHÔNG GỘP (nguồn: *"Đã làm không đồng nghĩa đã duyệt kết
quả"*). `thuc_hien` là của module Thực hiện; `ket_qua` là của phiếu kết quả /
tệp. Một chỉ định có thể "Đã làm" mà kết quả còn đang nhập.

NHÁP KHÔNG PHẢI KẾT QUẢ. Phiếu kết quả còn DRAFT thì chỉ báo "đang nhập", không
trả nội dung — chưa ai chịu trách nhiệm về chữ trong đó. Phiếu READY đang được
sửa lại thì bản trả về vẫn là bản CHÍNH THỨC (`du_lieu`), không phải bản nháp.

CHỈ ĐỌC. Không ghi bảng nào của module khác.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from clinicai.phieu_kham.khung import FORM_IDS

#: Bảy phiếu khám KHÔNG phải kết quả CLS — chúng là nơi ĐỌC kết quả, và gắn vào
#: consultation/visit chứ không vào chỉ định. Chỉ phiếu kết quả dịch vụ (18 mẫu
#: `KQ_*`, và mẫu sau này) mới gắn `service_order_id`.
_PHIEU_KHONG_PHAI_KET_QUA = list(FORM_IDS)


def _tom_tat_phieu(r: asyncpg.Record) -> dict[str, Any]:
    san_sang = r["trang_thai"] == "READY"
    return {
        "loai": "PHIEU",
        "phieu_id": str(r["id"]),
        "form_id": r["form_id"],
        "version": r["version"],
        "ten": r["ten"],
        "trang_thai": r["trang_thai"],
        # Đang sửa lại: màn phải nói ra, nhưng nội dung dưới đây vẫn là bản
        # chính thức cho tới lúc [Xác nhận sửa].
        "dang_sua": bool(r["dang_sua"]),
        # Bản chuyên môn thứ mấy: 1 + số lần sửa đã xác nhận.
        "ban_thu": 1 + int(r["so_lan_sua"]) if san_sang else None,
        "hoan_tat_luc": r["hoan_tat_luc"].isoformat() if r["hoan_tat_luc"] else None,
        "khung": json.loads(r["khung"]) if san_sang else None,
        "du_lieu": json.loads(r["du_lieu"]) if san_sang else None,
    }


def _tom_tat_tep(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "loai": "TEP",
        "tep_id": str(r["id"]),
        "ten": r["ten_hien_thi"],
        "loai_tep": r["loai_tep"],
        "tai_len_luc": r["tai_len_luc"].isoformat(),
        "xac_nhan_trang_thai": r["xac_nhan_trang_thai"],
    }


async def doc_ket_qua_theo_chi_dinh(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> list[dict[str, Any]]:
    """Mỗi chỉ định (chưa huỷ) của lượt + kết quả của CHÍNH nó."""
    # `vong` = vòng khám (phiên) đã ra chỉ định — nguồn của "LẦN chỉ định"
    # (Tuyền 25/09/2026: "chỉ định thêm 2, 3 lượt trong CÙNG một lần khám").
    # Chỉ định mang sang từ lượt trước không thuộc vòng nào của lượt này.
    don = await conn.fetch(
        "SELECT o.id, o.service_code, o.service_name, o.exec_status,"
        "       o.execution_status, o.created_at, o.mang_tu_visit_id, o.bat_buoc,"
        "       CASE WHEN c.visit_id = o.visit_id THEN c.round_no END AS vong"
        "  FROM service_order o"
        "  LEFT JOIN consultation c"
        "    ON c.id = o.consultation_id AND c.clinic_id = o.clinic_id"
        " WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid"
        "   AND o.exec_status <> 'cancelled'"
        "   AND coalesce(o.execution_status, '') <> 'CANCELLED'"
        " ORDER BY o.created_at, o.id",
        clinic_id,
        visit_id,
    )
    # Vòng → lần 1, 2, 3… theo thứ tự các vòng CÓ chỉ định (tư vấn là vòng 0).
    lan_cua_vong = {
        v: i
        for i, v in enumerate(
            sorted({r["vong"] for r in don if r["vong"] is not None}), start=1
        )
    }
    if not don:
        return []
    ids = [r["id"] for r in don]

    phieu = await conn.fetch(
        "SELECT i.id, i.service_order_id, i.form_id, i.version, i.trang_thai,"
        "       i.dang_sua, i.du_lieu, i.hoan_tat_luc, d.ten, d.khung,"
        "       (SELECT count(*) FROM result_correction c"
        "         WHERE c.clinic_id = i.clinic_id AND c.form_instance_id = i.id)"
        "         AS so_lan_sua"
        "  FROM form_instance i"
        "  JOIN form_definition d"
        "    ON d.clinic_id = i.clinic_id AND d.form_id = i.form_id"
        "   AND d.version = i.version"
        " WHERE i.clinic_id = $1::uuid AND i.service_order_id = ANY($2::uuid[])"
        "   AND NOT (i.form_id = ANY($3::text[]))"
        " ORDER BY i.hoan_tat_luc DESC NULLS LAST, i.tao_luc DESC",
        clinic_id,
        ids,
        _PHIEU_KHONG_PHAI_KET_QUA,
    )
    tep = await conn.fetch(
        "SELECT id, service_order_id, ten_hien_thi, loai_tep, tai_len_luc,"
        "       xac_nhan_trang_thai"
        "  FROM tep_ket_qua"
        " WHERE clinic_id = $1::uuid AND service_order_id = ANY($2::uuid[])"
        # Tệp đã thu hồi không còn là kết quả — giữ trong kho để đối chiếu,
        # nhưng không được hiện như thể vẫn còn hiệu lực.
        "   AND thu_hoi_luc IS NULL"
        " ORDER BY tai_len_luc DESC",
        clinic_id,
        ids,
    )

    # Mẫu kết quả đã GẮN cho từng dịch vụ (Danh mục & biểu mẫu). Bác sĩ điền
    # kết quả ngay trong phiếu khám (Tuyền 23/09: "khỏi duyệt kết quả, tự điền
    # vào đây") thì mở đúng mẫu này; chưa gắn thì màn cho chọn mẫu dự phòng.
    gan_mau: dict[str, list[dict[str, Any]]] = {}
    for r in await conn.fetch(
        "SELECT d.service_code, m.ma, m.ten, m.nhom FROM dich_vu_mau_ket_qua d"
        "  JOIN ket_qua_mau m ON m.clinic_id = d.clinic_id AND m.ma = d.mau"
        "   AND m.active"
        " WHERE d.clinic_id = $1::uuid AND d.service_code = ANY($2::text[])"
        " ORDER BY m.ten",
        clinic_id,
        list({r["service_code"] for r in don}),
    ):
        gan_mau.setdefault(r["service_code"], []).append(
            {"ma": r["ma"], "ten": r["ten"], "nhom": r["nhom"]}
        )

    theo_don: dict[Any, list[dict[str, Any]]] = {i: [] for i in ids}
    for r in phieu:
        theo_don[r["service_order_id"]].append(_tom_tat_phieu(r))
    for r in tep:
        theo_don[r["service_order_id"]].append(_tom_tat_tep(r))

    kq = []
    for r in don:
        cua_no = theo_don[r["id"]]
        co = any(
            (k["loai"] == "PHIEU" and k["trang_thai"] == "READY") or k["loai"] == "TEP"
            for k in cua_no
        )
        dang_nhap = any(
            k["loai"] == "PHIEU" and k["trang_thai"] == "DRAFT" for k in cua_no
        )
        kq.append(
            {
                "service_order_id": str(r["id"]),
                "service_code": r["service_code"],
                # CHỈ ĐỂ HIỂN THỊ. Không đem đi so khớp với gì cả.
                "ten_hien_thi": r["service_name"],
                "thuc_hien": r["execution_status"] or r["exec_status"],
                "ket_qua_trang_thai": (
                    "CO_KET_QUA" if co else "DANG_NHAP" if dang_nhap else "CHUA_CO"
                ),
                "ket_qua": cua_no,
                "mau_ket_qua": gan_mau.get(r["service_code"], []),
                "lan": lan_cua_vong.get(r["vong"]),
                "chi_dinh_luc": (
                    r["created_at"].isoformat() if r["created_at"] else None
                ),
                "mang_sang": r["mang_tu_visit_id"] is not None,
                "bat_buoc": bool(r["bat_buoc"]),
            }
        )
    return kq


async def doc_mau_du_phong(
    conn: asyncpg.Connection, *, clinic_id: str
) -> list[dict[str, Any]]:
    """18 mẫu kết quả đang bật — "Mẫu dự phòng: mở nhanh 18 biểu mẫu" (v5)."""
    return [
        dict(r)
        for r in await conn.fetch(
            "SELECT ma, ten, nhom FROM ket_qua_mau"
            " WHERE clinic_id = $1::uuid AND active ORDER BY nhom, ten",
            clinic_id,
        )
    ]


__all__ = ["doc_ket_qua_theo_chi_dinh", "doc_mau_du_phong"]
