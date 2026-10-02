"""Bảy phiếu khám — định nghĩa theo phiên bản, cổng kiểm một lần lưu, dữ liệu đọc kèm.

GÓI NÀY KHÔNG TỰ QUYẾT BA THỨ, và cả ba được CẮM TỪ NGOÀI VÀO:

1. **Phiếu gắn vào đâu.** Bảy phiếu khám (5 chuyên khoa + Thủ thuật + Sàn chậu)
   gắn vào consultation/visit. Chỉ phiếu KẾT QUẢ DỊCH VỤ mới gắn
   `service_order`. `form_instance` hiện chỉ có `service_order_id`, nên chỗ
   lưu một lần điền phiếu khám CHƯA CÓ — INTEGRATION_BLOCKER, không vá bằng
   cách giả khám thành một chỉ định. Gói này vì thế không mở/ghi
   `form_instance` nào; nó cung cấp cổng `kiem_luu` mà chỗ lưu tương lai gọi.
2. **Hồ sơ đã chốt chưa.** Clinical shell truyền `editable` /
   `finalized_locked` / `amendment_mode` (`phieu_kham.che_do`). Gói này không
   đọc trạng thái lượt, không biết mốc chốt ở đâu.
3. **Ai được làm.** `KiemQuyen` do hệ phân quyền của CORE cung cấp. Gói này
   không thêm capability, không mượn capability của module khác.

Còn lại là việc của gói: khung theo ĐÚNG phiên bản, kiểm dữ liệu theo khoá ổn
định (không so tên), phần mang sang, kết quả CLS theo `service_order_id`.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone
from typing import Any, Literal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.events.catalogue import DonThuocDaLuu
from clinicai.events.emit import emit_event, nguoi_lam_thay
from clinicai.permissions.ca_truc import kiem_dung_ca
from clinicai.permissions.can import can, doi_quyen
from clinicai.permissions.y_khoa import QUYEN_IN_PHIEU
from clinicai.phieu_kham import anh_xa_danh_muc as ax
from clinicai.phieu_kham.che_do import doi_ghi_duoc
from clinicai.phieu_kham.hanh_trinh import doc_hanh_trinh
from clinicai.phieu_kham.ket_qua_chi_dinh import (
    doc_ket_qua_theo_chi_dinh,
    doc_mau_du_phong,
    doc_tep_chua_gan,
)
from clinicai.phieu_kham.khung import (
    FORM_IDS,
    cac_o,
    dinh_nghia,
    kiem_du_lieu,
    la_phieu_kham,
    tham_chieu_nguon,
)
from clinicai.phieu_kham.mang_sang import doc_dau_phieu
from clinicai.services import hen_tai_kham_service as htk
from clinicai.services.bac_si_phu_trach import bac_si_cua_phien
from clinicai.services.cskh_service import clinic_today
from clinicai.services.danh_muc_dich_vu_service import (
    ly_do_khoa_chi_dinh,
    nhom_hang_hien,
)
from clinicai.services.danh_muc_dich_vu_service import (
    thu_tu_nhom_hang as _thu_tu_nhom_hang,
)
from clinicai.services.thai_ky_service import dong_bo_tu_phieu, thai_ky_cua_luot

logger = structlog.get_logger()

#: Việc cần hỏi quyền. Đây là NHÃN của lời hỏi gửi sang hệ phân quyền, không
#: phải capability — ánh xạ sang capability nào là việc của CORE.
HanhDong = Literal["doc_phieu", "ghi_phieu", "doc_ket_qua_cls", "xem_lich_su"]

#: Hệ phân quyền của CORE: không có quyền thì RAISE (SafetyGateError).
KiemQuyen = Callable[[asyncpg.Connection, StaffIdentity, HanhDong], Awaitable[None]]


async def chua_noi_quyen(
    conn: asyncpg.Connection, identity: StaffIdentity, hanh_dong: HanhDong
) -> None:
    """Mặc định khi CHƯA nối hệ phân quyền: chặn tất. Đóng khi nghi ngờ."""
    raise SafetyGateError(f"Phiếu khám chưa được nối với hệ phân quyền ({hanh_dong}).")


#: Ghi phiếu khám = ghi bệnh án (bác sĩ, thư ký y khoa, BS siêu âm).
QUYEN_GHI = "clinical.record.write"
#: Bác sĩ tư vấn ghi vào CHÍNH phiếu khám của lượt (Tuyền chốt 24/09: "tư vấn
#: ghi vào chính bệnh án") — người chỉ có khối Tư vấn cũng ghi được.
QUYEN_GHI_THEM: frozenset[str] = frozenset({"clinical.intake.perform"})
#: Đọc: ai đang khám / ghi bệnh án / điền kết quả của lượt.
QUYEN_DOC = (
    "clinical.record.write",
    "clinical.consult.perform",
    "clinical.intake.perform",
    "result.form.fill",
)
#: Đọc ĐỂ IN (27/09/2026, Tuyền "in ở mọi khâu"): thêm các khâu quầy
#: (`QUYEN_IN_PHIEU`). Chỉ phiếu / đầu phiếu / kết quả / đơn — KHÔNG lịch sử sửa
#: (ai sửa ô nào lúc nào là chuyện chuyên môn), KHÔNG ghi.
QUYEN_DOC_DE_IN = (*QUYEN_DOC, *QUYEN_IN_PHIEU)

#: Không khoá (Tuyền chốt 23/09/2026): Hoàn tất chỉ là mốc giờ, phiếu sửa tiếp
#: được. Chế độ duy nhất shell dùng cho phiếu mới.
CHE_DO_MO = "editable"


async def kiem_quyen_core(
    conn: asyncpg.Connection, identity: StaffIdentity, hanh_dong: HanhDong
) -> None:
    """Hệ phân quyền của CORE cắm vào gói (IP-2) — hỏi capability, không hỏi vai."""
    if hanh_dong == "ghi_phieu":
        for quyen in QUYEN_GHI_THEM:
            if await can(conn, identity, quyen):
                return
        await doi_quyen(
            conn, identity, QUYEN_GHI, cau="Bạn không có quyền ghi phiếu khám."
        )
        return
    for quyen in QUYEN_DOC if hanh_dong == "xem_lich_su" else QUYEN_DOC_DE_IN:
        if await can(conn, identity, quyen):
            return
    raise SafetyGateError("Bạn không có quyền xem phiếu khám.")


#: Hai ô thai kỳ của phiếu Sản khoa v5 (mục B) — khoá ổn định của nguồn.
O_KINH_CUOI = "sk_lmp"
O_DU_KIEN_SINH = "sk_edd"
O_THAI_KY = (O_KINH_CUOI, O_DU_KIEN_SINH)


def _dict(v: Any) -> dict[str, Any]:
    v = json.loads(v) if isinstance(v, str) else v
    return dict(v) if isinstance(v, dict) else {}


def _gia(o: Any) -> Any:
    """`gia_tri` của một ô; trống ("" / [] / thiếu) → None để so "có đổi"."""
    v = o.get("gia_tri") if isinstance(o, dict) else None
    return None if v is None or v == "" or v == [] else v


def _trong(o: Any) -> bool:
    v = _gia(o)
    return v is None or (isinstance(v, str) and not v.strip())


def _khoa_ten(t: str) -> str:
    """Khoá so tên thuốc: bỏ hoa/thường và MỌI dấu cách ("Dunium/ Fetogard" =
    "Dunium/Fetogard")."""
    return "".join(t.split()).lower()


#: Nhóm hiển thị của dịch vụ danh mục phòng khám theo phòng làm (node).
_NHOM_THEO_NODE = {
    "DICHVU-SIEUAM": "Siêu âm",
    "DICHVU-THUTHUAT": "Thủ thuật",
    "DICHVU-LAYMAU-MAU": "Xét nghiệm",
    "DICHVU-LAYMAU-AMDAO": "Xét nghiệm",
    "DICHVU-LAYMAU-NUOCTIEU": "Xét nghiệm",
    "DICHVU-SANGLOC-COTUCUNG": "Sàng lọc cổ tử cung",
}


class PhieuKhamService:
    def __init__(self, pool: asyncpg.Pool, *, kiem_quyen: KiemQuyen) -> None:
        self._pool = pool
        self._kiem_quyen = kiem_quyen

    # ------------------------------------------------------------------
    async def khung_theo_ban(
        self, *, form_id: str, version: int | None, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Khung của MỘT phiên bản (hoặc bản đang dùng nếu `version` None).

        Phiếu đã bắt đầu điền thì ghim phiên bản của nó: xuất bản v2 thêm một
        ô thì phiếu v1 vẫn không có ô ấy.
        """
        if not la_phieu_kham(form_id):
            raise ValidationError(f"“{form_id}” không phải phiếu khám.")
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            dong = await conn.fetchrow(
                "SELECT form_id, version, ten, khung FROM form_definition"
                " WHERE clinic_id = $1::uuid AND form_id = $2"
                "   AND (($3::int IS NULL AND trang_thai = 'PUBLISHED')"
                "        OR version = $3::int)",
                identity.clinic_id,
                form_id,
                version,
            )
        if dong is None:
            ban = f" v{version}." if version is not None else " nào đang dùng."
            raise ValidationError(f"Phiếu “{form_id}” chưa có bản{ban}")
        return {
            "form_id": dong["form_id"],
            "version": dong["version"],
            "ten": dong["ten"],
            "khung": json.loads(dong["khung"]),
        }

    async def kiem_luu(
        self,
        *,
        form_id: str,
        version: int,
        du_lieu: dict[str, Any],
        che_do: object,
        identity: StaffIdentity,
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
        """Cổng một lần lưu — chỗ lưu phiếu khám (khi có) gọi TRƯỚC khi ghi.

        Thứ tự có chủ ý: chế độ trước (hồ sơ đã chốt thì không cần biết dữ liệu
        đúng hay sai), rồi quyền, rồi khung đúng phiên bản, rồi từng ô.
        """
        doi_ghi_duoc(che_do)
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "ghi_phieu")
        ban = await self.khung_theo_ban(
            form_id=form_id, version=version, identity=identity
        )
        return kiem_du_lieu(ban["khung"], du_lieu)

    # ------------------------------------------------------------------
    # CHỖ LƯU: phiếu của một LƯỢT (bảng `phieu_kham_luot`, migration
    # 20260924000008). Gỡ INTEGRATION_BLOCKER mà không giả khám thành chỉ định.
    async def doc_luot(
        self, *, visit_id: str, form_id: str | None, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Phiếu của lượt. Chưa có bản ghi thì dựng từ loại khám của lượt;
        loại khám không gắn phiếu nào thì trả danh sách để bác sĩ chọn."""
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            luot = await conn.fetchrow(
                "SELECT st.form_code FROM visit v"
                " LEFT JOIN service_type st ON st.id = v.service_type_id"
                " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
                cid,
                visit_id,
            )
            if luot is None:
                raise ValidationError("Không tìm thấy lượt khám.")
            dong = await conn.fetchrow(
                "SELECT form_id, version, du_lieu, revision, sua_luc"
                "  FROM phieu_kham_luot"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND ($3::text IS NULL OR form_id = $3)"
                " ORDER BY sua_luc DESC LIMIT 1",
                cid,
                visit_id,
                form_id,
            )
        chon = form_id or (dong["form_id"] if dong else None)
        if chon is None and luot["form_code"] in FORM_IDS:
            chon = luot["form_code"]
        if chon is None:
            return {
                "form_id": None,
                "chon_duoc": [
                    {"form_id": f, "ten": dinh_nghia(f)["ten"]} for f in FORM_IDS
                ],
            }
        ban = await self.khung_theo_ban(
            form_id=chon,
            version=int(dong["version"]) if dong else None,
            identity=identity,
        )
        du_lieu: Any = dong["du_lieu"] if dong else {}
        if isinstance(du_lieu, str):
            du_lieu = json.loads(du_lieu)
        du_lieu = await self._dien_nguoc_thai_ky(
            ban["khung"], du_lieu, clinic_id=cid, visit_id=visit_id
        )
        return {
            **ban,
            "du_lieu": du_lieu,
            "revision": int(dong["revision"]) if dong else 0,
            "sua_luc": dong["sua_luc"].isoformat() if dong else None,
            "che_do": CHE_DO_MO,
            "mac_dinh_theo_loai_kham": luot["form_code"] in FORM_IDS,
        }

    async def _dien_nguoc_thai_ky(
        self,
        khung: Any,
        du_lieu: dict[str, Any],
        *,
        clinic_id: str,
        visit_id: str,
    ) -> dict[str, Any]:
        """Phiếu có hai ô thai kỳ mà ô TRỐNG → điền từ thai kỳ bao trùm ngày
        khám (29/09/2026). Chỉ điền vào bản TRẢ VỀ, không ghi phiếu: thai kỳ là
        nguồn; màn coi đó là giá trị đã lưu nên không tự gửi lại."""
        o_khung = cac_o(khung) if isinstance(khung, list) else {}
        trong = [k for k in O_THAI_KY if k in o_khung and _trong(du_lieu.get(k))]
        if not trong:
            return du_lieu
        async with self._pool.acquire() as conn:
            tk = await thai_ky_cua_luot(conn, clinic_id, visit_id)
        if tk is None:
            return du_lieu
        ra = dict(du_lieu)
        if O_KINH_CUOI in trong and tk["lmp"] is not None:
            # Ô kinh cuối là CHỮ tự do → ngày kiểu Việt Nam.
            ra[O_KINH_CUOI] = {
                "gia_tri": tk["lmp"].strftime("%d/%m/%Y"),
                "nguon": "PATIENT_CONTEXT",
            }
        if O_DU_KIEN_SINH in trong and tk["edd"] is not None:
            ra[O_DU_KIEN_SINH] = {
                "gia_tri": tk["edd"].isoformat(),
                "nguon": "PATIENT_CONTEXT",
            }
        return ra

    async def luu_luot(
        self,
        *,
        visit_id: str,
        form_id: str,
        du_lieu: dict[str, Any] | None,
        expected_revision: int,
        identity: StaffIdentity,
        thay_doi: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Tự lưu một lần: qua cổng `kiem_luu` rồi ghi.

        Hai cách:
        * `thay_doi` (lát 2, 26/09/2026) — CHỈ các ô vừa đổi, gộp vào bản đang
          có dưới khoá dòng. Hai người (bác sĩ + thư ký, tư vấn + bác sĩ chính)
          sửa hai ô khác nhau đều được lưu; cùng một ô thì lần sau đè lần trước
          — lịch sử sửa (trigger) giữ đủ vết.
        * `du_lieu` (cũ) — cả gói, có chống đè bằng `revision`: người kia vừa
          lưu → 409, màn tải lại chứ không đè im lặng.
        """
        la_va = thay_doi is not None
        goi_vao = thay_doi if la_va else du_lieu
        if goi_vao is None:
            raise ValidationError("Thiếu dữ liệu phiếu.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            ban = await conn.fetchval(
                "SELECT version FROM phieu_kham_luot WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND form_id = $3",
                cid,
                visit_id,
                form_id,
            )
        if ban is None:
            ban = (
                await self.khung_theo_ban(
                    form_id=form_id, version=None, identity=identity
                )
            )["version"]
        sach, canh_bao = await self.kiem_luu(
            form_id=form_id,
            version=int(ban),
            du_lieu=goi_vao,
            che_do=CHE_DO_MO,
            identity=identity,
        )
        async with self._pool.acquire() as conn, conn.transaction():
            if not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM visit WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid)",
                cid,
                visit_id,
            ):
                raise ValidationError("Không tìm thấy lượt khám.")
            bac_si_id = await bac_si_cua_phien(
                conn,
                clinic_id=cid,
                visit_id=visit_id,
                nguoi_bam=identity.staff_id,
            )
            await kiem_dung_ca(conn, identity, bac_si_id, visit_id=visit_id)
            dong = await conn.fetchrow(
                "SELECT id, revision, du_lieu FROM phieu_kham_luot"
                " WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND form_id = $3 FOR UPDATE",
                cid,
                visit_id,
                form_id,
            )
            goi = json.dumps(sach, ensure_ascii=False)
            if dong is None:
                if expected_revision != 0 and not la_va:
                    raise ConflictError("Phiếu này không còn — tải lại trang.")
                moi = await conn.fetchval(
                    "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id,"
                    " version, du_lieu, revision, tao_boi, sua_boi)"
                    " VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, 1, $6::uuid,"
                    " $6::uuid)"
                    " ON CONFLICT (clinic_id, visit_id, form_id) DO NOTHING"
                    " RETURNING revision",
                    cid,
                    visit_id,
                    form_id,
                    int(ban),
                    goi,
                    identity.staff_id,
                )
                if moi is None:
                    raise ConflictError(
                        "Có người vừa mở phiếu này cùng lúc — tải lại để không đè."
                    )
            elif la_va:
                if not sach:
                    return {
                        "ok": True,
                        "revision": int(dong["revision"]),
                        "canh_bao": canh_bao,
                    }
                moi = await conn.fetchval(
                    "UPDATE phieu_kham_luot SET du_lieu = du_lieu || $2::jsonb,"
                    " revision = revision + 1, sua_boi = $3::uuid, sua_luc = now()"
                    " WHERE id = $1::uuid RETURNING revision",
                    dong["id"],
                    goi,
                    identity.staff_id,
                )
            else:
                if int(dong["revision"]) != expected_revision:
                    raise ConflictError(
                        "Có người vừa lưu phiếu này — tải lại để không đè."
                    )
                moi = await conn.fetchval(
                    "UPDATE phieu_kham_luot SET du_lieu = $2::jsonb,"
                    " revision = revision + 1, sua_boi = $3::uuid, sua_luc = now()"
                    " WHERE id = $1::uuid RETURNING revision",
                    dong["id"],
                    goi,
                    identity.staff_id,
                )
            # THAI KỲ từ phiếu Sản khoa (29/09/2026): hai ô kinh cuối / dự kiến
            # sinh VỪA ĐỔI trong lần lưu này → ghi sang `pregnancy`, cùng giao
            # dịch. Chỉ khi đổi: lưu một ô khác không được đè thai kỳ bác sĩ đã
            # sửa ở khối Thai kỳ bằng số cũ trên phiếu.
            cu_dl = _dict(dong["du_lieu"]) if dong is not None else {}
            sau_dl = {**cu_dl, **sach} if la_va else sach
            thai_ky: str | None = None
            if any(_gia(cu_dl.get(k)) != _gia(sau_dl.get(k)) for k in O_THAI_KY):
                thai_ky = await dong_bo_tu_phieu(
                    conn,
                    identity,
                    visit_id=visit_id,
                    kinh_cuoi_raw=_gia(sau_dl.get(O_KINH_CUOI)),
                    du_kien_sinh_raw=_gia(sau_dl.get(O_DU_KIEN_SINH)),
                )
            # HẸN TÁI KHÁM (Tuyền 29/09/2026): ngày hẹn VỪA ĐỔI (đặt / sửa /
            # xoá, kể cả sau Hoàn tất) → việc gọi CSKH của lượt bám theo, cùng
            # giao dịch. Trong SAVEPOINT: việc hỏng không được làm mất chữ bác
            # sĩ vừa gõ — phiếu vẫn lưu, màn được báo.
            hen: dict[str, Any] | None = None
            if any(
                _gia(cu_dl.get(k)) != _gia(sau_dl.get(k))
                for k in {*cu_dl, *sau_dl}
                if htk.la_o_ngay_hen(k)
            ):
                try:
                    async with conn.transaction():
                        hen = await htk.dong_bo(
                            conn,
                            identity,
                            visit_id=visit_id,
                            hom_nay=date.fromisoformat(clinic_today()),
                            bay_gio=datetime.now(timezone.utc),
                        )
                except Exception:  # noqa: BLE001 — xem trên
                    logger.exception("hen_tai_kham_dong_bo_hong", visit_id=visit_id)
                    hen = {
                        "trang_thai": "LOI",
                        "loi": "Phiếu đã lưu nhưng CHƯA cập nhật được việc gọi"
                        " tái khám — sửa lại ngày hẹn để thử lại.",
                    }
        return {
            "ok": True,
            "revision": int(moi),
            "canh_bao": canh_bao,
            # "tao" / "cap_nhat" — màn nạp lại khối Thai kỳ bên dưới phiếu.
            "thai_ky": thai_ky,
            # Việc gọi tái khám của lượt sau lần lưu này (None = ngày không đổi).
            "hen_tai_kham": hen,
        }

    # ------------------------------------------------------------------
    async def lich_su(
        self, *, visit_id: str, form_id: str | None, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        """Lịch sử sửa phiếu của lượt (P4A, 25/09/2026) — mới nhất trước.

        Trigger `ghi_lich_su_phieu_kham` ghi; ở đây chỉ đọc. Mỗi dòng: ai, từ lúc
        nào tới lúc nào, các ô đổi (giá trị trước → sau), và có phải sửa SAU khi
        bác sĩ đã Hoàn tất khám không.
        """
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "xem_lich_su")
            dong = await conn.fetch(
                "SELECT h.id::text AS id, h.form_id, h.bat_dau, h.sua_luc,"
                "       h.tu_revision, h.den_revision, h.truoc, h.sau,"
                "       s.full_name AS sua_boi_ten,"
                "       (v.exam_completed_at IS NOT NULL"
                "        AND h.sua_luc > v.exam_completed_at) AS sau_hoan_tat"
                "  FROM phieu_kham_lich_su h"
                "  JOIN visit v ON v.clinic_id = h.clinic_id"
                "   AND v.visit_id = h.visit_id"
                "  LEFT JOIN staff s ON s.id = h.sua_boi"
                " WHERE h.clinic_id = $1::uuid AND h.visit_id = $2::uuid"
                "   AND ($3::text IS NULL OR h.form_id = $3)"
                " ORDER BY h.sua_luc DESC",
                cid,
                visit_id,
                form_id,
            )

        def gia(o: Any) -> Any:
            return o.get("gia_tri") if isinstance(o, dict) else o

        def goi(o: Any) -> dict[str, Any]:
            return json.loads(o) if isinstance(o, str) else dict(o)

        ra: list[dict[str, Any]] = []
        for r in dong:
            truoc, sau = goi(r["truoc"]), goi(r["sau"])
            ra.append(
                {
                    "id": r["id"],
                    "form_id": r["form_id"],
                    "sua_boi": r["sua_boi_ten"],
                    "bat_dau": r["bat_dau"].isoformat(),
                    "sua_luc": r["sua_luc"].isoformat(),
                    "tao_moi": int(r["tu_revision"]) == 0,
                    "sau_hoan_tat": bool(r["sau_hoan_tat"]),
                    "thay_doi": [
                        {"ma": k, "truoc": gia(truoc.get(k)), "sau": gia(sau.get(k))}
                        for k in sorted(sau)
                    ],
                }
            )
        return ra

    # ------------------------------------------------------------------
    async def tham_chieu_that(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Danh mục C / F / thuốc của nguồn, GẮN mã thật của phòng khám này.

        Mã lấy từ bảng ghép viết tay (`anh_xa_danh_muc`) rồi hỏi DB xem phòng
        khám có dịch vụ / thuốc ấy đang bật không. Không có → `service_code`
        null (màn khoá ô), không đoán.
        """
        tc = tham_chieu_nguon()
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            # MỘT chỗ đọc danh mục (01/10/2026): hàm `danh_muc_dich_vu` nói
            # dịch vụ nào là phí khám, thuộc nhóm hàng nào — cùng luật với Bảng
            # giá dịch vụ & phòng và cảnh báo trang chủ.
            dong_dv = await conn.fetch(
                "SELECT service_code, unit_price, name, node_code, ma_kiotviet,"
                "       billing_owner = 'EXTERNAL_PARTNER' AS doi_tac_thu,"
                "       nhom"
                "  FROM public.danh_muc_dich_vu($1::uuid)"
                " WHERE active ORDER BY name",
                cid,
            )
            dv = {r["service_code"]: r["unit_price"] for r in dong_dv}
            # Khách trả TRỰC TIẾP cho đối tác (27/09/2026): nút "Chỉ định N mục
            # · tổng" ở bàn khám chỉ cộng phần phòng khám — cờ do máy chủ nói.
            dt_thu = {r["service_code"] for r in dong_dv if r["doi_tac_thu"]}
            dong_kho = await conn.fetch(
                "SELECT DISTINCT ON (name_raw) id, name_raw, name_base, unit_price,"
                "       don_vi_ban, duong_dung, cach_dung, luu_y, biet_duoc"
                "  FROM drug_catalog WHERE clinic_id = $1::uuid AND is_active"
                " ORDER BY name_raw, created_at",
                cid,
            )
            kho = {r["name_raw"]: r for r in dong_kho}
            # Gắn theo TÊN (bỏ qua hoa/thường, dấu cách) khi bảng ghép viết tay
            # thiếu (24/09/2026: "thuốc quy chuẩn về, đừng đẻ cái kiểu chưa gắn kho").
            theo_ten: dict[str, asyncpg.Record] = {}
            for r in dong_kho:
                for t in (r["name_raw"], r["name_base"]):
                    if t:
                        theo_ten.setdefault(_khoa_ten(t), r)

        theo_ma = {r["service_code"]: r for r in dong_dv}

        def gan(d: ax.DichVuPhieu | None) -> dict[str, Any]:
            if d is None or d.ma not in dv:
                return {
                    "service_code": None,
                    "gia": None,
                    "doi_tac_thu": False,
                    "ten_dich_vu": None,
                }
            gia = dv[d.ma]
            return {
                "service_code": d.ma,
                # TÊN THẬT của bảng giá (file phòng khám gửi) — màn hiện tên này,
                # nhãn phiếu giấy chỉ còn dòng phụ; ô tìm dò cả hai (C21: gõ
                # "trương lực" phải ra "Đo cơ lực âm đạo bằng máy (sàng lọc)").
                "ten_dich_vu": theo_ma[d.ma]["name"],
                "gia": int(gia) if gia is not None else None,
                "doi_tac_thu": d.ma in dt_thu,
                "nhom_hang": nhom_hang_hien(theo_ma[d.ma]["nhom"]),
                "khoa": ly_do_khoa_chi_dinh(theo_ma[d.ma]),
            }

        for nhom in tc["chi_dinh_cls"]:
            nhom["muc"] = [{**m, **gan(ax.CLS.get(m["nhan"]))} for m in nhom["muc"]]
        tc["thu_thuat"] = [
            {**t, **gan(ax.THU_THUAT.get(t["ma"]))} for t in tc["thu_thuat"]
        ]

        # DANH MỤC PHÒNG KHÁM: MỌI dịch vụ đang bán mà phiếu giấy chưa liệt kê
        # đều chỉ định được — gom theo NHÓM HÀNG của danh mục chuẩn (Tuyền
        # 01/10/2026: "danh sách chỉ định đang thiếu rất nhiều; KHÔNG được để
        # dịch vụ nào bị lọt"). Trước đây chỉ lấy dòng có mã KiotViet + có nhóm
        # việc → xét nghiệm nam khoa, tinh dịch đồ, biofeedback… lọt mất.
        # Chỉ trừ mục ĐÃ có trong chính mục C. Thủ thuật của phiếu giấy (Ghế
        # ĐTT, Biofeedback… ở mục F của phiếu Sàn chậu) VẪN có ở đây (C21,
        # 02/10/2026: bác sĩ phụ khoa tìm "Ghế điện từ trường" ở Chỉ định cận
        # lâm sàng không thấy — nó chỉ nằm ở danh sách thủ thuật).
        da_co = {
            m["service_code"]
            for nhom in tc["chi_dinh_cls"]
            for m in nhom["muc"]
            if m.get("service_code")
        }
        them: dict[str, list[dict[str, Any]]] = {}
        for r in dong_dv:
            # PHÍ KHÁM CŨNG CHỈ ĐỊNH ĐƯỢC (Tuyền 02/10/2026, C21: "toàn bộ 93
            # dịch vụ … phải chọn được ở bàn khám"). Không lọc theo phí khám nữa
            # — phí khám chưa nhóm việc vẫn HIỆN, khoá kèm lý do. Tiền khám không
            # tính hai lần: chặn ở `chan_trung_dich_vu_kham`. Chỉ dòng TIÊU ĐỀ của
            # phiếu giấy ("*XN dịch âm đạo", "• Laser") không bao giờ hiện lại.
            if r["service_code"] in da_co or r["service_code"] in ax.KHONG_LIET_KE:
                continue
            nhom_ten = nhom_hang_hien(r["nhom"]) or _NHOM_THEO_NODE.get(
                r["node_code"] or "", "Khác"
            )
            gia_dv = r["unit_price"]
            them.setdefault(nhom_ten, []).append(
                {
                    "nhan": r["name"],
                    "ten_dich_vu": r["name"],
                    "cach_tra_ket_qua": "",
                    "form_id_ket_qua": None,
                    "service_code": r["service_code"],
                    "gia": int(gia_dv) if gia_dv is not None else None,
                    "ma_kiotviet": r["ma_kiotviet"],
                    "doi_tac_thu": bool(r["doi_tac_thu"]),
                    "nhom_hang": nhom_ten,
                    "khoa": ly_do_khoa_chi_dinh(r),
                }
            )
        for ten in sorted(them, key=_thu_tu_nhom_hang):
            tc["chi_dinh_cls"].append(
                {"nhom": f"{ten} (danh mục phòng khám)", "muc": them[ten]}
            )

        # KHO LÀ NGUỒN (Tuyền 25/09/2026): tên, giá, đơn vị, cách dùng, lưu ý đọc
        # từ danh mục kho — dược sĩ sửa ở Kho thuốc là màn kê đơn đổi theo. Nhãn
        # phiếu chỉ còn là chỗ bác sĩ quen tìm. Mặt hàng kho không có trên phiếu
        # (Ozempic, King Seal…) cũng chọn được, kèm hướng dẫn.
        def tu_kho(m: dict[str, Any], r: asyncpg.Record | None) -> dict[str, Any]:
            if r is None:
                return {**m, "drug_catalog_id": None, "gia": None}
            return {
                **m,
                "brand": r["biet_duoc"] or m.get("brand") or "",
                "type": r["duong_dung"] or m.get("type") or "",
                "dosage": r["cach_dung"] or m.get("dosage") or "",
                "note": r["luu_y"] or m.get("note") or "",
                "unit": r["don_vi_ban"] or m.get("unit") or "",
                "drug_catalog_id": str(r["id"]),
                "gia": int(r["unit_price"]) if r["unit_price"] is not None else None,
            }

        mau = []
        da_gan: set[str] = set()
        for m in tc["mau_thuoc"]:
            ten_kho = ax.THUOC.get(m["ma"])
            r = kho.get(ten_kho) if ten_kho else None
            if r is None and m.get("nhan_nguon"):
                r = theo_ten.get(_khoa_ten(str(m["nhan_nguon"])))
            if r is not None:
                da_gan.add(str(r["id"]))
            mau.append(tu_kho(m, r))
        for r in dong_kho:
            if str(r["id"]) in da_gan:
                continue
            mau.append(
                tu_kho(
                    {"ma": f"kho:{r['id']}", "nhan_nguon": r["name_raw"]},
                    r,
                )
            )
        tc["mau_thuoc"] = mau
        return tc

    # Đơn thuốc (mục E) — ghi qua ĐÚNG đường bệnh án đang dùng
    # (`luu_don_chua_ky`), nên nhà thuốc nhận đơn y như trước.
    async def doc_don_thuoc(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            # Đơn giá + ĐVT của KHO (27/09/2026, bản giao diện mẫu: cột "Đơn
            # giá", ĐVT là chữ khi danh mục có). Đọc từ `drug_catalog` — cùng
            # giá quầy thu dùng (`quay_thuoc_service`); dòng ngoài danh mục → null.
            rows = await conn.fetch(
                "SELECT p.id::text, p.drug_catalog_id::text, p.drug_name_raw,"
                "       p.quantity, p.dosage_instructions, p.caution,"
                "       c.unit_price AS don_gia, c.don_vi_ban AS dvt_kho,"
                "       p.so_luong_dien_luc, p.so_luong_ke_goc,"
                "       sd.full_name AS so_luong_dien_boi"
                "  FROM prescription p"
                "  LEFT JOIN drug_catalog c"
                "    ON c.id = p.drug_catalog_id AND c.clinic_id = p.clinic_id"
                "  LEFT JOIN staff sd ON sd.id = p.so_luong_dien_boi"
                " WHERE p.clinic_id = $1::uuid AND p.visit_id = $2::uuid"
                "   AND p.removed_at IS NULL AND p.nguon = 'BAC_SI'"
                " ORDER BY p.created_at, p.id",
                identity.clinic_id,
                visit_id,
            )
        return [
            {
                **dict(r),
                "don_gia": int(r["don_gia"]) if r["don_gia"] is not None else None,
                "dvt_kho": (r["dvt_kho"] or "").strip() or None,
                # C14: quầy thu thuốc điền số lượng bác sĩ để trống — màn kê đơn
                # hiện "SL do thu ngân điền" (người + lúc).
                "so_luong_do_thu_ngan": r["so_luong_dien_luc"] is not None,
                "so_luong_dien_luc": r["so_luong_dien_luc"].isoformat()
                if r["so_luong_dien_luc"]
                else None,
            }
            for r in rows
        ]

    async def luu_don_thuoc(
        self,
        *,
        visit_id: str,
        dong: list[dict[str, Any]],
        ly_do: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        from clinicai.services.dinh_chinh_don import luu_don_chua_ky

        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await self._kiem_quyen(conn, identity, "ghi_phieu")
            # Thứ tự khoá của đơn thuốc: visit → prescription → allocation.
            luot = await conn.fetchrow(
                "SELECT clinic_patient_id::text AS pid FROM visit"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid FOR UPDATE",
                cid,
                visit_id,
            )
            if luot is None:
                raise ValidationError("Không tìm thấy lượt khám.")
            bac_si_id = await bac_si_cua_phien(
                conn,
                clinic_id=cid,
                visit_id=visit_id,
                nguoi_bam=identity.staff_id,
            )
            await kiem_dung_ca(conn, identity, bac_si_id, visit_id=visit_id)
            tom_tat = await luu_don_chua_ky(
                conn,
                visit_id=visit_id,
                clinic_id=cid,
                clinic_patient_id=luot["pid"],
                prescriptions=dong,
                created_by=identity.staff_id,
                identity=identity,
                ly_do=ly_do,
            )
            thay = int((tom_tat or {}).get("so_dong_thay") or 0)
            bo = int((tom_tat or {}).get("so_dong_bo") or 0)
            them = int((tom_tat or {}).get("so_dong_them") or 0)
            doi_tai_cho = int((tom_tat or {}).get("so_dong_sua") or 0) + int(
                (tom_tat or {}).get("so_dong_xoa") or 0
            )
            if thay or bo or them or doi_tai_cho:
                so_dong = await conn.fetchval(
                    "SELECT count(*) FROM prescription WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND removed_at IS NULL",
                    cid,
                    visit_id,
                )
                await emit_event(
                    conn,
                    ten="prescription.saved",
                    clinic_id=cid,
                    aggregate_id=visit_id,
                    payload=DonThuocDaLuu(
                        visit_id=visit_id,
                        so_dong=int(so_dong or 0),
                        so_dong_them=them,
                        so_dong_thay=thay,
                        so_dong_bo=bo,
                    ),
                    boi=nguoi_lam_thay(identity, bac_si_id),
                    correlation_id=visit_id,
                )
        return {"ok": True, "tom_tat": tom_tat}

    # ------------------------------------------------------------------
    async def dau_phieu(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            return await doc_dau_phieu(
                conn, clinic_id=identity.clinic_id, visit_id=visit_id
            )

    async def mau_du_phong(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_ket_qua_cls")
            return await doc_mau_du_phong(conn, clinic_id=identity.clinic_id)

    async def hanh_trinh(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Dải mốc hành trình ở đầu phiếu khám (lát 5) — cùng quyền đọc phiếu."""
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_phieu")
            kq = await doc_hanh_trinh(
                conn, clinic_id=identity.clinic_id, visit_id=visit_id
            )
        if kq is None:
            raise NotFoundError("Không tìm thấy lượt khám.")
        return kq

    async def ket_qua_chi_dinh(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_ket_qua_cls")
            return await doc_ket_qua_theo_chi_dinh(
                conn, clinic_id=identity.clinic_id, visit_id=visit_id
            )

    async def tep_chua_gan(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        """Tệp của lượt chưa gắn chỉ định (đợt 3, 27/09) — cùng quyền khối 2."""
        async with self._pool.acquire() as conn:
            await self._kiem_quyen(conn, identity, "doc_ket_qua_cls")
            return await doc_tep_chua_gan(
                conn, clinic_id=identity.clinic_id, visit_id=visit_id
            )


__all__ = [
    "HanhDong",
    "KiemQuyen",
    "PhieuKhamService",
    "chua_noi_quyen",
    "kiem_quyen_core",
]
