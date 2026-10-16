"""Việc của ĐỐI TÁC xét nghiệm — danh sách việc, chờ tài liệu, đã lấy mẫu.

Bóc khỏi ``luot_kham_service`` ngày 24/09/2026 (bước 4 đợt bóc lõi). Khối
``doi_tac`` (modules.py): ghi bảng của mình rồi PHÁT ``partner.sample_collected``.
Vòng đọc + khép lượt KHÔNG gọi thẳng nữa — khối VÒNG ĐỌC nghe sự kiện ấy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import doc_ngay_xem, hom_nay_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import (
    DoiTacDaLayMau,
    DoiTacDaNhanMau,
    DoiTacDaThuTien,
    DoiTacHoanTacNhanMau,
    DoiTacHoanTacTraKetQua,
    DoiTacHuyThuTien,
    DoiTacTraKetQua,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
from clinicai.services.audit import record_event
from clinicai.services.hang_cho import (
    cap_nhat_vi_tri,
    mo_cho_bi_chan,
)
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.lenh_kham_core import ma_uuid as _uuid
from clinicai.services.service_routing_service import DOI_TAC_LAM_TRON_SQL

logger = structlog.get_logger()

#: Giữ nguồn nhật ký cũ — đọc lại event_log không phải đổi truy vấn.
ORIGIN = "api:luot-kham"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


#: "VIỆC CỦA ĐỐI TÁC" — một chỗ nói cho mọi lệnh của bàn đối tác (29/09/2026):
#: bước làm bên ngoài (node `lam_ben_ngoai`) HOẶC chỉ định ĐÃ SANG bàn đối tác
#: (`doi_tac_nhan_viec`) — gồm MẪU GỬI ĐỐI TÁC: dịch vụ thu hộ đối tác làm ở
#: phòng của phòng khám (Giải phẫu bệnh, Sinh thiết + GPB ở phòng Thủ thuật), đã
#: xong nên mẫu gửi sang đối tác. Dùng với bí danh chỉ định `o` và
#: `LEFT JOIN node_definition n`.
LA_VIEC_DOI_TAC_SQL = """(coalesce(n.lam_ben_ngoai, false) OR EXISTS (
        SELECT 1 FROM public.doi_tac_nhan_viec dnv
         WHERE dnv.clinic_id = o.clinic_id AND dnv.service_order_id = o.id))"""

#: Hình thức khách trả đối tác (khớp CHECK của `doi_tac_thanh_toan`).
HINH_THUC_THU = ("CASH", "TRANSFER")

#: Trần một ghi nhận — chặn gõ thừa số 0 (100.000.000 đồng / một việc).
SO_TIEN_TOI_DA = 100_000_000


def doc_so_tien(value: Any) -> int | None:
    """Số tiền đối tác ghi nhận đã thu. Rác / âm / quá trần → None, không ném.

    Nhận số nguyên, chuỗi có dấu chấm / phẩy / khoảng trắng / "đ" ("900.000đ").
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        so = value
    elif isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        if value != int(value):
            return None
        so = int(value)
    elif isinstance(value, str):
        chu = value.strip().lower().replace("đ", "").replace("vnd", "")
        for k in (".", ",", " ", "\u00a0", "_"):
            chu = chu.replace(k, "")
        if not chu.isdigit():
            return None
        so = int(chu)
    else:
        return None
    if so < 0 or so > SO_TIEN_TOI_DA:
        return None
    return so


def doc_hinh_thuc(value: Any) -> str | None:
    """CASH / TRANSFER (không phân biệt hoa thường). Rác → None."""
    if not isinstance(value, str):
        return None
    v = value.strip().upper()
    return v if v in HINH_THUC_THU else None


#: Trạng thái việc đối tác đã XONG — nhận mẫu là xong, kết quả về sau tuỳ ý.
VIEC_DOI_TAC_XONG = frozenset({"DA_NHAN_MAU", "DA_GUI_KET_QUA"})


def trang_thai_doi_tac(
    *, exec_status: str, cho_tai_lieu: bool, co_ket_qua: bool
) -> str:
    """Trạng thái một việc trên bàn đối tác — một chỗ tính cho cả đối tác lẫn CSKH.

    DA_GUI_KET_QUA > DA_NHAN_MAU > DA_LAY_MAU > CHO_LAY_MAU.

    NHẬN MẪU LÀ XONG (Tuyền 29/09/2026): *"khi NHẬN MẪU là coi như XONG VIỆC …
    còn việc đối tác up kết quả lúc nào thì THÔNG BÁO … KHÔNG được hiển thị là
    việc này chưa xong"*. `DA_NHAN_MAU` và `DA_GUI_KET_QUA` đều là XONG
    (`VIEC_DOI_TAC_XONG`); có kết quả chỉ là mốc tuỳ chọn về sau. Tham số
    `cho_tai_lieu` giữ tên cột cũ (`doi_tac_cho_tai_lieu_luc` = mốc nhận mẫu).
    """
    if co_ket_qua:
        return "DA_GUI_KET_QUA"
    if cho_tai_lieu:
        return "DA_NHAN_MAU"
    if exec_status == "performed":
        return "DA_LAY_MAU"
    return "CHO_LAY_MAU"


#: CHỮ trạng thái việc đối tác — MỘT bộ chữ cho mọi màn (Tuyền 16/10/2026:
#: "chỉ hai chữ riêng của đối tác"). Trước khi nhận mẫu dùng chữ CHUNG của mọi
#: dịch vụ ("Chờ làm"); không còn "Chờ lấy mẫu" / "Có mẫu · chờ nhận".
CHU_CHO_LAM = "Chờ làm"
CHU_DA_NHAN_MAU = "Đã nhận mẫu · chờ kết quả"
CHU_CO_KET_QUA = "Có kết quả"
CHU_TRANG_THAI_DOI_TAC: dict[str, str] = {
    "CHO_LAY_MAU": CHU_CHO_LAM,
    "DA_LAY_MAU": CHU_CHO_LAM,
    "DA_NHAN_MAU": CHU_DA_NHAN_MAU,
    "DA_GUI_KET_QUA": CHU_CO_KET_QUA,
}


def chu_trang_thai_doi_tac(trang_thai: str | None) -> str:
    """Mã trạng thái (`trang_thai_doi_tac`) → chữ hiển thị. Mã lạ → "Chờ làm"."""
    return CHU_TRANG_THAI_DOI_TAC.get(trang_thai or "", CHU_CHO_LAM)


async def _ghi_chu_doi_tac(
    conn: asyncpg.Connection, cid: str, oid: str, cot: str, ghi_chu: str | None
) -> None:
    """Ghi chú của đối tác vào dòng nhận việc (bảng của khối Đối tác)."""
    ghi = (ghi_chu or "").strip() or None
    if ghi is None:
        return
    if len(ghi) > 2000:
        raise LuotKhamConflictError(
            "NOTE_TOO_LONG", "Ghi chú quá dài (tối đa 2.000 ký tự)."
        )
    sql = {
        "ghi_chu_lay_mau": "UPDATE doi_tac_nhan_viec SET ghi_chu_lay_mau = $3",
        "ghi_chu_tai_lieu": "UPDATE doi_tac_nhan_viec SET ghi_chu_tai_lieu = $3",
    }[cot]
    await conn.execute(
        sql + " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid",
        cid,
        oid,
        ghi,
    )


#: Mọi cột một VIỆC trên bàn đối tác / Phòng đối tác — MỘT câu cho danh sách
#: (`viec_doi_tac`) lẫn một việc (`mot_viec`), để hai màn không lệch nhau. Đòi
#: thêm điều kiện ở `{where}`; `nv` (dòng nhận việc) là LEFT JOIN — danh sách tự
#: thêm `nv.service_order_id IS NOT NULL`.
_VIEC_SQL = (
    """
            SELECT o.id::text AS chi_dinh_id, o.service_code, o.exec_status,
                   o.visit_id::text AS visit_id,
                   coalesce(sp.name, o.service_name) AS ten_dich_vu,
                   coalesce(sp.doi_tac_lay_mau, false) AS doi_tac_lay_mau,
                   p.full_name AS ten_khach, p.patient_code AS ma_khach,
                   p.clinic_patient_id::text AS clinic_patient_id,
                   v.appointment_id::text AS appointment_id,
                   o.created_at, o.finished_at, o.ket_qua_luc,
                   o.doi_tac_cho_tai_lieu_luc,
                   nv.ghi_chu_lay_mau, nv.ghi_chu_tai_lieu,
                   nullif(btrim(coalesce(o.result_note, '')), '') IS NOT NULL
                     AS co_ket_qua_chu,
                   -- Thu hộ đối tác (27/09/2026): giá tham khảo + đã ghi nhận chưa.
                   sp.unit_price AS gia_tham_khao,
                   coalesce(sp.billing_owner = 'EXTERNAL_PARTNER', false)
                     AS doi_tac_thu,
                   -- Mẫu gửi đối tác (29/09/2026): phòng CỦA phòng khám làm
                   -- xong, mẫu sang đối tác — không phải bước làm bên ngoài.
                   NOT coalesce(n.lam_ben_ngoai, false) AS mau_gui_doi_tac,
                   """
    + DOI_TAC_LAM_TRON_SQL
    + """ AS doi_tac_lam,
                   tt.id::text AS thu_id, tt.so_tien AS thu_so_tien,
                   tt.hinh_thuc AS thu_hinh_thuc, tt.ghi_chu AS thu_ghi_chu,
                   tt.ghi_luc AS thu_luc, tn.full_name AS thu_boi
              FROM service_order o
              JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
              LEFT JOIN appointment ap
                ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
              JOIN patient p
                ON p.clinic_patient_id = v.clinic_patient_id
               AND p.clinic_id = v.clinic_id
              LEFT JOIN node_definition n
                ON n.clinic_id = o.clinic_id AND n.code = o.node_code
              LEFT JOIN doi_tac_nhan_viec nv
                ON nv.clinic_id = o.clinic_id AND nv.service_order_id = o.id
              LEFT JOIN LATERAL (
                   SELECT s.name, s.doi_tac_lay_mau, s.unit_price, s.billing_owner
                     FROM service_price s
                    WHERE s.clinic_id = o.clinic_id
                      AND s.service_code = o.service_code AND s.active
                    ORDER BY (s."group" = 'dich_vu') DESC LIMIT 1) sp ON true
              LEFT JOIN doi_tac_thanh_toan tt
                ON tt.clinic_id = o.clinic_id AND tt.service_order_id = o.id
               AND tt.huy_luc IS NULL
              LEFT JOIN staff tn ON tn.id = tt.ghi_boi
             WHERE o.clinic_id = $1::uuid
               AND {where}
            """
)


class DoiTacService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _doi_quyen_doi_tac(self, identity: StaffIdentity, cau: str) -> None:
        """Lego 21 "Đối tác" (quyền `partner.work`) — cùng câu router hỏi
        (`get_partner_identity`). Trước 27/09/2026 hỏi vai PARTNER/MANAGEMENT,
        nên quyền này là nhãn: thu lego không mất gì."""
        async with self._pool.acquire() as conn:
            if not await can(conn, identity, "partner.work"):
                raise SafetyGateError(cau)

    async def _dung_viec(
        self, identity: StaffIdentity, rows: list[asyncpg.Record]
    ) -> tuple[list[dict[str, Any]], bool]:
        """Dòng `_VIEC_SQL` → việc (đủ chữ, tệp, mẫu kết quả, phiếu, cờ nút).

        LỊCH SỬ CÁC LẦN TẢI của từng việc (29/09/2026): tên, loại, giờ, AI tải
        — kể cả tệp đã thu hồi (ghi rõ), để không ai phải hỏi "hôm qua gửi
        những gì". Đường mở tệp đi cửa đọc tệp chung (`/cskh/ket-qua`), cửa ấy
        tự hỏi `doc_duoc_tep_ket_qua` — vai PARTNER bên ngoài vẫn không mở được.

        XOÁ MỀM (V9 30/09/2026): tệp đã xoá VẪN nằm trong lịch sử (ghi rõ
        "đã xoá" + lý do), như tệp thu hồi; kèm cờ máy chủ `xoa_duoc` (tệp còn
        hiệu lực) / `khoi_phuc_duoc` (tệp đã xoá, trong 30 ngày).

        PHIẾU KẾT QUẢ THEO MẪU (16/10/2026): mỗi việc kèm mẫu kết quả của loại
        chỉ định (`mau_goi_y.chon_mau` — mẫu đã gắn → mẫu gợi ý → mẫu CHUNG) và
        phiếu đã mở, để điền rồi [Trả kết quả] ngay tại bàn / Phòng đối tác.
        """
        from clinicai.phieu_kham.mau_goi_y import mau_cho_cac_dich_vu
        from clinicai.services.tep_ket_qua_service import (
            COT_XOA_SQL,
            gan_co_xoa,
            quyen_xoa_tep,
        )

        ids = [r["chi_dinh_id"] for r in rows]
        async with self._pool.acquire() as conn:
            quyen = await quyen_xoa_tep(conn, identity)
            ds_tep = await conn.fetch(
                f"""
                SELECT t.service_order_id::text AS chi_dinh_id, t.id::text AS id,
                       t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte,
                       t.tai_len_luc, s.full_name AS tai_len_boi, t.thu_hoi_luc,
                       t.xac_nhan_trang_thai,
                       {COT_XOA_SQL}
                  FROM tep_ket_qua t
                  LEFT JOIN staff s ON s.id = t.tai_len_boi_staff_id
                 WHERE t.clinic_id = $1::uuid
                   AND t.service_order_id = ANY($2::uuid[])
                   AND t.da_don_tep_luc IS NULL
                 ORDER BY t.tai_len_luc, t.id
                """,
                identity.clinic_id,
                ids,
            )
            ds_phieu = await conn.fetch(
                "SELECT service_order_id::text AS chi_dinh_id, id::text AS id,"
                "       form_id, trang_thai"
                "  FROM form_instance"
                " WHERE clinic_id = $1::uuid AND service_order_id = ANY($2::uuid[])"
                " ORDER BY (trang_thai = 'READY') DESC,"
                "          hoan_tat_luc DESC NULLS LAST, tao_luc DESC",
                identity.clinic_id,
                ids,
            )
            mau = await mau_cho_cac_dich_vu(
                conn,
                clinic_id=identity.clinic_id,
                service_codes=[r["service_code"] for r in rows if r["service_code"]],
            )
        tep_theo_viec: dict[str, list[dict[str, Any]]] = {}
        co_tep: set[str] = set()
        for t in ds_tep:
            co = gan_co_xoa(t, quyen)
            con_hieu_luc = (
                t["thu_hoi_luc"] is None
                and t["da_xoa_luc"] is None
                and (t["xac_nhan_trang_thai"] in (None, "CHO_XAC_NHAN", "HOP_LE"))
            )
            if con_hieu_luc:
                co_tep.add(t["chi_dinh_id"])
            tep_theo_viec.setdefault(t["chi_dinh_id"], []).append(
                {
                    "id": t["id"],
                    "ten": t["ten_hien_thi"],
                    "loai": t["loai_tep"],
                    "mime": t["mime"],
                    "so_byte": int(t["so_byte"] or 0),
                    "luc": _iso(t["tai_len_luc"]),
                    "boi": t["tai_len_boi"],
                    "thu_hoi": t["thu_hoi_luc"] is not None,
                    "da_xoa": t["da_xoa_luc"] is not None,
                    "da_xoa_ly_do": t["da_xoa_ly_do"],
                    "xoa_duoc": bool(co.get("xoa_duoc")),
                    "xoa_loai": co.get("xoa_loai"),
                    "xoa_ly_do": co.get("xoa_ly_do"),
                    "khoi_phuc_duoc": bool(co.get("khoi_phuc_duoc")),
                }
            )
        phieu_theo_viec: dict[str, list[dict[str, Any]]] = {}
        for f in ds_phieu:
            phieu_theo_viec.setdefault(f["chi_dinh_id"], []).append(
                {"id": f["id"], "form_id": f["form_id"], "trang_thai": f["trang_thai"]}
            )
        out: list[dict[str, Any]] = []
        for r in rows:
            oid = r["chi_dinh_id"]
            tt = trang_thai_doi_tac(
                exec_status=r["exec_status"],
                cho_tai_lieu=r["doi_tac_cho_tai_lieu_luc"] is not None,
                co_ket_qua=r["ket_qua_luc"] is not None,
            )
            phieu = phieu_theo_viec.get(oid, [])
            co_noi_dung = (
                oid in co_tep
                or bool(r["co_ket_qua_chu"])
                or any(f["trang_thai"] == "READY" for f in phieu)
            )
            m = mau.get(r["service_code"] or "", {})
            out.append(
                {
                    "chi_dinh_id": oid,
                    "ten_dich_vu": r["ten_dich_vu"],
                    "appointment_id": r["appointment_id"],
                    "chi_dinh_luc": _iso(r["created_at"]),
                    "trang_thai": tt,
                    # Chữ máy chủ viết (16/10/2026) — mọi màn cùng một bộ chữ.
                    "trang_thai_chu": chu_trang_thai_doi_tac(tt),
                    "lay_mau_luc": _iso(r["finished_at"]),
                    "cho_tai_lieu_luc": _iso(r["doi_tac_cho_tai_lieu_luc"]),
                    "ket_qua_luc": _iso(r["ket_qua_luc"]),
                    "ghi_chu_lay_mau": r["ghi_chu_lay_mau"],
                    "ghi_chu_tai_lieu": r["ghi_chu_tai_lieu"],
                    "tep": tep_theo_viec.get(oid, []),
                    # Nhãn "Mẫu gửi đối tác" (29/09/2026).
                    "mau_gui_doi_tac": bool(r["mau_gui_doi_tac"]),
                    # Đối tác làm trọn (Phòng đối tác nhận, 16/10/2026).
                    "doi_tac_lam": bool(r["doi_tac_lam"]),
                    # Khách trả TRỰC TIẾP cho đối tác (Q1, 27/09/2026).
                    "doi_tac_thu": bool(r["doi_tac_thu"]),
                    "gia_tham_khao": (
                        int(r["gia_tham_khao"])
                        if r["gia_tham_khao"] is not None
                        else None
                    ),
                    "da_thu": (
                        {
                            "id": r["thu_id"],
                            "so_tien": int(r["thu_so_tien"]),
                            "hinh_thuc": r["thu_hinh_thuc"],
                            "ghi_chu": r["thu_ghi_chu"],
                            "luc": _iso(r["thu_luc"]),
                            "boi": r["thu_boi"],
                        }
                        if r["thu_id"]
                        else None
                    ),
                    # Phiếu kết quả theo mẫu của loại chỉ định (16/10/2026).
                    "mau_ket_qua": m.get("mau", []),
                    "mau_goi_y": m.get("chon_san"),
                    "phieu": phieu,
                    # CỜ NÚT — máy chủ quyết, màn chỉ ẩn / hiện.
                    "nhan_mau_duoc": r["doi_tac_cho_tai_lieu_luc"] is None
                    and r["exec_status"] not in ("not_performed", "cancelled"),
                    "co_noi_dung_ket_qua": co_noi_dung,
                    "tra_ket_qua_duoc": r["ket_qua_luc"] is None and co_noi_dung,
                }
            )
        return out, quyen.doc_duoc

    async def mot_viec(
        self, *, order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """MỘT việc đối tác (Phòng đối tác, 16/10/2026): khối trạng thái + thu hộ
        + phiếu của chỉ định đang mở ở phòng — cùng dữ liệu, cùng chữ với bàn
        `/doi-tac`. Chỉ việc của bàn đối tác (`LA_VIEC_DOI_TAC_SQL`) hoặc đối
        tác làm trọn; chỉ định khác → cùng một câu "không tìm thấy"."""
        await self._doi_quyen_doi_tac(identity, "Bạn không có quyền “Đối tác”.")
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        row = await self._pool.fetchrow(
            _VIEC_SQL.format(
                where="o.id = $2::uuid AND o.exec_status <> 'cancelled' AND ("
                + LA_VIEC_DOI_TAC_SQL
                + " OR "
                + DOI_TAC_LAM_TRON_SQL
                + ")"
            ),
            identity.clinic_id,
            oid,
        )
        if row is None:
            raise SafetyGateError("Không tìm thấy việc này trong danh sách của bạn.")
        ds, xem_tep = await self._dung_viec(identity, [row])
        return {**ds[0], "xem_tep": xem_tep}

    async def viec_doi_tac(
        self, *, identity: StaffIdentity, ngay: Any = None
    ) -> dict[str, Any]:
        """Việc trên bàn đối tác, gom theo khách.

        Hai loại xét nghiệm (Tuyền 16/09/2026: *"cả 2, tuỳ loại xét nghiệm"*):
          * ĐỐI TÁC LÀM TRỌN (tự lấy mẫu `service_price.doi_tac_lay_mau`, hoặc
            bước làm bên ngoài không phòng nội bộ nào làm) — hiện từ lúc khách
            chốt làm, "Chờ làm" tới khi bấm "Nhận mẫu".
          * ĐIỀU DƯỠNG LẤY — chỉ hiện SAU khi điều dưỡng bấm xong ở phòng Lấy
            mẫu; trước đó ống máu còn chưa có, đối tác chẳng có gì để nhận.

        NHẬN QUA SỰ KIỆN (24/09/2026): bàn chỉ hiện chỉ định ĐÃ NHẬN
        (`doi_tac_nhan_viec`, ghi bởi bên nhận cùng tên).

        MẪU GỬI ĐỐI TÁC (Tuyền 29/09/2026): dịch vụ thu hộ đối tác làm ở phòng
        CỦA phòng khám (Giải phẫu bệnh, Sinh thiết + GPB ở phòng Thủ thuật) —
        phòng bấm Xong thì lên bàn (lý do MAU_GUI_DOI_TAC), cờ `mau_gui_doi_tac`.

        CHỌN NGÀY (Tuyền 29/09/2026 — "cần một chỗ up lên và xem lại được lịch
        sử các lần up"): `ngay` (YYYY-MM-DD; rác/None = hôm nay).
          * HÔM NAY: việc còn chờ trong 60 ngày + mọi việc CÓ HOẠT ĐỘNG hôm nay.
          * NGÀY CŨ: mọi việc có hoạt động ngày ấy — chỉ định, lấy mẫu, nhận
            mẫu, gửi kết quả, hay có tệp tải lên ngày ấy. Việc đã gửi tệp hôm
            qua vẫn tìm lại được để gửi bổ sung.
        """
        await self._doi_quyen_doi_tac(identity, "Màn này chỉ dành cho đối tác.")
        hom_nay = hom_nay_vn()
        ngay_xem = doc_ngay_xem(ngay) or hom_nay
        la_hom_nay = ngay_xem == hom_nay
        rows = await self._pool.fetch(
            _VIEC_SQL.format(
                where="""
                -- Bàn đọc ĐÚNG bảng nhận việc: bước làm bên ngoài lẫn mẫu gửi
                -- đối tác (phòng của phòng khám) đều đã có dòng ở đây.
                nv.service_order_id IS NOT NULL
               AND o.exec_status IN ('authorized', 'assigned', 'in_progress',
                                     'performed')
               AND (
                    -- Hôm nay: việc CÒN CHỜ (chưa trả kết quả) trong 60 ngày.
                    ($3::boolean AND o.ket_qua_luc IS NULL
                         AND o.created_at > now() - interval '60 days')
                    -- Mọi ngày: việc có hoạt động đúng ngày đang xem.
                 OR (o.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $2::date
                 OR (o.finished_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $2::date
                 OR (o.ket_qua_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $2::date
                 OR (o.doi_tac_cho_tai_lieu_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                    = $2::date
                 OR EXISTS (
                        SELECT 1 FROM tep_ket_qua t
                         WHERE t.clinic_id = o.clinic_id
                           AND t.service_order_id = o.id
                           AND (t.tai_len_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                               = $2::date))
               -- Cơ sở ($4): nhân viên nội bộ chỉ thấy việc của cơ sở đang
               -- đứng; tài khoản đối tác ngoài nhận mẫu mọi cơ sở → $4 NULL.
               AND coalesce(v.location_id, ap.location_id, $4::uuid)
                   IS NOT DISTINCT FROM
                   coalesce($4::uuid, v.location_id, ap.location_id)
             -- Việc CHƯA gửi trước, mới nhất trước: trần 300 dòng không bao giờ
             -- được cắt mất một chỉ định vừa gửi sang chỉ vì còn tồn việc cũ.
             ORDER BY (o.ket_qua_luc IS NOT NULL
                       OR o.doi_tac_cho_tai_lieu_luc IS NOT NULL),
                      o.created_at DESC, o.id
             LIMIT 300"""
            ),
            identity.clinic_id,
            ngay_xem,
            la_hom_nay,
            None
            if identity.co_vai([ClinicRole.PARTNER])
            else (identity.location_id or None),
        )
        canh_bao_neu_day("doi_tac.viec", len(rows), 300, clinic_id=identity.clinic_id)
        ds_viec, xem_tep = await self._dung_viec(identity, list(rows))
        theo_id = {v["chi_dinh_id"]: v for v in ds_viec}
        khach: dict[str, dict[str, Any]] = {}
        for r in rows:
            k = khach.setdefault(
                r["clinic_patient_id"],
                {
                    "clinic_patient_id": r["clinic_patient_id"],
                    "ten_khach": r["ten_khach"],
                    "ma_khach": r["ma_khach"],
                    "cho_tu": None,
                    "viec": [],
                },
            )
            luc = _iso(r["created_at"])
            if luc and (k["cho_tu"] is None or luc < k["cho_tu"]):
                k["cho_tu"] = luc
            k["viec"].append(theo_id[r["chi_dinh_id"]])
        # Việc CÒN DỞ = chưa nhận mẫu, chưa có kết quả (nhận mẫu là xong).
        con_viec = sum(
            1
            for r in rows
            if r["ket_qua_luc"] is None and r["doi_tac_cho_tai_lieu_luc"] is None
        )
        # Người đến trước lên trước — truy vấn đã lấy mới nhất trước cho trần.
        ds = sorted(khach.values(), key=lambda k: k["cho_tu"] or "")
        for k in ds:
            k["viec"].sort(key=lambda v: v["chi_dinh_luc"] or "")
        return {
            "khach": ds,
            "so_viec": con_viec,
            "ngay": ngay_xem.isoformat(),
            "hom_nay": la_hom_nay,
            # Người xem MỞ được tệp (xem/tải/in) không — máy chủ quyết, màn
            # chỉ ẩn/hiện nút. Vai PARTNER bên ngoài: False (chỉ gửi lên).
            "xem_tep": xem_tep,
        }

    async def doi_tac_cho_tai_lieu(
        self, *, order_id: str, identity: StaffIdentity, ghi_chu: str | None = None
    ) -> dict[str, Any]:
        """ "Nhận mẫu" / "Đã nhận mẫu" — ĐIỂM XONG của việc đối tác, MỘT lệnh cho
        bàn `/doi-tac` lẫn Phòng đối tác (Tuyền 29/09 + 16/10/2026).

        Tuyền 29/09/2026: *"khi NHẬN MẪU là coi như XONG VIỆC … Phải xong để bác
        sĩ, điều dưỡng, TKYK cùng thao tác cho khách còn về"*. Trong MỘT giao dịch:
          * việc ĐỐI TÁC LÀM TRỌN chưa làm xong: Phòng đối tác đã Bắt đầu (lần làm
            đang chạy) → đóng lần làm ấy đúng như [Xong] của mọi phòng
            (`service.completed`, khách rời hàng phòng); chưa ai Bắt đầu (bấm ở
            bàn `/doi-tac`) → ghi "đã làm" như lệnh lấy mẫu sẵn có
            (`partner.sample_collected`). Phòng đối tác thay nút "Lấy mẫu";
          * ghi mốc nhận mẫu (cột cũ `doi_tac_cho_tai_lieu_luc`) — một lần, bấm
            lại không đổi mốc đầu (ghi chú vẫn lưu);
          * PHÁT `partner.sample_received`.
        Khách KHÔNG bị giữ lượt — việc đối tác không giữ lượt ở mọi bước (chốt
        28/09: nút đối tác chỉ ghi sự kiện). Mở theo ngày: lượt đã đóng vẫn bấm
        được — chỉ khoá dòng lượt + chỉ định, không xét trạng thái lượt.
        Hoàn tác: `huy_nhan_mau`.
        """
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await conn.fetchval(
                "SELECT o.visit_id::text FROM service_order o"
                "  LEFT JOIN node_definition n"
                "    ON n.clinic_id = o.clinic_id AND n.code = o.node_code"
                " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid AND ("
                + LA_VIEC_DOI_TAC_SQL
                + " OR "
                + DOI_TAC_LAM_TRON_SQL
                + ")",
                cid,
                oid,
            )
            if vid is None:
                raise SafetyGateError(
                    "Không tìm thấy việc này trong danh sách của bạn."
                )
            # Khoá lượt TRƯỚC chỉ định (cùng thứ tự mọi lệnh khác).
            trang_thai_luot = await conn.fetchval(
                "SELECT status FROM visit WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid FOR UPDATE",
                cid,
                vid,
            )
            o = await conn.fetchrow(
                f"""
                SELECT o.exec_status, o.doi_tac_cho_tai_lieu_luc, o.ket_qua_luc,
                       {DOI_TAC_LAM_TRON_SQL} AS doi_tac_lam
                  FROM service_order o
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                   FOR UPDATE OF o
                """,
                cid,
                oid,
            )
            assert o is not None
            if o["exec_status"] in ("cancelled", "not_performed"):
                raise LuotKhamConflictError(
                    "ORDER_NOT_OPEN", "Chỉ định này đã huỷ / không làm."
                )
            # Ghi chú đối tác (24/09/2026) — lưu cả khi bấm lại để bổ sung.
            await _ghi_chu_doi_tac(conn, cid, oid, "ghi_chu_tai_lieu", ghi_chu)
            if o["doi_tac_lam"] and o["exec_status"] in (
                "authorized",
                "assigned",
                "in_progress",
            ):
                await self._lam_xong_doi_tac(
                    conn,
                    identity,
                    vid=vid,
                    oid=oid,
                    trang_thai_luot=trang_thai_luot,
                    ghi_chu=ghi_chu,
                )
            if o["doi_tac_cho_tai_lieu_luc"] is not None:
                return {"ok": True, "already": True}
            await conn.execute(
                """
                UPDATE service_order
                   SET doi_tac_cho_tai_lieu_luc = now(),
                       doi_tac_cho_tai_lieu_boi = $3::uuid,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="partner.awaiting_documents",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
            await emit_event(
                conn,
                ten="partner.sample_received",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DoiTacDaNhanMau(visit_id=vid, service_order_id=oid),
                boi=nguoi(identity),
                correlation_id=vid,
            )
        return {"ok": True, "already": False}

    async def _lam_xong_doi_tac(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        vid: str,
        oid: str,
        trang_thai_luot: str | None,
        ghi_chu: str | None,
    ) -> None:
        """Việc đối tác làm trọn → "đã làm" (người gọi đã khoá lượt + chỉ định).

        Phòng đối tác đã Bắt đầu → đóng ĐÚNG lần làm đang chạy bằng lệnh Xong
        chung của phòng (`ServiceExecutionService._ghi_xong`): lần làm, hàng chờ,
        chỗ chờ khác của lượt mở lại, `service.completed`. Lần làm do bàn khám
        mở thì không đụng. Chưa ai Bắt đầu → `_ghi_da_lay_mau` (đường cũ)."""
        from clinicai.services.service_execution_service import (
            NOI_BAN_KHAM,
            ServiceExecutionService,
        )

        lan = await conn.fetchrow(
            "SELECT id::text, attempt_no, noi_lam FROM service_execution_attempt"
            " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
            "   AND status = 'IN_PROGRESS' FOR UPDATE",
            identity.clinic_id,
            oid,
        )
        if lan is not None and lan["noi_lam"] != NOI_BAN_KHAM:
            ghi = (ghi_chu or "").strip() or None
            await ServiceExecutionService(self._pool)._ghi_xong(
                conn, identity.clinic_id, vid, oid, lan, identity, ghi
            )
            if trang_thai_luot in ("OPEN", "IN_PROGRESS"):
                await cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            return
        if lan is not None:
            raise LuotKhamConflictError(
                "DANG_LAM_BAN_KHAM",
                "Bác sĩ đang làm dịch vụ này ở bàn khám — bàn khám bấm Xong.",
            )
        await self._ghi_da_lay_mau(
            conn, identity, vid=vid, oid=oid, trang_thai_luot=trang_thai_luot
        )

    async def huy_nhan_mau(
        self,
        *,
        order_id: str,
        identity: StaffIdentity,
        ly_do: Any = None,
        xac_nhan: bool = False,
        mo_lai_phong: bool = False,
    ) -> dict[str, Any]:
        """HOÀN TÁC "Nhận mẫu" (luật 01/10: không thao tác nào khoá cứng): gỡ mốc
        nhận mẫu, việc về "Chờ làm". Đã trả kết quả → hoàn tác Trả kết quả trước.

        `mo_lai_phong` (nút Hoàn tác ở Phòng đối tác): "Đã nhận mẫu" ở phòng cũng
        đã ĐÓNG lần làm — mở lại nó bằng ĐÚNG lệnh hoàn tác "Xong" của mọi phòng
        (`HoanTacService.hoan_tac_xong_dich_vu`: quyền, hỏi xác nhận, vòng đọc,
        hàng chờ) TRƯỚC khi gỡ mốc; lệnh ấy hỏi lại / từ chối thì mốc giữ nguyên.
        Bàn `/doi-tac` không gửi cờ này (tài khoản đối tác không mở lại phòng)."""
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        ly = ly_do.strip()[:2000] if isinstance(ly_do, str) else None
        if mo_lai_phong:
            dong_o_phong = await self._pool.fetchval(
                "SELECT o.execution_status = 'COMPLETED'"
                "   AND o.ket_qua_luc IS NULL AND EXISTS ("
                "       SELECT 1 FROM service_execution_attempt a"
                "        WHERE a.clinic_id = o.clinic_id"
                "          AND a.service_order_id = o.id AND a.status = 'COMPLETED'"
                "          AND a.noi_lam IS DISTINCT FROM 'BAN_KHAM')"
                "  FROM service_order o"
                " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid",
                cid,
                oid,
            )
            if dong_o_phong:
                from clinicai.services.hoan_tac_service import HoanTacService

                await HoanTacService(self._pool).hoan_tac_xong_dich_vu(
                    order_id=oid, identity=identity, ly_do=ly_do, xac_nhan=xac_nhan
                )
        async with self._pool.acquire() as conn, conn.transaction():
            o = await conn.fetchrow(
                "SELECT o.visit_id::text AS visit_id, o.doi_tac_cho_tai_lieu_luc,"
                "       o.ket_qua_luc FROM service_order o"
                "  LEFT JOIN node_definition n"
                "    ON n.clinic_id = o.clinic_id AND n.code = o.node_code"
                " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid AND ("
                + LA_VIEC_DOI_TAC_SQL
                + " OR "
                + DOI_TAC_LAM_TRON_SQL
                + ") FOR UPDATE OF o",
                cid,
                oid,
            )
            if o is None:
                raise SafetyGateError(
                    "Không tìm thấy việc này trong danh sách của bạn."
                )
            if o["doi_tac_cho_tai_lieu_luc"] is None:
                return {"ok": True, "already": True}
            if o["ket_qua_luc"] is not None:
                raise LuotKhamConflictError(
                    "DA_TRA_KET_QUA",
                    "Việc này đã trả kết quả — hoàn tác “Trả kết quả” trước.",
                )
            await conn.execute(
                "UPDATE service_order SET doi_tac_cho_tai_lieu_luc = NULL,"
                "       doi_tac_cho_tai_lieu_boi = NULL,"
                "       version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                oid,
            )
            await emit_event(
                conn,
                ten="partner.sample_receipt_undone",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DoiTacHoanTacNhanMau(
                    visit_id=o["visit_id"], service_order_id=oid, co_ly_do=bool(ly)
                ),
                boi=nguoi(identity),
                correlation_id=o["visit_id"],
            )
        return {"ok": True, "already": False}

    async def tra_ket_qua(
        self, *, order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """[Trả kết quả] (Tuyền 16/10/2026): đối tác tải tệp lên và/hoặc điền
        phiếu theo mẫu, rồi bấm nút này → "Có kết quả" ở MỌI màn (cột
        `ket_qua_luc` — mọi màn đã đọc nó). Tải tệp KHÔNG tự đặt mốc nữa với việc
        đối tác (tải dở hai tệp chưa phải trả kết quả).

        Phải có nội dung: ít nhất một tệp còn hiệu lực, hoặc phiếu kết quả đã Hoàn
        tất, hoặc kết quả ghi chữ — không thì báo rõ, không ghi. Chưa bấm Nhận
        mẫu → nhận mẫu trước (cùng lệnh sẵn có): có kết quả thì mẫu đã có.
        Bấm lại = đã trả (không đổi mốc). Hoàn tác: `huy_tra_ket_qua`."""
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        dau = await self._pool.fetchrow(
            "SELECT o.doi_tac_cho_tai_lieu_luc, o.ket_qua_luc,"
            "       (EXISTS (SELECT 1 FROM v_tep_ket_qua_hieu_luc t"
            "         WHERE t.clinic_id = o.clinic_id AND t.service_order_id = o.id"
            "           AND coalesce(t.xac_nhan_trang_thai, 'HOP_LE')"
            "               IN ('CHO_XAC_NHAN', 'HOP_LE'))"
            "        OR EXISTS (SELECT 1 FROM form_instance f"
            "         WHERE f.clinic_id = o.clinic_id AND f.service_order_id = o.id"
            "           AND f.trang_thai = 'READY')"
            "        OR nullif(btrim(coalesce(o.result_note, '')), '') IS NOT NULL)"
            "         AS co_noi_dung"
            "  FROM service_order o"
            "  LEFT JOIN node_definition n"
            "    ON n.clinic_id = o.clinic_id AND n.code = o.node_code"
            " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid"
            "   AND o.exec_status NOT IN ('cancelled', 'not_performed') AND ("
            + LA_VIEC_DOI_TAC_SQL
            + " OR "
            + DOI_TAC_LAM_TRON_SQL
            + ")",
            cid,
            oid,
        )
        if dau is None:
            raise SafetyGateError("Không tìm thấy việc này trong danh sách của bạn.")
        if dau["ket_qua_luc"] is not None:
            return {"ok": True, "already": True}
        if not dau["co_noi_dung"]:
            raise LuotKhamConflictError(
                "CHUA_CO_KET_QUA",
                "Chưa có kết quả để trả — tải tệp kết quả lên hoặc điền và Hoàn tất"
                " phiếu kết quả trước.",
            )
        if dau["doi_tac_cho_tai_lieu_luc"] is None:
            await self.doi_tac_cho_tai_lieu(order_id=oid, identity=identity)
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await conn.fetchval(
                "UPDATE service_order SET ket_qua_luc = now(),"
                "       version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                "   AND ket_qua_luc IS NULL"
                " RETURNING visit_id::text",
                cid,
                oid,
            )
            if vid is None:
                return {"ok": True, "already": True}
            await emit_event(
                conn,
                ten="partner.result_returned",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DoiTacTraKetQua(visit_id=vid, service_order_id=oid),
                boi=nguoi(identity),
                correlation_id=vid,
            )
        return {"ok": True, "already": False}

    async def huy_tra_ket_qua(
        self, *, order_id: str, identity: StaffIdentity, ly_do: Any = None
    ) -> dict[str, Any]:
        """HOÀN TÁC [Trả kết quả]: gỡ mốc "Có kết quả" → "Đã nhận mẫu · chờ kết
        quả". Tệp + phiếu GIỮ NGUYÊN (xoá tệp / sửa phiếu là lệnh riêng)."""
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        ly = ly_do.strip()[:2000] if isinstance(ly_do, str) else None
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await conn.fetchval(
                "SELECT o.visit_id::text FROM service_order o"
                "  LEFT JOIN node_definition n"
                "    ON n.clinic_id = o.clinic_id AND n.code = o.node_code"
                " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid"
                "   AND o.ket_qua_luc IS NOT NULL AND ("
                + LA_VIEC_DOI_TAC_SQL
                + " OR "
                + DOI_TAC_LAM_TRON_SQL
                + ") FOR UPDATE OF o",
                cid,
                oid,
            )
            if vid is not None:
                await conn.execute(
                    "UPDATE service_order SET ket_qua_luc = NULL,"
                    "       version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    oid,
                )
            if vid is None:
                return {"ok": True, "already": True}
            await emit_event(
                conn,
                ten="partner.result_return_undone",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DoiTacHoanTacTraKetQua(
                    visit_id=vid, service_order_id=oid, co_ly_do=bool(ly)
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
        return {"ok": True, "already": False}

    async def doi_tac_da_lay_mau(
        self, *, order_id: str, identity: StaffIdentity, ghi_chu: str | None = None
    ) -> dict[str, Any]:
        """Bấm "Đã lấy mẫu" cho việc đối tác làm trọn — LỆNH CŨ, giữ cho tương
        thích (màn đã bỏ nút từ 16/10/2026: "Nhận mẫu" làm luôn việc này).

        LỆNH IDEMPOTENT, MỞ THEO NGÀY (Tuyền 29/09/2026): bấm được cả ở ngày cũ,
        cả khi lượt đã Hoàn tất / khách đã về — lấy mẫu là sự thật ngoài đời,
        không phải việc bị khoá theo lượt. Vì thế KHÔNG gọi `khoa_luot` (nó
        chặn lượt FINALIZED / INCOMPLETE); chỉ khoá dòng lượt + dòng chỉ định
        để hai người bấm cùng lúc không ghi đôi.
          * Lần đầu: ghi nhận (performed, giờ lấy mẫu, người lấy) + phát
            `partner.sample_collected`.
          * Lần sau: KHÔNG ghi nhận lại, không đổi giờ, không bỏ ghi nhận — chỉ
            GHI LẠI vào nhật ký (`partner.sample_noted_again`) kèm ghi chú.
        """
        await self._doi_quyen_doi_tac(identity, "Bạn không có quyền “Đối tác”.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await conn.fetchval(
                f"""
                SELECT o.visit_id::text
                  FROM service_order o
                  JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                   AND n.lam_ben_ngoai
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                   AND {DOI_TAC_LAM_TRON_SQL}
                """,
                cid,
                oid,
            )
            if vid is None:
                # Một câu cho cả "không có" lẫn "không phải việc đối tác tự lấy".
                raise SafetyGateError(
                    "Không tìm thấy việc này trong danh sách của bạn."
                )
            # Khoá lượt TRƯỚC chỉ định (cùng thứ tự mọi lệnh khác — không kẹt
            # chéo), nhưng KHÔNG xét trạng thái lượt.
            trang_thai_luot = await conn.fetchval(
                "SELECT status FROM visit WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid FOR UPDATE",
                cid,
                vid,
            )
            await _ghi_chu_doi_tac(conn, cid, oid, "ghi_chu_lay_mau", ghi_chu)
            trang_thai = await conn.fetchval(
                "SELECT exec_status FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
                cid,
                oid,
            )
            if trang_thai == "performed":
                await record_event(
                    conn,
                    event_type="partner.sample_noted_again",
                    aggregate_type="visit",
                    aggregate_id=vid,
                    identity=identity,
                    origin=ORIGIN,
                    payload={
                        "visit_id": vid,
                        "order_id": oid,
                        # Chữ ghi chú nằm ở doi_tac_nhan_viec; nhật ký chỉ
                        # mang cờ (payload không chở chữ tự do).
                        "co_ghi_chu": bool((ghi_chu or "").strip()),
                    },
                )
                return {"ok": True, "already": True, "order_id": oid}
            if trang_thai not in ("authorized", "assigned", "in_progress"):
                raise LuotKhamConflictError(
                    "ORDER_NOT_OPEN", "Việc này không còn chờ lấy mẫu."
                )
            await self._lam_xong_doi_tac(
                conn,
                identity,
                vid=vid,
                oid=oid,
                trang_thai_luot=trang_thai_luot,
                ghi_chu=ghi_chu,
            )
        return {"ok": True, "already": False, "order_id": oid}

    async def _ghi_da_lay_mau(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        vid: str,
        oid: str,
        trang_thai_luot: str | None,
    ) -> None:
        """Ghi "đã làm" cho việc đối tác làm trọn CHƯA có lần làm ở phòng (người
        gọi đã khoá lượt + chỉ định). Phòng của chỉ định giữ nguyên nếu đã xếp
        (Phòng đối tác đã Nhận); chưa xếp thì phòng đối tác của đúng cơ sở."""
        cid = identity.clinic_id
        await conn.execute(
            """
            UPDATE service_order
               SET exec_status = 'performed', performed_by = $3::uuid,
                   room_id = coalesce(room_id, (
                       SELECT r.id FROM clinic_room r
                        WHERE r.clinic_id = $1::uuid AND r.la_doi_tac
                          AND r.is_active
                          AND phong_lam_duoc(r.clinic_id, r.id,
                                             service_order.node_code,
                                             service_order.service_code)
                        -- Phòng đối tác của ĐÚNG cơ sở lượt trước (hai
                        -- cơ sở, 08/10/2026); cơ sở chưa có thì dùng chung.
                        ORDER BY (r.location_id IS NOT DISTINCT FROM
                                  co_so_cua_luot(service_order.visit_id)) DESC,
                                 r.sort
                        LIMIT 1)),
                   assigned_by = coalesce(assigned_by, $3::uuid),
                   assigned_at = coalesce(assigned_at, now()),
                   started_at = coalesce(started_at, now()), finished_at = now(),
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND id = $2::uuid
            """,
            cid,
            oid,
            identity.staff_id,
        )
        await conn.execute(
            """
            UPDATE queue_entry
               SET status = 'done', done_at = now(), version = version + 1,
                   updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND ref_id = $3::uuid AND reason = 'SERVICE'
               AND status NOT IN ('done', 'left', 'cancelled')
            """,
            cid,
            vid,
            oid,
        )
        # Lượt đã đóng / khách đã về: không mở lại hàng chờ, không dời con
        # trỏ "khách đang ở đâu" — chỉ ghi sự thật lấy mẫu.
        if trang_thai_luot in ("OPEN", "IN_PROGRESS"):
            await mo_cho_bi_chan(conn, cid, vid)
            await cap_nhat_vi_tri(conn, identity.clinic_id, vid)
        await emit_event(
            conn,
            ten="partner.sample_collected",
            clinic_id=cid,
            aggregate_id=oid,
            so_ke_tiep=True,
            payload=DoiTacDaLayMau(visit_id=vid, service_order_id=oid),
            boi=nguoi(identity),
            correlation_id=vid,
        )
        await record_event(
            conn,
            event_type="service.performed",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={"visit_id": vid, "order_id": oid, "doi_tac_lay_mau": True},
        )

    # ------------------------------------------------------------------
    # ĐỐI TÁC TỰ THU (Tuyền chốt 27/09/2026, Q1): "khách trả trực tiếp cho đối
    # tác, màn đối tác cũng phải có ghi nhận thanh toán thực hiện". Sổ của khối
    # Đối tác — KHÔNG phải tiền phòng khám (không vào két, không vào phiếu thu).

    async def ghi_nhan_da_thu(
        self,
        *,
        order_id: str,
        identity: StaffIdentity,
        so_tien: Any,
        hinh_thuc: Any,
        ghi_chu: str | None = None,
    ) -> dict[str, Any]:
        """Đối tác bấm "Đã thu tiền khách" cho một việc đã nhận.

        Một việc — một ghi nhận còn hiệu lực (unique ở Postgres). Bấm lại cùng số
        tiền + hình thức = trả lại bản cũ (chạy lại được); khác số = phải huỷ bản
        cũ (có lý do) rồi ghi lại.
        """
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        # Ô số tiền TUỲ CHỌN (Tuyền 16/10/2026): để trống = không ghi gì, không
        # lỗi — thu hộ không chặn việc nào khác. 0 vẫn là một ghi nhận. Rác thì
        # báo rõ (không đoán số).
        if so_tien is None or (isinstance(so_tien, str) and not so_tien.strip()):
            return {"ok": True, "bo_qua": True, "id": None}
        tien = doc_so_tien(so_tien)
        if tien is None:
            raise ValidationError("Số tiền không hợp lệ (số nguyên ≥ 0, đơn vị đồng).")
        ht = doc_hinh_thuc(hinh_thuc)
        if ht is None:
            raise ValidationError("Hình thức phải là Tiền mặt hoặc Chuyển khoản.")
        ghi = (ghi_chu or "").strip() or None
        if ghi is not None and len(ghi) > 2000:
            raise LuotKhamConflictError(
                "NOTE_TOO_LONG", "Ghi chú quá dài (tối đa 2.000 ký tự)."
            )
        async with self._pool.acquire() as conn, conn.transaction():
            o = await conn.fetchrow(
                """
                SELECT o.visit_id::text AS visit_id
                  FROM service_order o
                  JOIN doi_tac_nhan_viec nv
                    ON nv.clinic_id = o.clinic_id AND nv.service_order_id = o.id
                  JOIN service_price sp
                    ON sp.clinic_id = o.clinic_id AND sp.service_code = o.service_code
                   AND sp.active AND sp."group" = 'dich_vu'
                   AND sp.billing_owner = 'EXTERNAL_PARTNER'
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                   AND o.exec_status <> 'cancelled'
                 LIMIT 1
                 FOR UPDATE OF o
                """,
                cid,
                oid,
            )
            if o is None:
                # Một câu cho "không có" lẫn "không phải việc khách trả đối tác".
                raise SafetyGateError(
                    "Không tìm thấy việc này trong danh sách của bạn."
                )
            cu = await conn.fetchrow(
                "SELECT id::text AS id, so_tien, hinh_thuc FROM doi_tac_thanh_toan"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND huy_luc IS NULL",
                cid,
                oid,
            )
            if cu is not None:
                if int(cu["so_tien"]) == tien and cu["hinh_thuc"] == ht:
                    return {"ok": True, "already": True, "id": cu["id"]}
                raise LuotKhamConflictError(
                    "PARTNER_PAYMENT_EXISTS",
                    "Việc này đã ghi nhận đã thu — huỷ ghi nhận cũ (kèm lý do)"
                    " rồi ghi lại.",
                )
            moi = await conn.fetchval(
                """
                INSERT INTO doi_tac_thanh_toan
                    (clinic_id, service_order_id, so_tien, hinh_thuc, ghi_chu,
                     ghi_boi)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)
                RETURNING id::text
                """,
                cid,
                oid,
                tien,
                ht,
                ghi,
                identity.staff_id,
            )
            await emit_event(
                conn,
                ten="partner.payment_recorded",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DoiTacDaThuTien(
                    visit_id=o["visit_id"],
                    service_order_id=oid,
                    so_tien=tien,
                    hinh_thuc=ht,
                ),
                boi=nguoi(identity),
                correlation_id=o["visit_id"],
            )
        return {"ok": True, "already": False, "id": moi}

    async def huy_da_thu(
        self, *, order_id: str, identity: StaffIdentity, ly_do: Any
    ) -> dict[str, Any]:
        """Huỷ ghi nhận "đã thu" đang hiệu lực (ghi nhầm / sửa số) — bắt buộc lý
        do. Không xoá: dòng cũ giữ lại kèm ai huỷ, lúc nào, vì sao."""
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        ly = ly_do.strip() if isinstance(ly_do, str) else ""
        if not 3 <= len(ly) <= 2000:
            raise ValidationError("Ghi lý do huỷ (3–2.000 ký tự).")
        async with self._pool.acquire() as conn, conn.transaction():
            cu = await conn.fetchrow(
                """
                SELECT t.id::text AS id, t.so_tien, o.visit_id::text AS visit_id
                  FROM doi_tac_thanh_toan t
                  JOIN service_order o
                    ON o.clinic_id = t.clinic_id AND o.id = t.service_order_id
                 WHERE t.clinic_id = $1::uuid AND t.service_order_id = $2::uuid
                   AND t.huy_luc IS NULL
                   FOR UPDATE OF t
                """,
                cid,
                oid,
            )
            if cu is None:
                return {"ok": True, "already": True}
            await conn.execute(
                "UPDATE doi_tac_thanh_toan SET huy_luc = now(), huy_boi = $3::uuid,"
                " ly_do_huy = $4 WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                cu["id"],
                identity.staff_id,
                ly,
            )
            await emit_event(
                conn,
                ten="partner.payment_voided",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DoiTacHuyThuTien(
                    visit_id=cu["visit_id"],
                    service_order_id=oid,
                    so_tien=int(cu["so_tien"]),
                ),
                boi=nguoi(identity),
                correlation_id=cu["visit_id"],
            )
        return {"ok": True, "already": False}
