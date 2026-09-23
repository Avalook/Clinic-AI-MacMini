"""Form Template Engine — một cỗ máy điền biểu mẫu, dùng chung cho mọi phiếu.

18 mẫu kết quả, 7 biểu mẫu khám, các phiếu thủ thuật — chúng na ná nhau: vài
mục, mỗi mục vài ô, có câu mẫu điền sẵn, sửa thoải mái, xong thì xác nhận. Nên
chỉ có MỘT engine; từng biểu mẫu là DỮ LIỆU (`form_definition.khung`).

BỐN LUẬT ĐÃ CHỐT (chat #174–#178)

1. **"Hoàn tất" = xác nhận TOÀN BỘ nội dung hiện tại**, kể cả câu mẫu không ai
   sửa (#177). Trước lúc ấy, chữ điền sẵn chỉ là gợi ý nháp. Đây là xương sống:
   nó biến "máy điền hộ" thành "người chịu trách nhiệm".

2. **Hồ sơ cũ ghim phiên bản cũ.** Sửa mẫu v4 → v5 không đổi một chữ nào trong
   phiếu đã điền. Bản đã xuất bản không sửa tại chỗ — muốn đổi thì xuất bản bản
   mới.

3. **Người gõ ≠ người thực hiện.** Điều dưỡng nhập thay bác sĩ là chuyện thường
   ngày. `nhap_boi` là nhật ký; `thuc_hien_boi` là dữ liệu nghiệp vụ, và không
   bao giờ được suy ra từ ai đang đăng nhập.

4. **Mỗi giá trị nhớ nó từ đâu ra.** Thiếu cái này thì về sau không phân biệt
   được "bác sĩ viết thế" với "máy điền sẵn mà không ai đọc" — thứ duy nhất trả
   lời được câu ấy khi có chuyện.

KHÔNG CHẶN NGƯỜI DÙNG (#147, #157). Điền thiếu vẫn Hoàn tất được; máy chỉ đếm
"còn 3 mục chưa điền" và ghi lại. Bắt buộc chuyên môn chỉ bật khi phòng khám
chốt, không phải khi lập trình viên thấy nên thế.

TỰ LƯU KHÔNG PHÁT SỰ KIỆN (#150). Nháp là nháp. Chỉ `[Hoàn tất]` mới là sự thật.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.events.catalogue import KetQuaDaSua, KetQuaSanSang, PhieuDaHoanTat
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen

QUYEN_DIEN = "result.form.fill"
QUYEN_SUA_MAU = "catalogue.form_template.edit"
QUYEN_XUAT_BAN = "catalogue.form_template.publish"

#: Giá trị này từ đâu ra. V1 dùng năm nguồn; AI_SUGGESTION để dành.
NGUON = frozenset(
    {
        "TEMPLATE_DEFAULT",  # câu mẫu trong khung
        "USER",  # người gõ
        "PATIENT_CONTEXT",  # tự điền từ hồ sơ khách
        "SERVICE_CONTEXT",  # tự điền từ dịch vụ/phòng
        "COMPUTED",  # máy tính ra
        "PREVIOUS_RESULT",  # người bấm "Lấy từ lần trước"
        "AI_SUGGESTION",  # AI gợi ý — luôn là nháp
    }
)


class FormEngineService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Mở phiếu
    # ------------------------------------------------------------------
    async def mo_phieu(
        self,
        *,
        service_order_id: str,
        form_id: str,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Mở (hoặc tạo) phiếu cho một chỉ định, theo bản mẫu ĐANG DÙNG.

        Mở lần thứ hai KHÔNG tạo phiếu thứ hai, và KHÔNG nhảy sang bản mẫu mới
        hơn: phiếu đang điền dở phải giữ nguyên bản nó bắt đầu.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_DIEN)

            co = await conn.fetchrow(
                "SELECT * FROM form_instance"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND form_id = $3",
                identity.clinic_id,
                service_order_id,
                form_id,
            )
            if co is not None:
                khung = await self._khung(
                    conn, identity.clinic_id, form_id, co["version"]
                )
                return self._tra_phieu(co, khung)

            ban = await conn.fetchrow(
                "SELECT version, khung FROM form_definition"
                " WHERE clinic_id = $1::uuid AND form_id = $2"
                "   AND trang_thai = 'PUBLISHED'",
                identity.clinic_id,
                form_id,
            )
            if ban is None:
                raise ValidationError(
                    f"Biểu mẫu “{form_id}” chưa có bản nào đang dùng."
                )

            khung = json.loads(ban["khung"])
            moi = await conn.fetchrow(
                "INSERT INTO form_instance"
                " (clinic_id, service_order_id, form_id, version, du_lieu, nhap_boi)"
                " VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6::uuid)"
                " RETURNING *",
                identity.clinic_id,
                service_order_id,
                form_id,
                ban["version"],
                json.dumps(_mac_dinh_tu_khung(khung), ensure_ascii=False),
                identity.staff_id,
            )
        return self._tra_phieu(moi, khung)

    # ------------------------------------------------------------------
    # Tự lưu
    # ------------------------------------------------------------------
    async def luu_nhap(
        self,
        *,
        phieu_id: str,
        du_lieu: dict[str, Any],
        expected_revision: int,
        identity: StaffIdentity,
        thuc_hien_boi: str | None = None,
    ) -> dict[str, Any]:
        """Tự lưu. KHÔNG phát sự kiện — nháp không phải sự thật nghiệp vụ."""
        sach = _kiem_du_lieu(du_lieu)
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_DIEN)
            dong = await conn.fetchrow(
                "SELECT trang_thai, dang_sua, revision FROM form_instance"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
                identity.clinic_id,
                phieu_id,
            )
            if dong is None:
                raise ValidationError("Không tìm thấy phiếu này.")
            if dong["trang_thai"] == "READY" and not dong["dang_sua"]:
                # Không chặn vĩnh viễn — chặn tới khi người dùng nói rõ "tôi
                # muốn sửa" bằng lệnh `mo_sua`. Sửa được là quyền của họ; cái
                # phải giữ là DẤU VẾT của lần sửa ấy.
                raise ValidationError(
                    "Phiếu đã hoàn tất. Bấm [Sửa lại] trước khi gõ tiếp."
                )
            if dong["revision"] != expected_revision:
                # Hai người cùng gõ: không ghi đè im lặng.
                raise ValidationError(
                    "Phiếu vừa được người khác lưu — tải lại trước khi gõ tiếp."
                )

            moi = await conn.fetchrow(
                "UPDATE form_instance"
                "   SET du_lieu = $3::jsonb, revision = revision + 1,"
                "       nhap_boi = $4::uuid, sua_luc = now(),"
                "       thuc_hien_boi = COALESCE($5::uuid, thuc_hien_boi)"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                " RETURNING id::text, revision, sua_luc",
                identity.clinic_id,
                phieu_id,
                json.dumps(sach, ensure_ascii=False),
                identity.staff_id,
                thuc_hien_boi,
            )
        return {
            "ok": True,
            "id": moi["id"],
            "revision": moi["revision"],
            "luu_luc": moi["sua_luc"].isoformat(),
        }

    # ------------------------------------------------------------------
    # Hoàn tất
    # ------------------------------------------------------------------
    async def hoan_tat(
        self,
        *,
        phieu_id: str,
        expected_revision: int,
        identity: StaffIdentity,
        thuc_hien_boi: str | None = None,
    ) -> dict[str, Any]:
        """`CompleteForm` — xác nhận TOÀN BỘ nội dung hiện tại của phiếu.

        Kể cả những câu mẫu không ai sửa: bấm nút này là nhận trách nhiệm về
        chúng (#177). Vì vậy `hoan_tat_boi` là người bấm, và nguồn của mọi ô
        đang là câu mẫu được đổi sang "người dùng đã xác nhận".
        """
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_DIEN)
            dong = await conn.fetchrow(
                "SELECT i.*, d.khung,"
                "       (SELECT o.visit_id::text FROM service_order o"
                "         WHERE o.clinic_id = i.clinic_id"
                "           AND o.id = i.service_order_id) AS visit_id"
                "  FROM form_instance i"
                "  JOIN form_definition d"
                "    ON d.clinic_id = i.clinic_id AND d.form_id = i.form_id"
                "   AND d.version = i.version"
                " WHERE i.clinic_id = $1::uuid AND i.id = $2::uuid FOR UPDATE OF i",
                identity.clinic_id,
                phieu_id,
            )
            if dong is None:
                raise ValidationError("Không tìm thấy phiếu này.")
            sua_lai = bool(dong["trang_thai"] == "READY" and dong["dang_sua"])
            if dong["trang_thai"] == "READY" and not sua_lai:
                # Bấm hai lần: lần thứ hai không tạo sự thật thứ hai.
                return {
                    "ok": True,
                    "da_hoan_tat": True,
                    "revision": dong["revision"],
                    "con_trong": [],
                }
            if dong["revision"] != expected_revision:
                raise ValidationError(
                    "Phiếu vừa được người khác lưu — tải lại rồi hoàn tất."
                )

            du_lieu = json.loads(dong["du_lieu"])
            khung = json.loads(dong["khung"])
            con_trong = _con_trong(khung, du_lieu)

            # Xác nhận toàn bộ: ô nào còn là câu mẫu cũng thành "đã xác nhận".
            for o in du_lieu.values():
                if o.get("nguon") == "TEMPLATE_DEFAULT":
                    o["nguon"] = "USER"

            moi = await conn.fetchrow(
                "UPDATE form_instance"
                "   SET trang_thai = 'READY', dang_sua = false, du_lieu = $3::jsonb,"
                "       revision = revision + 1, hoan_tat_boi = $4::uuid,"
                "       hoan_tat_luc = now(), sua_luc = now(),"
                "       thuc_hien_boi = COALESCE($5::uuid, thuc_hien_boi, $4::uuid)"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                " RETURNING revision, thuc_hien_boi::text AS thuc_hien_boi",
                identity.clinic_id,
                phieu_id,
                json.dumps(du_lieu, ensure_ascii=False),
                identity.staff_id,
                thuc_hien_boi,
            )

            if not sua_lai:
                await emit_event(
                    conn,
                    ten="result_form.completed",
                    clinic_id=identity.clinic_id,
                    # Đối tượng là chính cái phiếu; chỉ định nằm trong payload.
                    aggregate_id=phieu_id,
                    aggregate_version=int(moi["revision"]),
                    payload=PhieuDaHoanTat(
                        service_order_id=str(dong["service_order_id"]),
                        visit_id=dong["visit_id"],
                        form_id=dong["form_id"],
                        form_version=int(dong["version"]),
                        nhap_boi=str(dong["nhap_boi"]) if dong["nhap_boi"] else None,
                        thuc_hien_boi=moi["thuc_hien_boi"],
                        so_o_con_trong=len(con_trong),
                    ),
                    boi=nguoi(identity),
                )

            # SỰ THẬT THỨ HAI TỪ CÙNG MỘT NÚT BẤM (ChatGPT #156, Tuyền #157).
            # "Dịch vụ đã làm xong" và "đã có kết quả để đọc" là hai chuyện; chỉ
            # dịch vụ nào sinh kết quả ngay tại phòng mới phát `result.ready`.
            # Lấy mẫu gửi ra ngoài thì kết quả hai ngày sau mới về.
            mode = await self._result_mode(
                conn, identity.clinic_id, str(dong["service_order_id"])
            )
            if mode == "INLINE":
                await emit_event(
                    conn,
                    ten="result.corrected" if sua_lai else "result.ready",
                    clinic_id=identity.clinic_id,
                    # Kết quả là một vòng đời RIÊNG của phiếu sinh ra nó —
                    # cùng mã, khác loại đối tượng, nên hai chuỗi số không
                    # giẫm chân nhau.
                    aggregate_id=phieu_id,
                    aggregate_version=int(moi["revision"]),
                    payload=(
                        KetQuaDaSua(
                            service_order_id=str(dong["service_order_id"]),
                            visit_id=dong["visit_id"],
                            form_id=dong["form_id"],
                            form_version=int(dong["version"]),
                            ban_thu=int(moi["revision"]),
                            sua_boi=identity.staff_id,
                        )
                        if sua_lai
                        else KetQuaSanSang(
                            service_order_id=str(dong["service_order_id"]),
                            visit_id=dong["visit_id"],
                            form_id=dong["form_id"],
                            form_version=int(dong["version"]),
                            result_mode=mode,
                            thuc_hien_boi=moi["thuc_hien_boi"],
                        )
                    ),
                    boi=nguoi(identity),
                    correlation_id=dong["visit_id"],
                )

        # Điền xong phiếu mà dịch vụ còn đang làm dở: đóng hộ, nhưng bằng LỆNH
        # của module Thực hiện (khai ở `modules.py` mục `goi_dong_bo`), không
        # thò tay vào bảng của nó.
        dich_vu = await self._dong_dich_vu_neu_dang_lam(
            service_order_id=str(dong["service_order_id"]), identity=identity
        )

        return {
            "ok": True,
            "da_hoan_tat": True,
            "la_lan_sua": sua_lai,
            "revision": moi["revision"],
            # Không chặn, chỉ nói: "còn 3 mục chưa điền".
            "con_trong": con_trong,
            # Dịch vụ đã đóng chưa, và nếu chưa thì vì sao — màn phải nói ra,
            # đừng để người làm tưởng xong mà hàng chờ vẫn còn tên khách.
            "dich_vu": dich_vu,
        }

    async def mo_sua(self, *, phieu_id: str, identity: StaffIdentity) -> dict[str, Any]:
        """`ReopenForm` — mở lại phiếu đã hoàn tất để sửa.

        KHÔNG đưa phiếu về nháp. Kết quả cũ vẫn là kết quả chính thức trong
        suốt lúc sửa — không có khoảnh khắc nào bác sĩ mở ra mà thấy trống.
        Bấm [Hoàn tất] lần nữa thì phát `result.corrected`.

        Bản thân việc mở ra sửa CHƯA phải một sự thật nghiệp vụ, nên không phát
        sự kiện: người ta mở ra rồi đổi ý là chuyện thường.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_DIEN)
            dong = await conn.fetchrow(
                "SELECT trang_thai, dang_sua, revision FROM form_instance"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
                identity.clinic_id,
                phieu_id,
            )
            if dong is None:
                raise ValidationError("Không tìm thấy phiếu này.")
            if dong["trang_thai"] != "READY":
                raise ValidationError("Phiếu chưa hoàn tất — cứ gõ tiếp.")
            if not dong["dang_sua"]:
                await conn.execute(
                    "UPDATE form_instance SET dang_sua = true, sua_luc = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    identity.clinic_id,
                    phieu_id,
                )
        return {"ok": True, "dang_sua": True, "revision": dong["revision"]}

    @staticmethod
    async def _result_mode(
        conn: asyncpg.Connection, clinic_id: str, service_order_id: str
    ) -> str:
        """Dịch vụ này có sinh kết quả ngay tại phòng không.

        Chưa cấu hình thì `NONE`: im lặng là "không có kết quả để đọc", chứ
        không phải "cứ báo có kết quả cho chắc". Báo thừa một lần là một lần
        bác sĩ mở ra và thấy trống.
        """
        mode = await conn.fetchval(
            "SELECT d.result_mode FROM dich_vu_mau_ket_qua d"
            "  JOIN service_order o"
            "    ON o.clinic_id = d.clinic_id AND o.service_code = d.service_code"
            " WHERE d.clinic_id = $1::uuid AND o.id = $2::uuid"
            " ORDER BY CASE d.result_mode WHEN 'INLINE' THEN 0 ELSE 1 END"
            " LIMIT 1",
            clinic_id,
            service_order_id,
        )
        return str(mode) if mode else "NONE"

    async def _dong_dich_vu_neu_dang_lam(
        self, *, service_order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Phiếu xong rồi thì dịch vụ coi như xong — nếu nó còn đang làm dở.

        BA LÝ DO ĐỂ LÀM Ở ĐÂY CHỨ KHÔNG PHẢI TRONG CÙNG GIAO DỊCH:

        1. Lệnh `CompleteService` tự khoá lượt và tự kiểm quyền. Gọi nó trong
           giao dịch đang mở của phiếu là mời một vòng khoá chéo.
        2. Phiếu đã hoàn tất là một sự thật độc lập: nó không được cuộn lại chỉ
           vì việc đóng dịch vụ hỏng.
        3. Nếu không đóng được, người làm PHẢI biết ngay — nên kết quả trả về
           nói rõ, thay vì im lặng để khách còn tên trong hàng chờ.

        Không có gì ép buộc ở đây: dịch vụ đã xong, đã huỷ, hay người bấm không
        có quyền đóng thì phiếu vẫn hoàn tất bình thường.
        """
        from clinicai.services.service_execution_service import (
            ServiceExecutionService,
        )

        async with self._pool.acquire() as conn:
            don = await conn.fetchrow(
                "SELECT execution_status, execution_revision FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                identity.clinic_id,
                service_order_id,
            )
            if don is None or don["execution_status"] != "IN_PROGRESS":
                return {"da_dong": False, "vi_sao": "khong_dang_lam"}
            lan = await conn.fetchval(
                "SELECT id::text FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND status = 'IN_PROGRESS'",
                identity.clinic_id,
                service_order_id,
            )
        if lan is None:
            return {"da_dong": False, "vi_sao": "khong_co_lan_lam_dang_chay"}

        try:
            await ServiceExecutionService(self._pool).xong(
                order_id=service_order_id,
                attempt_id=lan,
                expected_execution_revision=int(don["execution_revision"] or 0),
                identity=identity,
                idempotency_key=f"form-{service_order_id}-{lan}",
            )
        except SafetyGateError:
            # Điều dưỡng nhập hộ nhưng không có quyền đóng dịch vụ: phiếu vẫn
            # xong, và màn nói "nhờ người có quyền bấm Xong ở phòng".
            return {"da_dong": False, "vi_sao": "khong_du_quyen"}
        except Exception as loi:  # noqa: BLE001 — không làm hỏng việc đã xong
            return {"da_dong": False, "vi_sao": "loi", "chi_tiet": str(loi)[:200]}
        return {"da_dong": True}

    # ------------------------------------------------------------------
    # Sửa và xuất bản bản mẫu
    # ------------------------------------------------------------------
    async def xuat_ban(
        self, *, form_id: str, khung: list[dict[str, Any]], identity: StaffIdentity
    ) -> dict[str, Any]:
        """`PublishFormVersion` — bản mới thành bản đang dùng, bản cũ về hưu.

        Phiếu đã điền KHÔNG đổi: chúng ghim phiên bản của chúng.
        """
        if not isinstance(khung, list) or not khung:
            raise ValidationError("Khung biểu mẫu trống.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_XUAT_BAN)
            hien = await conn.fetchrow(
                "SELECT version, ten, nhom FROM form_definition"
                " WHERE clinic_id = $1::uuid AND form_id = $2"
                " ORDER BY version DESC LIMIT 1",
                identity.clinic_id,
                form_id,
            )
            if hien is None:
                raise ValidationError(f"Chưa có biểu mẫu “{form_id}”.")

            await conn.execute(
                "UPDATE form_definition SET trang_thai = 'RETIRED'"
                " WHERE clinic_id = $1::uuid AND form_id = $2"
                "   AND trang_thai = 'PUBLISHED'",
                identity.clinic_id,
                form_id,
            )
            ban_moi = int(hien["version"]) + 1
            await conn.execute(
                "INSERT INTO form_definition"
                " (clinic_id, form_id, version, ten, nhom, khung, trang_thai,"
                "  tao_boi, xuat_ban_boi, xuat_ban_luc)"
                " VALUES ($1::uuid, $2, $3, $4, $5, $6::jsonb, 'PUBLISHED',"
                "         $7::uuid, $7::uuid, now())",
                identity.clinic_id,
                form_id,
                ban_moi,
                hien["ten"],
                hien["nhom"],
                json.dumps(khung, ensure_ascii=False),
                identity.staff_id,
            )
        return {"ok": True, "form_id": form_id, "version": ban_moi}

    # ------------------------------------------------------------------
    @staticmethod
    async def _khung(
        conn: asyncpg.Connection, clinic_id: str, form_id: str, version: int
    ) -> list[dict[str, Any]]:
        raw = await conn.fetchval(
            "SELECT khung FROM form_definition"
            " WHERE clinic_id = $1::uuid AND form_id = $2 AND version = $3",
            clinic_id,
            form_id,
            version,
        )
        return list(json.loads(raw)) if raw else []

    @staticmethod
    def _tra_phieu(dong: asyncpg.Record, khung: list[dict[str, Any]]) -> dict[str, Any]:
        du_lieu = json.loads(dong["du_lieu"])
        return {
            "id": str(dong["id"]),
            "form_id": dong["form_id"],
            "version": dong["version"],
            "trang_thai": dong["trang_thai"],
            # Đã hoàn tất nhưng đang được sửa lại — màn phải nói ra, không để
            # người khác tưởng đây là bản cuối.
            "dang_sua": bool(dong["dang_sua"]),
            "revision": dong["revision"],
            "khung": khung,
            "du_lieu": du_lieu,
            "con_trong": _con_trong(khung, du_lieu),
        }


def _mac_dinh_tu_khung(khung: list[dict[str, Any]]) -> dict[str, Any]:
    """Câu mẫu trong khung thành giá trị ban đầu, đánh dấu rõ là câu mẫu."""
    return {
        block["ma"]: {"gia_tri": block.get("mac_dinh", ""), "nguon": "TEMPLATE_DEFAULT"}
        for muc in khung
        for block in muc.get("block", [])
        if block.get("mac_dinh")
    }


def _kiem_du_lieu(du_lieu: dict[str, Any]) -> dict[str, Any]:
    """Mỗi ô phải nói rõ giá trị và nguồn — nguồn lạ thì chặn ngay lúc lưu."""
    sach: dict[str, Any] = {}
    for ma, o in du_lieu.items():
        if not isinstance(o, dict) or "gia_tri" not in o:
            raise ValidationError(f"Ô “{ma}” phải có dạng {{gia_tri, nguon}}.")
        ngu = o.get("nguon", "USER")
        if ngu not in NGUON:
            raise ValidationError(f"Ô “{ma}” có nguồn lạ: {ngu}.")
        sach[ma] = {"gia_tri": o["gia_tri"], "nguon": ngu}
    return sach


def _con_trong(khung: list[dict[str, Any]], du_lieu: dict[str, Any]) -> list[str]:
    """Đếm ô chưa điền để NHẮC, không để chặn."""
    trong = []
    for muc in khung:
        for block in muc.get("block", []):
            o = du_lieu.get(block["ma"])
            if o is None or o.get("gia_tri") in (None, "", []):
                trong.append(block.get("ten", block["ma"]))
    return trong


__all__ = [
    "NGUON",
    "QUYEN_DIEN",
    "QUYEN_SUA_MAU",
    "QUYEN_XUAT_BAN",
    "FormEngineService",
    "SafetyGateError",
]
