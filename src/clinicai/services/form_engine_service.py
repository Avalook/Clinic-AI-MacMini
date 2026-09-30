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
from collections.abc import Mapping, Sequence
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.events.catalogue import (
    KetQuaDaSua,
    KetQuaSanSang,
    PhieuDaHoanTat,
    PhieuKetQuaDaXem,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.permissions.y_khoa import doc_duoc_in_phieu
from clinicai.phieu_kham.kiem_khung_mau import kiem_khung_mau
from clinicai.phieu_kham.mang_sang import dia_chi_benh_nhan, doc_chan_doan
from clinicai.services.bac_si_ky import bac_si_chi_dinh_hien_thi, bac_si_ky_in
from clinicai.services.bac_si_phu_trach import bac_si_thuc_hien_mac_dinh

QUYEN_DIEN = "result.form.fill"
MIME_DICOM = "application/dicom"

#: Ai ĐỌC được phiếu đã hoàn tất (chỉ đọc) — vai làm chuyên môn + điều phối.
DOC_KET_QUA: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
    }
)
#: Mở là "đã xem" (cùng tập với tệp kết quả, tep_ket_qua_service.XEM_LA_DA_XEM).
XEM_LA_DA_XEM: frozenset[ClinicRole] = frozenset(
    {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR, ClinicRole.TKYK}
)
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


def chon_phieu_de_in(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Phiếu nào của một chỉ định được IN (27/09/2026, đợt 3 — B11).

    Góp ý phòng khám: *"In phiếu vẫn thấy báo Dịch vụ chưa hoàn tất dù xong
    rồi"*. Gốc: mở khách ở phòng tự tạo phiếu nháp của mẫu chọn sẵn (vd
    `KQ_CHUNG`); đổi sang mẫu siêu âm rồi Hoàn tất thì phiếu nháp cũ vẫn nằm đó,
    và bản in in cả hai — trang nháp mang dòng "BẢN NHÁP".

    Luật: có phiếu READY thì CHỈ in READY (mới hoàn tất trước) — nháp bỏ qua
    nhưng KHÔNG xoá. Chưa có READY thì in nháp (mới tạo trước), bản in vẫn ghi
    BẢN NHÁP. READY đang sửa lại vẫn là READY: in bản chính thức.
    """
    xong = [r for r in rows if r["trang_thai"] == "READY"]
    if xong:
        return sorted(
            xong,
            key=lambda r: (r["hoan_tat_luc"] is not None, r["hoan_tat_luc"] or 0),
            reverse=True,
        )
    return sorted(rows, key=lambda r: r["tao_luc"], reverse=True)


def la_anh_xem_duoc(loai_tep: str | None, mime: str | None) -> bool:
    """Tệp là ẢNH trình duyệt vẽ được (in được, xem nhanh được).

    DICOM từng được nhận là ANH (máy siêu âm xuất thẳng DICOM) nhưng không
    trình duyệt nào vẽ nó bằng thẻ img: bản in ra khung trống. Từ 27/09 (đợt 3)
    tệp DICOM mới lưu là TAI_LIEU; kiểm cả mime để dòng cũ lỡ mang ANH cũng
    không lọt vào trang ảnh.
    """
    return loai_tep == "ANH" and (mime or "") != MIME_DICOM


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
            # HAI LỆNH MỞ CÙNG LÚC (29/09/2026): hai người cùng mở một phiếu, hay
            # một màn gọi mở hai lần, đều đọc "chưa có" rồi cùng INSERT — lệnh
            # sau đụng `uq_form_instance_chi_dinh` và màn báo "Resource already
            # exists" dù phiếu đã mở được. Ghi-nếu-chưa-có rồi đọc lại: lệnh sau
            # nhận đúng phiếu lệnh trước vừa tạo.
            moi = await conn.fetchrow(
                "INSERT INTO form_instance"
                " (clinic_id, service_order_id, form_id, version, du_lieu, nhap_boi)"
                " VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6::uuid)"
                " ON CONFLICT (clinic_id, service_order_id, form_id) DO NOTHING"
                " RETURNING *",
                identity.clinic_id,
                service_order_id,
                form_id,
                ban["version"],
                json.dumps(_mac_dinh_tu_khung(khung), ensure_ascii=False),
                identity.staff_id,
            )
            if moi is None:
                moi = await conn.fetchrow(
                    "SELECT * FROM form_instance"
                    " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                    "   AND form_id = $3",
                    identity.clinic_id,
                    service_order_id,
                    form_id,
                )
                if moi is None:  # không thể xảy ra: vừa đụng chính dòng này
                    raise ValidationError("Chưa mở được phiếu — thử lại.")
                khung = await self._khung(
                    conn, identity.clinic_id, form_id, moi["version"]
                )
        return self._tra_phieu(moi, khung)

    # ------------------------------------------------------------------
    # Xem kết quả (chỉ đọc) — bác sĩ chính / thư ký ở Bàn khám
    # ------------------------------------------------------------------
    async def xem_ket_qua(
        self, *, service_order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Phiếu kết quả ĐÃ HOÀN TẤT của một chỉ định — CHỈ ĐỌC.

        Trước 24/09 phiếu chỉ mở được ở phòng làm (lệnh `mo_phieu` đòi quyền
        ĐIỀN), nên bác sĩ chính không đọc được kết quả dạng phiếu trên Bàn khám.
        Đọc là bản CHÍNH THỨC (`du_lieu`), không phải bản đang sửa dở.

        "Đã xem" (Tuyền chốt 24/09: duyệt không bắt buộc, mở kết quả là tự ghi):
        bác sĩ / thư ký y khoa / BS siêu âm mở lần đầu → `service_order
        .da_xem_ket_qua_*` + sự kiện `result.viewed`.
        """
        if not identity.co_vai(DOC_KET_QUA):
            raise SafetyGateError("Vai của bạn không đọc phiếu kết quả.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            rows = await conn.fetch(
                "SELECT * FROM form_instance WHERE clinic_id = $1::uuid"
                "   AND service_order_id = $2::uuid AND trang_thai = 'READY'"
                " ORDER BY form_id",
                cid,
                service_order_id,
            )
            phieu = []
            for r in rows:
                khung = await self._khung(conn, cid, r["form_id"], r["version"])
                phieu.append(
                    {
                        "id": str(r["id"]),
                        "form_id": r["form_id"],
                        "khung": khung,
                        "du_lieu": json.loads(r["du_lieu"]),
                        "dang_sua": bool(r["dang_sua"]),
                    }
                )
            # "Đã xem" là DỮ KIỆN y khoa (bác sĩ / thư ký đã đọc kết quả), không
            # phải quyền: hỏi VAI TÀI KHOẢN, không hỏi vai suy từ lego — mở full
            # lego (30/09/2026) thì lễ tân mở phiếu để in cũng mang vai DOCTOR.
            if phieu and identity.vai_goc in XEM_LA_DA_XEM:
                vid = await conn.fetchval(
                    "UPDATE service_order SET da_xem_ket_qua_luc = now(),"
                    "       da_xem_ket_qua_boi = $3::uuid"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                    "   AND da_xem_ket_qua_luc IS NULL"
                    " RETURNING visit_id::text",
                    cid,
                    service_order_id,
                    identity.staff_id,
                )
                if vid is not None:
                    await emit_event(
                        conn,
                        ten="result.viewed",
                        clinic_id=cid,
                        aggregate_id=service_order_id,
                        so_ke_tiep=True,
                        payload=PhieuKetQuaDaXem(
                            service_order_id=service_order_id, visit_id=vid
                        ),
                        boi=nguoi(identity),
                        correlation_id=vid,
                    )
        return {"phieu": phieu}

    # ------------------------------------------------------------------
    # In phiếu kết quả (23/09/2026 khuya: "sửa lại rồi lưu rồi in được")
    # ------------------------------------------------------------------
    async def in_ket_qua(
        self, *, service_order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Dữ liệu để IN mọi phiếu kết quả của một chỉ định — chỉ đọc.

        Bản chính thức (READY) nếu có; phiếu mới lưu nháp vẫn in được nhưng
        màn in phải ghi "BẢN NHÁP". Thông tin bệnh nhân lấy từ hồ sơ (mẫu
        không có khung bệnh nhân). Ai in: vai đọc kết quả, người được điền kết
        quả, và CSKH (gửi kết quả cho khách). In KHÔNG tính là "đã xem".
        """
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            # Theo QUYỀN in phiếu (28/09/2026): CSKH (`crm.manage`) + các khâu
            # quầy in trả khách, không phụ thuộc vai của tài khoản.
            if not (
                identity.co_vai(DOC_KET_QUA | {ClinicRole.CSKH})
                or await can(conn, identity, QUYEN_DIEN)
                or await doc_duoc_in_phieu(conn, identity)
            ):
                raise SafetyGateError("Bạn không có quyền in phiếu kết quả.")
            dau = await conn.fetchrow(
                "SELECT o.service_name, o.service_code, o.visit_id::text AS visit_id,"
                "       c.name AS phong_kham, c.address AS dia_chi_pk,"
                "       p.full_name, p.patient_code, p.birth_year, p.date_of_birth,"
                "       p.gender, p.phone_primary, p.address,"
                "       p.address_detail, p.ward_name, p.province_name,"
                # Đầu trang HAI BÊN (27/09/2026 — bản mẫu): cơ sở của LƯỢT +
                # địa chỉ; mã dịch vụ (mã phòng khám), số booking / check-in.
                "       lv.name AS co_so, lv.address AS dia_chi_co_so,"
                "       v.checked_in_at, a.so_booking, a.so_tiep_don,"
                "       sp.ma_kiotviet"
                "  FROM service_order o"
                "  JOIN visit v"
                "    ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id"
                "  JOIN patient p ON p.clinic_patient_id = v.clinic_patient_id"
                "   AND p.clinic_id = v.clinic_id"
                "  JOIN clinic c ON c.id = o.clinic_id"
                "  LEFT JOIN clinic_location lv"
                "    ON lv.id = v.location_id AND lv.clinic_id = v.clinic_id"
                "  LEFT JOIN appointment a"
                "    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id"
                "  LEFT JOIN LATERAL ("
                "       SELECT s.ma_kiotviet FROM service_price s"
                "        WHERE s.clinic_id = o.clinic_id"
                "          AND s.service_code = o.service_code"
                "        ORDER BY s.active DESC LIMIT 1) sp ON true"
                " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid",
                cid,
                service_order_id,
            )
            if dau is None:
                raise ValidationError("Không tìm thấy chỉ định.")
            # Giờ làm + người làm: LẦN LÀM gần nhất (làm lại sau khi dừng thì
            # lần mới là lần có kết quả).
            lan = await conn.fetchrow(
                "SELECT a.started_at, a.completed_at, s.full_name AS nguoi_lam,"
                "       a.completed_by::text AS completed_by,"
                "       a.started_by::text AS started_by"
                "  FROM service_execution_attempt a"
                "  LEFT JOIN staff s ON s.id = coalesce(a.completed_by, a.started_by)"
                " WHERE a.clinic_id = $1::uuid AND a.service_order_id = $2::uuid"
                " ORDER BY a.attempt_no DESC LIMIT 1",
                cid,
                service_order_id,
            )
            chan_doan = await doc_chan_doan(
                conn, clinic_id=cid, visit_id=dau["visit_id"]
            )
            # Bảy phiếu khám không phải kết quả của chỉ định — cùng bộ lọc với
            # khối 2 (`ket_qua_chi_dinh._PHIEU_KHONG_PHAI_KET_QUA`).
            from clinicai.phieu_kham.khung import FORM_IDS

            rows = await conn.fetch(
                "SELECT i.*, d.ten AS ten_mau, th.full_name AS thuc_hien_ten,"
                "       ht.full_name AS hoan_tat_ten"
                "  FROM form_instance i"
                "  JOIN form_definition d ON d.clinic_id = i.clinic_id"
                "   AND d.form_id = i.form_id AND d.version = i.version"
                # Tên in dưới "Bác sĩ thực hiện" — KHÔNG lùi về người nhập
                # (Tuyền 29/09/2026: người nhập chỉ ở lịch sử hệ thống).
                "  LEFT JOIN staff th ON th.id = i.thuc_hien_boi"
                "  LEFT JOIN staff ht ON ht.id = i.hoan_tat_boi"
                " WHERE i.clinic_id = $1::uuid AND i.service_order_id = $2::uuid"
                "   AND NOT (i.form_id = ANY($3::text[]))"
                " ORDER BY i.tao_luc",
                cid,
                service_order_id,
                list(FORM_IDS),
            )
            phieu = []
            for r in chon_phieu_de_in(rows):
                khung = await self._khung(conn, cid, r["form_id"], r["version"])
                # Chỗ ký "Bác sĩ thực hiện" LUÔN là bác sĩ (Tuyền 29/09/2026):
                # người thực hiện / người bấm là bác sĩ → họ; không thì bác sĩ
                # đứng phòng theo lịch LÚC HOÀN TẤT (không phải lúc in) → bác sĩ
                # của lượt → bác sĩ chỉ định. Không ai → để trống. Không ghi đè
                # dữ liệu; người bấm vẫn ở `hoan_tat_boi` (lịch sử).
                ky = await bac_si_ky_in(
                    conn,
                    clinic_id=cid,
                    service_order_id=service_order_id,
                    nguoi_bam=(r["thuc_hien_boi"], r["hoan_tat_boi"]),
                    luc=(
                        r["hoan_tat_luc"]
                        or (lan["completed_at"] if lan else None)
                        or (lan["started_at"] if lan else None)
                        or r["sua_luc"]
                        or r["tao_luc"]
                    ),
                )
                ten_ky = ky.ten if ky else None
                phieu.append(
                    {
                        "form_id": r["form_id"],
                        "ten": r["ten_mau"],
                        "khung": khung,
                        "du_lieu": json.loads(r["du_lieu"]),
                        "ban_nhap": r["trang_thai"] != "READY",
                        "thuc_hien": ten_ky,
                        "hoan_tat_boi": r["hoan_tat_ten"],
                        "hoan_tat_luc": (
                            r["hoan_tat_luc"].isoformat() if r["hoan_tat_luc"] else None
                        ),
                    }
                )
            # ẢNH in kèm phiếu (lát 5, 26/09/2026 — bản mẫu: 4 tấm/hàng). Tệp đã
            # thu hồi / bị đánh dấu không hợp lệ không in. Video, tài liệu chỉ
            # đếm — giấy không phát được video. DICOM (27/09 đợt 3) cũng chỉ
            # đếm: trình duyệt không vẽ được, in ra là một khung trống.
            tep = await conn.fetch(
                "SELECT id::text AS id, ten_hien_thi, loai_tep, mime FROM tep_ket_qua"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND thu_hoi_luc IS NULL"
                "   AND coalesce(xac_nhan_trang_thai, 'HOP_LE') = 'HOP_LE'"
                " ORDER BY tai_len_luc, id",
                cid,
                service_order_id,
            )
            # Chỉ định CHỈ CÓ ẢNH (không phiếu): "Người thực hiện" cũng là BÁC SĨ
            # — người làm / người tải là điều dưỡng thì lấy bác sĩ đứng phòng lúc
            # làm, rồi bác sĩ của lượt. Không lùi về tên người làm.
            ky_chung = await bac_si_ky_in(
                conn,
                clinic_id=cid,
                service_order_id=service_order_id,
                nguoi_bam=((lan["completed_by"], lan["started_by"]) if lan else ()),
                luc=((lan["completed_at"] or lan["started_at"]) if lan else None)
                or await conn.fetchval(
                    "SELECT min(tai_len_luc) FROM tep_ket_qua"
                    " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid",
                    cid,
                    service_order_id,
                ),
            )
            bs_chi_dinh = await bac_si_chi_dinh_hien_thi(conn, cid, service_order_id)
        return {
            "anh": [
                {"id": t["id"], "ten": t["ten_hien_thi"]}
                for t in tep
                if la_anh_xem_duoc(t["loai_tep"], t["mime"])
            ],
            "so_tep_khac": sum(
                1 for t in tep if not la_anh_xem_duoc(t["loai_tep"], t["mime"])
            ),
            # Video / tài liệu / DICOM: không in, nhưng TẢI VỀ được ở cột ảnh
            # của trang in (Tuyền 28/09/2026: "tải ảnh video riêng").
            "tep_khac": [
                {"id": t["id"], "ten": t["ten_hien_thi"], "loai_tep": t["loai_tep"]}
                for t in tep
                if not la_anh_xem_duoc(t["loai_tep"], t["mime"])
            ],
            "phong_kham": {
                "ten": dau["phong_kham"],
                "dia_chi": dau["dia_chi_co_so"] or dau["dia_chi_pk"],
                "co_so": dau["co_so"],
            },
            "ma_dich_vu": dau["ma_kiotviet"] or dau["service_code"],
            "so_booking": dau["so_booking"],
            "so_tiep_don": dau["so_tiep_don"],
            "ngay_kham": (
                dau["checked_in_at"].astimezone(CLINIC_TZ).date().isoformat()
                if dau["checked_in_at"]
                else None
            ),
            "gio_lam": (
                {
                    "bat_dau": lan["started_at"].isoformat(),
                    "xong": (
                        lan["completed_at"].isoformat() if lan["completed_at"] else None
                    ),
                    "nguoi_lam": lan["nguoi_lam"],
                }
                if lan
                else None
            ),
            "chan_doan": chan_doan,
            "benh_nhan": {
                "ho_ten": dau["full_name"],
                "ma_bn": dau["patient_code"],
                "nam_sinh": (
                    dau["date_of_birth"].isoformat()
                    if dau["date_of_birth"]
                    else dau["birth_year"]
                ),
                "gioi_tinh": dau["gender"],
                "dien_thoai": dau["phone_primary"],
                "dia_chi": dia_chi_benh_nhan(dict(dau)),
            },
            "dich_vu": dau["service_name"],
            # "BS chỉ định" chỉ in BÁC SĨ — điều dưỡng/thư ký chỉ định hộ thì
            # lấy bác sĩ của lượt (Tuyền 29/09/2026).
            "bac_si_chi_dinh": bs_chi_dinh.ten if bs_chi_dinh else None,
            # Chữ ký chung của chỉ định (chỉ có ảnh, không phiếu) — bác sĩ.
            "bac_si_thuc_hien": ky_chung.ten if ky_chung else None,
            "phieu": phieu,
        }

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

            # ĐANG SỬA THÌ GHI VÀO NHÁP. Bản chính thức (`du_lieu`) đứng yên
            # cho tới khi bấm [Xác nhận sửa] — đó là thứ làm câu "bản cũ vẫn là
            # kết quả chính thức" trên màn thành sự thật, chứ không phải lời hứa.
            if dong["dang_sua"]:
                # ĐANG SỬA: KHÔNG chạm gì thuộc về bản chính thức — không
                # `du_lieu`, không `nhap_boi`, không `thuc_hien_boi`.
                #
                # Bản trước ghi `nhap_boi = người đang gõ` ở mọi lần tự lưu. Hệ
                # quả: v1 còn nguyên nội dung, nhưng tên NGƯỜI NHẬP v1 âm thầm
                # biến thành người đang gõ v2 — một dòng hồ sơ nói sai về ai đã
                # làm, mà không ai bấm nút nào.
                #
                # NHƯNG KHÔNG ĐÁNH MẤT NGƯỜI GÕ NHÁP. Contract Form Engine
                # tách `nhap_boi` (người gõ — nhật ký) khỏi `thuc_hien_boi`
                # (người làm — dữ liệu nghiệp vụ); bỏ cả hai trong lúc sửa là
                # xoá một vai có thật:
                #
                #   v1: điều dưỡng A nhập · bác sĩ B thực hiện
                #   sửa: điều dưỡng C gõ · B vẫn thực hiện · bác sĩ D xác nhận
                #
                # Ba người, ba vai. Nên metadata đi THEO BẢN NHÁP, và chỉ trở
                # thành chính thức lúc [Xác nhận sửa].
                moi = await conn.fetchrow(
                    "UPDATE form_instance"
                    "   SET du_lieu_dang_sua = $3::jsonb,"
                    "       nhap_boi_dang_sua = $4::uuid,"
                    "       thuc_hien_boi_dang_sua ="
                    "           COALESCE($5::uuid, thuc_hien_boi_dang_sua),"
                    "       revision = revision + 1, sua_luc = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                    " RETURNING id::text, revision, sua_luc",
                    identity.clinic_id,
                    phieu_id,
                    json.dumps(sach, ensure_ascii=False),
                    identity.staff_id,
                    thuc_hien_boi,
                )
            else:
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
        ly_do_sua: str | None = None,
    ) -> dict[str, Any]:
        """`CompleteForm` — xác nhận TOÀN BỘ nội dung hiện tại của phiếu.

        Kể cả những câu mẫu không ai sửa: bấm nút này là nhận trách nhiệm về
        chúng (#177). Vì vậy `hoan_tat_boi` là người bấm, và nguồn của mọi ô
        đang là câu mẫu được đổi sang "người dùng đã xác nhận".

        LẦN SỬA THÌ PHẢI CÓ LÝ DO. Kết quả này đã được in ra giấy và giao cho
        khách; đổi nó mà không nói vì sao là để lại một câu hỏi không ai trả lời
        được. `ly_do_sua` bắt buộc khi đang sửa lại, và nó đi vào
        `visit_amendment.reason` — nơi duy nhất giữ lý do, không chép sang chỗ
        thứ hai.
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

            # ĐANG SỬA: nội dung mới nằm ở bản NHÁP, bản chính thức vẫn là bản
            # người bệnh đang cầm trên tay.
            ban_cu = json.loads(dong["du_lieu"])
            du_lieu = json.loads(dong["du_lieu_dang_sua"]) if sua_lai else ban_cu
            khung = json.loads(dong["khung"])
            con_trong = _con_trong(khung, du_lieu)

            anh_cu: dict[str, Any] = {}
            if sua_lai:
                anh_cu = _anh_phien_ban(dong, du_lieu=ban_cu, nhap_theo_nhap=False)
                # Bản dự kiến, CHỈ để trả lời "có gì đổi không". Ảnh chụp thật
                # dựng SAU khi ghi, từ chính giá trị Postgres vừa nhận.
                du_kien = _anh_phien_ban(
                    dong,
                    du_lieu=du_lieu,
                    nhap_theo_nhap=True,
                    hoan_tat_boi=identity.staff_id,
                    thuc_hien_boi=thuc_hien_boi,
                )
                # THỨ TỰ CÓ CHỦ Ý: hỏi "có đổi gì không" TRƯỚC, rồi mới đòi lý
                # do. Bắt người ta gõ lý do xong mới báo "thực ra không thay gì"
                # là bắt họ làm một việc vô ích rồi mới nói.
                if not _da_doi_gi(anh_cu, du_kien):
                    raise ValidationError(
                        "Không có gì thay đổi so với bản hiện tại — bấm"
                        " [Huỷ sửa] nếu bạn đổi ý."
                    )
                if not (ly_do_sua or "").strip():
                    raise ValidationError("Sửa kết quả đã hoàn tất thì phải ghi lý do.")

            # Xác nhận toàn bộ: ô nào còn là câu mẫu cũng thành "đã xác nhận".
            for o in du_lieu.values():
                if o.get("nguon") == "TEMPLATE_DEFAULT":
                    o["nguon"] = "USER"

            # NGƯỜI THỰC HIỆN MẶC ĐỊNH (Tuyền 29/09/2026: "mặc định tên bác sĩ;
            # trong hệ thống ghi lịch sử thì mới ghi dòng người nhập"). Không ai
            # chọn người thực hiện → BÁC SĨ đang đứng phòng làm chỉ định hôm nay
            # (`bac_si_phu_trach.bac_si_thuc_hien_mac_dinh`), không phải điều
            # dưỡng bấm Hoàn tất. Người bấm vẫn nằm ở `hoan_tat_boi`.
            mac_dinh = identity.staff_id
            if thuc_hien_boi is None and not (
                dong["thuc_hien_boi_dang_sua"] or dong["thuc_hien_boi"]
            ):
                mac_dinh = await bac_si_thuc_hien_mac_dinh(
                    conn,
                    clinic_id=identity.clinic_id,
                    service_order_id=str(dong["service_order_id"]),
                    nguoi_bam=identity.staff_id,
                )

            # ĐẨY NHÁP THÀNH CHÍNH THỨC — cả nội dung lẫn metadata, rồi dọn
            # sạch mọi cột nháp. `hoan_tat_boi` là người bấm nút; `nhap_boi`
            # là người đã gõ; `thuc_hien_boi` là người được chọn (hoặc bác sĩ
            # mặc định ở trên). Ba vai khác nhau.
            moi = await conn.fetchrow(
                "UPDATE form_instance"
                "   SET trang_thai = 'READY', dang_sua = false,"
                "       du_lieu = $3::jsonb, du_lieu_dang_sua = NULL,"
                "       nhap_boi = COALESCE(nhap_boi_dang_sua, nhap_boi),"
                "       nhap_boi_dang_sua = NULL,"
                "       revision = revision + 1, hoan_tat_boi = $4::uuid,"
                "       hoan_tat_luc = now(), sua_luc = now(),"
                "       thuc_hien_boi = COALESCE($5::uuid,"
                "           thuc_hien_boi_dang_sua, thuc_hien_boi, $6::uuid),"
                "       thuc_hien_boi_dang_sua = NULL"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                " RETURNING revision, nhap_boi::text AS nhap_boi,"
                "           thuc_hien_boi::text AS thuc_hien_boi,"
                "           hoan_tat_boi::text AS hoan_tat_boi, hoan_tat_luc",
                identity.clinic_id,
                phieu_id,
                json.dumps(du_lieu, ensure_ascii=False),
                identity.staff_id,
                thuc_hien_boi,
                mac_dinh,
            )

            ban_thu = 1
            if sua_lai:
                # ẢNH CHỤP DỰNG TỪ GIÁ TRỊ POSTGRES VỪA GHI, không dựng lại từ
                # phía Python. `hoan_tat_luc` trong ảnh phải là CHÍNH cái mốc
                # `form_instance.hoan_tat_luc` đang mang — nếu Python tự lấy giờ
                # của mình thì có hai mốc lệch nhau cho cùng một sự việc, và
                # không ai biết mốc nào mới là lúc kết quả được chốt.
                anh_moi = {
                    "du_lieu": du_lieu,
                    "nhap_boi": moi["nhap_boi"],
                    "thuc_hien_boi": moi["thuc_hien_boi"],
                    "hoan_tat_boi": moi["hoan_tat_boi"],
                    # ISO-8601 chuẩn (`2026-09-23T05:06:32+00:00`), không phải
                    # `str(datetime)` — bản sau có dấu cách thay chữ T, và ảnh
                    # chụp này còn phải đọc lại được sau nhiều năm.
                    "hoan_tat_luc": _gio_iso(moi["hoan_tat_luc"]),
                }
                ban_thu = await self._ghi_lan_sua(
                    conn,
                    identity=identity,
                    phieu_id=phieu_id,
                    visit_id=dong["visit_id"],
                    anh_cu=anh_cu,
                    anh_moi=anh_moi,
                    ly_do=(ly_do_sua or "").strip(),
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
                    # Đối tượng `ket_qua` đánh số theo PHIÊN BẢN CHUYÊN MÔN, nên
                    # chuỗi số của nó là 1, 2, 3… chứ không phải `revision` —
                    # `revision` tăng cả khi tự lưu nháp.
                    aggregate_version=ban_thu,
                    payload=(
                        KetQuaDaSua(
                            service_order_id=str(dong["service_order_id"]),
                            visit_id=dong["visit_id"],
                            form_id=dong["form_id"],
                            form_version=int(dong["version"]),
                            ban_thu=ban_thu,
                            sua_boi=identity.staff_id,
                        )
                        if sua_lai
                        else KetQuaSanSang(
                            service_order_id=str(dong["service_order_id"]),
                            visit_id=dong["visit_id"],
                            form_id=dong["form_id"],
                            form_version=int(dong["version"]),
                            result_mode=mode,
                            ban_thu=ban_thu,
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
            "ban_thu": ban_thu,
            "revision": moi["revision"],
            # Không chặn, chỉ nói: "còn 3 mục chưa điền".
            "con_trong": con_trong,
            # Dịch vụ đã đóng chưa, và nếu chưa thì vì sao — màn phải nói ra,
            # đừng để người làm tưởng xong mà hàng chờ vẫn còn tên khách.
            "dich_vu": dich_vu,
        }

    async def mo_sua(self, *, phieu_id: str, identity: StaffIdentity) -> dict[str, Any]:
        """`ReopenForm` — mở lại phiếu đã hoàn tất để sửa.

        KHÔNG đưa phiếu về nháp, và KHÔNG cho tự lưu chạm vào bản chính thức:
        `du_lieu` đứng yên, mọi thứ người dùng gõ đi vào `du_lieu_dang_sua`.
        Kết quả cũ vẫn là kết quả chính thức trong suốt lúc sửa — không có
        khoảnh khắc nào bác sĩ mở ra mà thấy trống.

        CHÉP MỘT LẦN. Người thứ hai mở ra sửa khi đã `dang_sua` thì nhận đúng
        bản nháp đang có; chép lại từ bản chính thức là xoá mất những gì người
        đầu vừa gõ.

        Bản thân việc mở ra sửa CHƯA phải một sự thật nghiệp vụ, nên không phát
        sự kiện: người ta mở ra rồi đổi ý là chuyện thường — và có [Huỷ sửa]
        cho đúng lúc ấy.

        TRẢ VỀ TOÀN BỘ PHIẾU, không chỉ số revision. Trả mỗi số là để lại một
        khoảng hở chết người: người thứ hai nhận SỐ mới nhưng màn hình họ vẫn
        giữ NỘI DUNG cũ, và lần tự lưu kế tiếp ghi đè những gì người đầu vừa gõ
        — bằng đúng số revision hợp lệ, nên không lớp chống ghi đè nào bắt được.
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
                    "UPDATE form_instance"
                    "   SET dang_sua = true, du_lieu_dang_sua = du_lieu,"
                    # Người THỰC HIỆN mặc định giữ nguyên người của bản chính
                    # thức: sửa một câu kết luận không đổi ai đã làm siêu âm.
                    # Người GÕ thì để trống — chưa ai gõ gì cả.
                    "       thuc_hien_boi_dang_sua = thuc_hien_boi,"
                    "       nhap_boi_dang_sua = NULL, sua_luc = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    identity.clinic_id,
                    phieu_id,
                )
            # Đọc lại SAU khi mở: người thứ hai phải nhận đúng bản nháp đang
            # có, kể cả những ô người đầu vừa gõ.
            moi = await conn.fetchrow(
                "SELECT * FROM form_instance"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                identity.clinic_id,
                phieu_id,
            )
            if moi is None:
                raise ValidationError("Không tìm thấy phiếu này.")
            khung = await self._khung(
                conn, identity.clinic_id, moi["form_id"], moi["version"]
            )
        return {"ok": True, **self._tra_phieu(moi, khung)}

    @staticmethod
    async def _ghi_lan_sua(
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        phieu_id: str,
        visit_id: str | None,
        anh_cu: dict[str, Any],
        anh_moi: dict[str, Any],
        ly_do: str,
    ) -> int:
        """Chụp bản cũ và bản mới, rồi nối chúng vào lịch sử. Trả số bản mới.

        ẢNH CHỤP LÀ CẢ PHIÊN BẢN, KHÔNG CHỈ PHẦN CHỮ. Kết quả ở phòng khám này
        được IN RA GIẤY và giao cho khách; muốn mở lại bản v1 thì phải có nguyên
        nó, không phải dựng lại từ hiệu số qua nhiều đời.

        Và "nguyên nó" gồm cả AI ĐÃ LÀM:

            {du_lieu, nhap_boi, thuc_hien_boi, hoan_tat_boi, hoan_tat_luc}

        Nếu chỉ chụp `du_lieu` thì tới lần sửa thứ hai, `form_instance` bị đẩy
        sang metadata của v3 và câu "ai nhập v2, ai thực hiện v2" không còn chỗ
        nào trả lời. v1→v2 nhìn rất đẹp, và chỉ vỡ ở v3.

        (Nói cho đúng: ảnh chụp này giữ được NỘI DUNG CHUYÊN MÔN của bản cũ, kèm
        `form_definition.version` để biết khung lúc ấy. Nó KHÔNG bảo đảm in ra
        giống hệt tờ giấy ngày xưa từng điểm ảnh — bộ vẽ và CSS đổi được. Muốn
        thế phải lưu bản PDF đã kết xuất; việc riêng, chưa làm.)

        Lý do · người sửa · lúc nào nằm ở `visit_amendment`, KHÔNG chép sang
        `result_correction`. Hai chỗ giữ cùng một sự thật là hai chỗ để lệch.
        """
        if not visit_id:
            raise ValidationError("Phiếu không gắn với lượt khám nào.")

        # `hoan_tat` đã chặn trường hợp rỗng; giữ lại phép tính ở đây vì
        # `corrected_fields` là cột NOT NULL có CHECK khác rỗng ở Postgres.
        doi = _da_doi_gi(anh_cu, anh_moi)
        amendment_id = await conn.fetchval(
            "INSERT INTO visit_amendment"
            " (clinic_id, visit_id, amended_by, amended_at, reason,"
            "  corrected_fields, original_values, corrected_values)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, now(), $4, $5::text[],"
            "         $6::jsonb, $7::jsonb)"
            " RETURNING amendment_id::text",
            identity.clinic_id,
            visit_id,
            identity.staff_id,
            ly_do,
            doi,
            json.dumps(anh_cu, ensure_ascii=False, default=str),
            json.dumps(anh_moi, ensure_ascii=False, default=str),  # lưới an toàn
        )

        # Số bản kế tiếp. Postgres kiểm lại trong trigger (liền mạch) và chặn
        # hai người cùng lúc bằng khoá duy nhất — ở đây chỉ tính để ghi.
        ban_thu = int(
            await conn.fetchval(
                "SELECT 2 + count(*) FROM result_correction"
                " WHERE clinic_id = $1::uuid AND form_instance_id = $2::uuid",
                identity.clinic_id,
                phieu_id,
            )
        )
        await conn.execute(
            "INSERT INTO result_correction"
            " (clinic_id, form_instance_id, visit_id, ban_thu, amendment_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5::uuid)",
            identity.clinic_id,
            phieu_id,
            visit_id,
            ban_thu,
            amendment_id,
        )
        return ban_thu

    async def huy_sua(
        self, *, phieu_id: str, identity: StaffIdentity, expected_revision: int
    ) -> dict[str, Any]:
        """`DiscardFormCorrection` — bỏ bản sửa đang gõ dở.

        KHÔNG có đường này thì bấm [Sửa lại] rồi đổi ý là phiếu kẹt ở chế độ
        sửa mãi, và màn hình nói với mọi người rằng kết quả đang được sửa trong
        khi không ai sửa gì.

        Bản chính thức KHÔNG đổi một chữ. Không có `visit_amendment`, không có
        `result_correction`, không phát `result.corrected` — chưa có sửa chữa
        chuyên môn nào được xác nhận thì không có gì để ghi vào lịch sử y khoa.

        ĐÒI ĐÚNG SỐ ĐANG THẤY, y như [Lưu] và [Xác nhận sửa]. Bản nháp là của
        CHUNG: người thứ hai cầm màn hình cũ mà bấm [Huỷ sửa] sẽ xoá luôn những
        gì người đầu vừa gõ. Hai lệnh kia đã chống ghi đè bằng revision, còn
        lệnh PHÁ HUỶ thì chưa — đúng chỗ cần nó nhất.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_DIEN)
            dong = await conn.fetchrow(
                "SELECT dang_sua, revision FROM form_instance"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
                identity.clinic_id,
                phieu_id,
            )
            if dong is None:
                raise ValidationError("Không tìm thấy phiếu này.")
            if not dong["dang_sua"]:
                # Bấm hai lần, hoặc người khác vừa huỷ: không phải lỗi.
                return {"ok": True, "dang_sua": False, "revision": dong["revision"]}
            if dong["revision"] != expected_revision:
                raise ValidationError(
                    "Bản sửa vừa được người khác gõ tiếp — tải lại rồi hãy huỷ."
                )
            moi = await conn.fetchval(
                "UPDATE form_instance"
                "   SET dang_sua = false, du_lieu_dang_sua = NULL,"
                "       nhap_boi_dang_sua = NULL, thuc_hien_boi_dang_sua = NULL,"
                "       revision = revision + 1, sua_luc = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid RETURNING revision",
                identity.clinic_id,
                phieu_id,
            )
        return {"ok": True, "dang_sua": False, "revision": int(moi)}

    @staticmethod
    async def _result_mode(
        conn: asyncpg.Connection, clinic_id: str, service_order_id: str
    ) -> str:
        """Dịch vụ này có sinh kết quả ngay tại phòng không.

        Chưa cấu hình → `INLINE` (đổi 23/09/2026 khuya). Trước đây là `NONE`
        ("im lặng là không có kết quả"), khi phòng chỉ điền được mẫu ĐÃ GẮN.
        Từ khi phòng mở mẫu gợi ý của phiếu v5 cho dịch vụ chưa gắn, một phiếu
        kết quả đã Hoàn tất LÀ có kết quả để đọc — bấm thật: phòng siêu âm
        hoàn tất phiếu mà bác sĩ chính không được báo. Muốn im lặng / báo sau
        thì quản lý cấu hình rõ `NONE` / `LATER` khi gắn mẫu.
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
        return str(mode) if mode else "INLINE"

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
    async def doc_bieu_mau(
        self, *, form_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Khung ĐANG DÙNG của một mẫu — cho màn sửa mẫu (27/09/2026).

        Ai sửa được hoặc xuất bản được mẫu thì đọc được; `version` gửi lại khi
        xuất bản để không đè lên bản người khác vừa xuất bản.
        """
        async with self._pool.acquire() as conn:
            if not (
                await can(conn, identity, QUYEN_SUA_MAU)
                or await can(conn, identity, QUYEN_XUAT_BAN)
            ):
                raise SafetyGateError("Bạn không có quyền sửa biểu mẫu.")
            r = await conn.fetchrow(
                "SELECT form_id, version, ten, nhom, khung, xuat_ban_luc"
                "  FROM form_definition"
                " WHERE clinic_id = $1::uuid AND form_id = $2"
                "   AND trang_thai = 'PUBLISHED'",
                identity.clinic_id,
                form_id,
            )
            if r is None:
                raise ValidationError(f"Chưa có biểu mẫu “{form_id}”.")
            so_phieu = await conn.fetchval(
                "SELECT count(*) FROM form_instance"
                " WHERE clinic_id = $1::uuid AND form_id = $2",
                identity.clinic_id,
                form_id,
            )
        return {
            "form_id": r["form_id"],
            "version": r["version"],
            "ten": r["ten"],
            "nhom": r["nhom"],
            "khung": json.loads(r["khung"]),
            "xuat_ban_luc": r["xuat_ban_luc"].isoformat()
            if r["xuat_ban_luc"]
            else None,
            # Phiếu đã điền (mọi bản) — màn nói rõ "N phiếu cũ giữ bản cũ".
            "so_phieu_da_dien": int(so_phieu),
        }

    async def xuat_ban(
        self,
        *,
        form_id: str,
        khung: list[dict[str, Any]],
        identity: StaffIdentity,
        expected_version: int | None = None,
        ten: str | None = None,
    ) -> dict[str, Any]:
        """`PublishFormVersion` — bản mới thành bản đang dùng, bản cũ về hưu.

        Phiếu đã điền KHÔNG đổi: chúng ghim phiên bản của chúng.

        27/09/2026 (màn sửa mẫu): khung được KIỂM (`kiem_khung_mau`) trước khi
        ghi; khoá dòng mẫu nên hai người xuất bản cùng lúc chạy nối tiếp, và
        `expected_version` lệch thì 409 — không lặng lẽ đè bản người kia vừa
        xuất bản. `ten` đổi tên mẫu (cả danh mục `ket_qua_mau` nếu là mẫu KQ).
        """
        ten_moi = (ten or "").strip() or None
        async with self._pool.acquire() as conn, conn.transaction():
            # Quyền TRƯỚC khung: người không có quyền không nhận được lời chỉ
            # dẫn sửa khung cho đúng.
            await doi_quyen(conn, identity, QUYEN_XUAT_BAN)
            # Luật khung chỉ cho MẪU KẾT QUẢ (`KQ_*`). Hàm này còn xuất bản bảy
            # phiếu khám (NT, PK…) — khung của chúng khác hẳn (`lien_ket`, nhóm,
            # bảng hàng×cột) và có luật riêng ở `phieu_kham/khung.py`.
            if form_id.startswith("KQ_"):
                khung = kiem_khung_mau(khung)
            else:
                # Nạp muộn: `phieu_kham.khung` nhập NGUON từ tệp này.
                from clinicai.phieu_kham.khung import kiem_khung, la_phieu_kham

                if la_phieu_kham(form_id):
                    kiem_khung(khung, form_id=form_id)
            if ten_moi is not None and len(ten_moi) > 200:
                raise ValidationError("Tên mẫu dài quá 200 ký tự.")
            # Khoá theo MẪU trước khi đọc bản mới nhất. `FOR UPDATE` trên dòng
            # bản mới nhất không đủ: người đến sau chờ xong vẫn thấy đúng dòng
            # cũ (bản N), qua kiểm rồi chèn N+1 trùng khoá chính → 500.
            await conn.execute(
                "SELECT pg_advisory_xact_lock("
                "hashtext('bieu_mau:' || $1 || ':' || $2))",
                identity.clinic_id,
                form_id,
            )
            hien = await conn.fetchrow(
                "SELECT version, ten, nhom FROM form_definition"
                " WHERE clinic_id = $1::uuid AND form_id = $2"
                " ORDER BY version DESC LIMIT 1",
                identity.clinic_id,
                form_id,
            )
            if hien is None:
                raise ValidationError(f"Chưa có biểu mẫu “{form_id}”.")
            if expected_version is not None and int(hien["version"]) != int(
                expected_version
            ):
                raise ConflictError(
                    f"Mẫu vừa được xuất bản bản {hien['version']} trong lúc bạn "
                    "sửa — tải lại để xem bản mới rồi sửa tiếp."
                )

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
                ten_moi or hien["ten"],
                hien["nhom"],
                json.dumps(khung, ensure_ascii=False),
                identity.staff_id,
            )
            if ten_moi and form_id.startswith("KQ_"):
                # Danh mục mẫu (chọn mẫu ở phòng, gắn mẫu) đọc tên ở đây.
                await conn.execute(
                    "UPDATE ket_qua_mau SET ten = $3, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND ma = $2",
                    identity.clinic_id,
                    form_id.removeprefix("KQ_"),
                    ten_moi,
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
        # ĐANG SỬA thì màn điền phải thấy BẢN NHÁP, không thấy bản chính thức:
        # người thứ hai mở ra sửa phải nối tiếp cái người đầu vừa gõ, chứ không
        # bắt đầu lại từ bản cũ.
        #
        # Còn ai ĐỌC KẾT QUẢ ở nơi khác vẫn đọc `du_lieu` — bản chính thức không
        # đổi cho tới lúc [Xác nhận sửa].
        du_lieu = json.loads(
            dong["du_lieu_dang_sua"]
            if dong["dang_sua"] and dong["du_lieu_dang_sua"]
            else dong["du_lieu"]
        )
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
            # Màn sửa phải nhận lại lựa chọn "người thực hiện" của chính bản
            # đang sửa; tải lại trang mà mất lựa chọn ấy thì tự lưu mới lưu nửa
            # cái phiếu.
            "thuc_hien_boi": str(
                dong["thuc_hien_boi_dang_sua"]
                if dong["dang_sua"] and dong["thuc_hien_boi_dang_sua"]
                else dong["thuc_hien_boi"] or ""
            )
            or None,
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


def _gio_iso(gio: Any) -> str | None:
    """Mốc thời gian trong ảnh chụp luôn là ISO-8601, không phải `str(datetime)`.

    `str()` cho ra `2026-09-23 05:06:32+00:00` — dấu cách thay chữ T. Đọc lại
    được, nhưng không phải chuẩn, và ảnh chụp này còn phải mở ra sau nhiều năm.
    """
    return gio.isoformat() if hasattr(gio, "isoformat") else (gio or None)


def _anh_phien_ban(
    dong: asyncpg.Record,
    *,
    du_lieu: dict[str, Any],
    nhap_theo_nhap: bool,
    hoan_tat_boi: str | None = None,
    thuc_hien_boi: str | None = None,
) -> dict[str, Any]:
    """Một phiên bản kết quả TRỌN VẸN: nội dung + ai đã làm.

    `nhap_theo_nhap=True` dựng ảnh của bản SẮP thành chính thức, nên lấy người
    gõ và người thực hiện từ các cột nháp. `False` dựng ảnh của bản ĐANG là
    chính thức.
    """
    if nhap_theo_nhap:
        nguoi_nhap = dong["nhap_boi_dang_sua"] or dong["nhap_boi"]
        nguoi_lam = (
            thuc_hien_boi or dong["thuc_hien_boi_dang_sua"] or dong["thuc_hien_boi"]
        )
        chot_boi: Any = hoan_tat_boi
        chot_luc: Any = None
    else:
        nguoi_nhap = dong["nhap_boi"]
        nguoi_lam = dong["thuc_hien_boi"]
        chot_boi = dong["hoan_tat_boi"]
        chot_luc = _gio_iso(dong["hoan_tat_luc"])
    return {
        "du_lieu": du_lieu,
        "nhap_boi": str(nguoi_nhap) if nguoi_nhap else None,
        "thuc_hien_boi": str(nguoi_lam) if nguoi_lam else None,
        "hoan_tat_boi": str(chot_boi) if chot_boi else None,
        "hoan_tat_luc": chot_luc,
    }


def _o_da_doi(ban_cu: dict[str, Any], ban_moi: dict[str, Any]) -> list[str]:
    """Những ô thật sự đổi giá trị. So GIÁ TRỊ, không so cả object.

    Nguồn của một ô đổi từ TEMPLATE_DEFAULT sang USER mà chữ y nguyên thì đó
    không phải một sửa chữa chuyên môn — không có gì để ghi vào lịch sử y khoa.
    """
    return sorted(
        k
        for k in set(ban_cu) | set(ban_moi)
        if ban_cu.get(k, {}).get("gia_tri") != ban_moi.get(k, {}).get("gia_tri")
    )


def _da_doi_gi(anh_cu: dict[str, Any], anh_moi: dict[str, Any]) -> list[str]:
    """Cái gì đã đổi giữa hai phiên bản — nội dung VÀ người thực hiện.

    KHÔNG tính `nhap_boi`: người khác ngồi gõ không làm kết quả khác đi. Tính
    `thuc_hien_boi`: đổi "ai làm siêu âm này" là sửa dữ liệu nghiệp vụ, kể cả
    khi không một chữ nào trong phiếu đổi.
    """
    doi = _o_da_doi(anh_cu.get("du_lieu", {}), anh_moi.get("du_lieu", {}))
    if anh_cu.get("thuc_hien_boi") != anh_moi.get("thuc_hien_boi"):
        doi.append("thuc_hien_boi")
    return doi


def _con_trong(khung: list[dict[str, Any]], du_lieu: dict[str, Any]) -> list[str]:
    """Đếm ô chưa điền để NHẮC, không để chặn."""
    trong = []
    for muc in khung:
        for block in muc.get("block", []):
            o = du_lieu.get(block["ma"])
            g = None if o is None else o.get("gia_tri")
            # Ô mục BẢNG (mẫu v3): {ma_cột: giá trị} — trống khi mọi cột trống.
            if isinstance(g, dict):
                g = [v for v in g.values() if v not in (None, "")]
            if g in (None, "", []):
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
