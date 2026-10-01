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
from clinicai.phieu_kham.mau_goi_y import mau_cho_cac_dich_vu
from clinicai.services.doi_tac_service import (
    LA_VIEC_DOI_TAC_SQL,
    trang_thai_doi_tac,
)
from clinicai.services.lam_them_tai_quay_service import nhan_lam_them

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
        # Màn cần mime để nhận ra DICOM (không vẽ được, chỉ tải về — đợt 3).
        "mime": r["mime"],
        "tai_len_luc": r["tai_len_luc"].isoformat(),
        "xac_nhan_trang_thai": r["xac_nhan_trang_thai"],
    }


async def doc_ket_qua_theo_chi_dinh(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> list[dict[str, Any]]:
    """Mỗi chỉ định (chưa huỷ) của lượt + kết quả của CHÍNH nó."""
    # "LẦN chỉ định" (Tuyền 25/09/2026: "chỉ định thêm 2, 3 lượt trong CÙNG một
    # lần khám") = cột `lan_chi_dinh`, trigger gán mỗi lần bấm chốt (26/09 — lát 4).
    # Trước đó lần suy từ vòng khám nên chỉ định thêm trong CÙNG phiên vẫn là
    # "Lần 1". Chỉ định mang sang từ lượt trước không có lần.
    don = await conn.fetch(
        "SELECT o.id, o.service_code, o.service_name, o.exec_status,"
        "       o.execution_status, o.created_at, o.mang_tu_visit_id, o.bat_buoc,"
        "       o.nguon_lam_them,"
        "       o.lan_chi_dinh, o.ket_qua_luc, o.doi_tac_cho_tai_lieu_luc,"
        # Việc của ĐỐI TÁC: bước làm bên ngoài HOẶC mẫu gửi đối tác (29/09/2026).
        "       " + LA_VIEC_DOI_TAC_SQL + " AS ben_ngoai,"
        # Dòng kết quả Y HỆT bản mẫu (27/09/2026): mã SP · giá · đã thu · đã xem.
        "       o.da_xem_ket_qua_luc, sp.ma_kiotviet, sp.unit_price,"
        "       EXISTS (SELECT 1 FROM payment_bill_line bl"
        "                 JOIN payment_cycle pc ON pc.clinic_id = bl.clinic_id"
        "                  AND pc.payment_cycle_id = bl.payment_cycle_id"
        "                WHERE bl.clinic_id = o.clinic_id"
        "                  AND bl.source_type = 'service_order'"
        "                  AND bl.source_id = o.id::text AND pc.status = 'PAID')"
        "         AS da_thu,"
        # Khách trả TRỰC TIẾP cho đối tác (27/09/2026): chip "Khách trả đối
        # tác" thay "Chờ thu tiền"; đối tác đã ghi nhận thu chưa.
        "       coalesce(sp.billing_owner = 'EXTERNAL_PARTNER', false)"
        "         AS doi_tac_thu,"
        "       EXISTS (SELECT 1 FROM doi_tac_thanh_toan tt"
        "                WHERE tt.clinic_id = o.clinic_id"
        "                  AND tt.service_order_id = o.id AND tt.huy_luc IS NULL)"
        "         AS doi_tac_da_thu"
        "  FROM service_order o"
        "  LEFT JOIN node_definition n"
        "    ON n.clinic_id = o.clinic_id AND n.code = o.node_code"
        "  LEFT JOIN LATERAL ("
        "       SELECT s.ma_kiotviet, s.unit_price, s.billing_owner"
        "         FROM service_price s"
        "        WHERE s.clinic_id = o.clinic_id AND s.service_code = o.service_code"
        "        ORDER BY s.active DESC LIMIT 1) sp ON true"
        " WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid"
        "   AND o.exec_status <> 'cancelled'"
        "   AND coalesce(o.execution_status, '') <> 'CANCELLED'"
        " ORDER BY o.created_at, o.id",
        clinic_id,
        visit_id,
    )
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
        "SELECT id, service_order_id, ten_hien_thi, loai_tep, mime, tai_len_luc,"
        "       xac_nhan_trang_thai"
        "  FROM v_tep_ket_qua_hieu_luc"
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
    # vào đây") thì mở đúng mẫu này. Chưa gắn: MÁY chọn (gợi ý v5 / CHUNG nhập
    # tự do — 01/10/2026), màn không tự quyết.
    chon_mau_dv = await mau_cho_cac_dich_vu(
        conn,
        clinic_id=clinic_id,
        service_codes=list({r["service_code"] for r in don}),
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
                # Mẫu ĐÃ GẮN (rỗng = quản lý chưa gắn) — chip "mẫu PDF / tự do".
                "mau_ket_qua": [
                    {"ma": m["ma"], "ten": m["ten"], "nhom": m["nhom"]}
                    for m in chon_mau_dv[r["service_code"]]["mau"]
                    if not chon_mau_dv[r["service_code"]]["mac_dinh"]
                ],
                # Mẫu để ĐIỀN: đã gắn, hoặc mặc định của máy khi chưa gắn.
                "mau_chon_duoc": chon_mau_dv[r["service_code"]]["mau"],
                "mau_chon_san": chon_mau_dv[r["service_code"]]["chon_san"],
                "mau_mac_dinh": chon_mau_dv[r["service_code"]]["mac_dinh"],
                "lan": r["lan_chi_dinh"],
                "chi_dinh_luc": (
                    r["created_at"].isoformat() if r["created_at"] else None
                ),
                "mang_sang": r["mang_tu_visit_id"] is not None,
                # Làm thêm tại quầy (01/10/2026) — lễ tân / người đo tick.
                "lam_them": nhan_lam_them(r["nguon_lam_them"]),
                "bat_buoc": bool(r["bat_buoc"]),
                "ma_kiotviet": r["ma_kiotviet"],
                "gia": int(r["unit_price"]) if r["unit_price"] is not None else None,
                "da_thu": bool(r["da_thu"]),
                "doi_tac_thu": bool(r["doi_tac_thu"]),
                "doi_tac_da_thu": bool(r["doi_tac_da_thu"]),
                "da_xem_luc": (
                    r["da_xem_ket_qua_luc"].isoformat()
                    if r["da_xem_ket_qua_luc"]
                    else None
                ),
                # Làm ở ĐỐI TÁC (phòng `lam_ben_ngoai`, hoặc mẫu gửi đối tác —
                # 29/09/2026): trạng thái bàn đối tác —
                # cùng một hàm với màn đối tác và CSKH (lát 4c, 26/09/2026).
                "doi_tac": (
                    trang_thai_doi_tac(
                        exec_status=r["exec_status"],
                        cho_tai_lieu=r["doi_tac_cho_tai_lieu_luc"] is not None,
                        co_ket_qua=r["ket_qua_luc"] is not None,
                    )
                    if r["ben_ngoai"]
                    else None
                ),
            }
        )
    return kq


async def doc_tep_chua_gan(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> list[dict[str, Any]]:
    """Tệp của CÙNG khách + CÙNG lịch hẹn của lượt mà CHƯA gắn chỉ định nào.

    Tệp tải ở màn Khách hàng trước 27/09 (đợt 3) chỉ mang `appointment_id` —
    không lọt vào dòng chỉ định nào, nên khối 2 không hiện, bác sĩ tưởng mất
    ảnh. KHÔNG tự ghép vào chỉ định theo tên (xem đầu tệp): chỉ hiện riêng là
    "n tệp chưa gắn chỉ định". Tệp thu hồi không hiện.
    """
    rows = await conn.fetch(
        "SELECT t.id, t.service_order_id, t.ten_hien_thi, t.loai_tep, t.mime,"
        "       t.tai_len_luc, t.xac_nhan_trang_thai"
        "  FROM v_tep_ket_qua_hieu_luc t"
        "  JOIN visit v ON v.clinic_id = t.clinic_id"
        "   AND v.appointment_id = t.appointment_id"
        "   AND v.clinic_patient_id = t.clinic_patient_id"
        " WHERE t.clinic_id = $1::uuid AND v.visit_id = $2::uuid"
        "   AND t.service_order_id IS NULL"
        "   AND t.thu_hoi_luc IS NULL"
        " ORDER BY t.tai_len_luc",
        clinic_id,
        visit_id,
    )
    return [_tom_tat_tep(r) for r in rows]


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


__all__ = ["doc_ket_qua_theo_chi_dinh", "doc_mau_du_phong", "doc_tep_chua_gan"]
