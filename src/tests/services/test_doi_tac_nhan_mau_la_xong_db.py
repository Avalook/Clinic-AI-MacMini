"""NHẬN MẪU LÀ XONG (Tuyền 29/09/2026).

"khi NHẬN MẪU là coi như XONG VIỆC … còn việc đối tác up kết quả lúc nào thì
THÔNG BÁO và ai cũng xem được … Phải xong để bác sĩ, điều dưỡng, TKYK cùng thao
tác cho khách còn về, chứ không 1 ca khám bao giờ mới kết thúc."

Một ca trọn: bác sĩ chờ kết quả xét nghiệm đối tác (VALID_RESULT) → đối tác bấm
"Nhận mẫu" (chưa bấm "Đã lấy mẫu") → yêu cầu vòng đọc ĐẠT, quầy không còn "chờ
kết quả", bác sĩ khép được lượt → lượt đóng rồi đối tác mới tải kết quả: tải
được, có chuông cho CSKH + bác sĩ chính, vòng đọc không mở lại.
"""

from __future__ import annotations

import pathlib
import uuid
from typing import Any

import pytest

from clinicai.api.v1.routers.doi_tac import _gui_ket_qua
from clinicai.events.catalogue import CHUONG, VONG_DOC
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.doi_tac_service import DoiTacService
from clinicai.services.nhan_tep_luong import TepDaNhan
from tests.chay_nguoi_dua_tin import chay_ben_nhan, danh_dau_doi_tac_da_nhan
from tests.services.test_luot_kham_service_db import (  # noqa: F401
    KichBan,
    _dat_doi_tac_lay_mau,
    _doi_tac,
    _vao_kham,
    _viec,
    kb,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

PDF = b"%PDF-1.4\nket qua xet nghiem doi tac\n%%EOF"


def _tep(tmp_path: pathlib.Path, ten: str) -> TepDaNhan:
    duong = tmp_path / ten
    duong.write_bytes(PDF)
    return TepDaNhan(
        duong=duong, ten=ten, so_byte=len(PDF), sha256=uuid.uuid4().hex, dau=PDF
    )


async def _yeu_cau(kb: KichBan, order_id: str) -> str:  # noqa: F811
    return str(
        await kb.pool.fetchval(
            "SELECT status FROM round_requirement WHERE service_order_id = $1::uuid",
            order_id,
        )
    )


async def test_nhan_mau_la_xong_luot_khep_duoc_ket_qua_ve_sau_co_chuong(
    kb: KichBan,  # noqa: F811
    tmp_path: pathlib.Path,
    monkeypatch: Any,
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    doi_tac = await _doi_tac(kb)
    await _dat_doi_tac_lay_mau(kb, True)
    svc = DoiTacService(kb.pool)
    try:
        phien = await _vao_kham(kb)
        duyet = await kb.svc.authorize_orders(
            consultation_id=phien,
            service_codes=[kb.ma_mau],
            draft_order_ids=None,
            identity=kb.bac_si,
        )
        mau_id = duyet["order_ids"][0]
        # Bác sĩ chờ KẾT QUẢ xét nghiệm đối tác rồi mới đọc.
        await kb.svc.complete_consultation(
            consultation_id=phien,
            outcome="SERVICES",
            requirements=[{"order_id": mau_id, "need": "VALID_RESULT"}],
            identity=kb.bac_si,
        )
        await danh_dau_doi_tac_da_nhan(kb.pool, mau_id)
        assert await _yeu_cau(kb, mau_id) == "open"
        truoc = await CheckoutService(kb.pool).readiness(
            identity=kb.le_tan, visit_id=kb.visit_id
        )
        assert "lab_pending" in {b["type"] for b in truoc["blockers"]}

        # Đối tác bấm "Nhận mẫu" thẳng (bận, chưa bấm "Đã lấy mẫu").
        kq = await svc.doi_tac_cho_tai_lieu(order_id=mau_id, identity=doi_tac)
        assert kq["already"] is False
        o = await kb.pool.fetchrow(
            "SELECT exec_status, doi_tac_cho_tai_lieu_luc FROM service_order"
            " WHERE id = $1::uuid",
            mau_id,
        )
        assert o["exec_status"] == "performed"  # nhận mẫu ⇒ đã lấy mẫu
        assert o["doi_tac_cho_tai_lieu_luc"] is not None
        assert (
            await kb.pool.fetchval(
                "SELECT count(*) FROM domain_event WHERE event_type ="
                " 'partner.sample_received' AND aggregate_id = $1::uuid",
                mau_id,
            )
            == 1
        )

        # Bàn đối tác: nhóm ĐÃ NHẬN MẪU · XONG, không còn tính là việc dở.
        ban = await svc.viec_doi_tac(identity=doi_tac)
        viec = _viec(ban, mau_id)
        assert viec is not None and viec["trang_thai"] == "DA_NHAN_MAU"

        # Vòng đọc nghe sự kiện: yêu cầu ĐẠT dù CHƯA có tệp nào.
        await chay_ben_nhan(kb.pool, VONG_DOC)
        assert await _yeu_cau(kb, mau_id) == "satisfied"
        yc_id = await kb.pool.fetchval(
            "SELECT id::text FROM round_requirement WHERE service_order_id = $1::uuid",
            mau_id,
        )
        cho = (await kb.svc.cho_quyet(identity=kb.bac_si))["viec"]
        assert yc_id not in {v["id"] for v in cho}
        sau = await CheckoutService(kb.pool).readiness(
            identity=kb.le_tan, visit_id=kb.visit_id
        )
        loai = {b["type"] for b in sau["blockers"]}
        assert "lab_pending" not in loai and "service_open" not in loai

        # Bác sĩ khép lượt (phiên đọc lại mở vì vòng đã đủ) — không chờ tệp.
        rev_id = await kb.pool.fetchval(
            "SELECT id::text FROM consultation"
            " WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kb.visit_id,
        )
        assert rev_id is not None
        await kb.svc.start_consultation(consultation_id=rev_id, identity=kb.bac_si)
        await kb.svc.complete_consultation(
            consultation_id=rev_id,
            outcome="DONE",
            requirements=None,
            identity=kb.bac_si,
        )
        dong = await CheckoutService(kb.pool).readiness(
            identity=kb.le_tan, visit_id=kb.visit_id
        )
        loai = {b["type"] for b in dong["blockers"]}
        assert not loai & {"lab_pending", "service_open", "exam_open"}
        assert (
            await kb.pool.fetchval(
                "SELECT exam_completed_at IS NOT NULL FROM visit"
                " WHERE visit_id = $1::uuid",
                kb.visit_id,
            )
            is True
        )

        # Lượt ĐÃ ĐÓNG, đối tác mới gửi kết quả: vẫn tải được + có chuông.
        await kb.pool.execute(
            "UPDATE visit SET status = 'FINALIZED' WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
        tai = await _gui_ket_qua(
            kb.pool, doi_tac, {"chi_dinh_id": mau_id}, _tep(tmp_path, "kq.pdf")
        )
        assert tai["ok"] is True
        await _gui_ket_qua(
            kb.pool, doi_tac, {"chi_dinh_id": mau_id}, _tep(tmp_path, "kq-2.pdf")
        )
        await chay_ben_nhan(kb.pool, CHUONG, VONG_DOC)
        chuong = await kb.pool.fetch(
            "SELECT vai_nhan, nguoi_nhan_staff_id::text AS nguoi, tieu_de"
            " FROM thong_bao WHERE nguon_id = $1",
            f"ket_qua_doi_tac:{mau_id}",
        )
        assert chuong, "kết quả đối tác phải có chuông"
        assert all(c["tieu_de"].startswith("Có kết quả đối tác:") for c in chuong)
        # Hai tệp gửi liền — một chuông cho mỗi người nhận.
        assert len([c for c in chuong if c["vai_nhan"] == "CSKH"]) == 1
        assert [c["nguoi"] for c in chuong if c["nguoi"]] == [kb.bac_si.staff_id]
        # Vòng đọc không mở lại, không thêm phiên đọc.
        assert (
            await kb.pool.fetchval(
                "SELECT count(*) FROM consultation WHERE visit_id = $1::uuid"
                " AND kind = 'REVIEW'",
                kb.visit_id,
            )
            == 1
        )
        viec = _viec(await svc.viec_doi_tac(identity=doi_tac), mau_id)
        assert viec is not None and viec["trang_thai"] == "DA_GUI_KET_QUA"
        assert [t["ten"] for t in viec["tep"]] == ["kq.pdf", "kq-2.pdf"]
    finally:
        await _dat_doi_tac_lay_mau(kb, False)


async def test_nhan_mau_bam_lai_khong_doi_moc_va_bang_dem_dung(
    kb: KichBan,  # noqa: F811
) -> None:
    doi_tac = await _doi_tac(kb)
    await _dat_doi_tac_lay_mau(kb, True)
    svc = DoiTacService(kb.pool)
    try:
        phien = await _vao_kham(kb)
        duyet = await kb.svc.authorize_orders(
            consultation_id=phien,
            service_codes=[kb.ma_mau],
            draft_order_ids=None,
            identity=kb.bac_si,
        )
        mau_id = duyet["order_ids"][0]
        await danh_dau_doi_tac_da_nhan(kb.pool, mau_id)
        ban = await svc.viec_doi_tac(identity=doi_tac)
        truoc = ban["so_viec"]
        assert _viec(ban, mau_id)["trang_thai"] == "CHO_LAY_MAU"  # type: ignore[index]

        await svc.doi_tac_cho_tai_lieu(order_id=mau_id, identity=doi_tac)
        ban = await svc.viec_doi_tac(identity=doi_tac)
        viec = _viec(ban, mau_id)
        assert viec is not None and viec["trang_thai"] == "DA_NHAN_MAU"
        # Đã nhận mẫu = xong: không còn đếm là việc dở.
        assert ban["so_viec"] == truoc - 1
        moc = viec["cho_tai_lieu_luc"]
        lai = await svc.doi_tac_cho_tai_lieu(order_id=mau_id, identity=doi_tac)
        assert lai["already"] is True
        viec = _viec(await svc.viec_doi_tac(identity=doi_tac), mau_id)
        assert viec is not None and viec["cho_tai_lieu_luc"] == moc
    finally:
        await _dat_doi_tac_lay_mau(kb, False)
