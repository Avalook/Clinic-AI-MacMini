"""Hẹn tái khám trên phiếu → MỘT việc CSKH bám theo lượt (Tuyền chốt 29/09/2026).

Bác sĩ chỉ đặt NGÀY tái khám (khối "Hẹn khám", ô `*_follow_date`) — không đặt
giờ, vì hôm đó có thể đổi lịch. Việc của hệ thống:

* TRƯỚC NGÀY HẸN 7 NGÀY khách ấy có một việc cho CSKH ("hẹn tái khám dd/mm —
  cần gọi chốt giờ"): hiện ở khung khách màn Quản lý khách hàng, ở màn Nhắc tái
  khám, và CHUÔNG trong app cho người có lego CSKH (vai CSKH).
* Việc ghi đủ để gọi: ngày hẹn, bác sĩ chỉ định, loại khám + chẩn đoán lần
  trước, các mục "Cần kiểm tra lại khi tái khám", ghi chú của bác sĩ. Các thứ ấy
  ĐỌC TỪ PHIẾU lúc hiện (`chi_tiet_viec`) — không chép ra chỗ khác, nên bác sĩ
  sửa chẩn đoán hay ghi chú lúc nào thì việc nói đúng lúc ấy.
* Sửa / xoá ngày MỌI LÚC (kể cả sau Hoàn tất) → việc bám theo: upsert theo lượt
  (khoá `uq_nhac_tai_kham_mot_viec_mo_theo_luot`, mig 20260929950000), xoá ngày
  → đóng việc "Bác sĩ bỏ hẹn tái khám". Mỗi lần đổi ghi `event_log`
  (`nhac_tai_kham.hen_doi`: ai, lúc nào, từ → tới).
* Khách đã có lịch hẹn từ hạn gọi trở đi → việc đóng "đã có lịch", không bắt
  gọi (trigger `nhac_tai_kham_dong_khi_co_lich` lo các lịch đặt SAU; hàm này lo
  lịch đã có TRƯỚC khi bác sĩ đặt ngày).

Hàm `dong_bo` chạy TRONG giao dịch lưu phiếu (luật hẹn giờ: hẹn ghi cùng giao
dịch với việc sinh ra nó). Ngày rác → coi như không có ngày, không ném.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.events.hen_gio import hen, huy_hen
from clinicai.phieu_kham.khung import cac_o, dinh_nghia, doc_ngay
from clinicai.phieu_kham.mang_sang import doc_chan_doan

#: Loại hẹn giờ: tới hạn gọi thì réo chuông CSKH (xử lý ở
#: `events/consumers/nhac_tai_kham.py`).
HEN_NHAC_TAI_KHAM = "nhac_tai_kham.den_han"
#: "Trước ngày hẹn 7 ngày" (Tuyền 29/09/2026; cùng cửa sổ lượt 1 từ 07/08).
SO_NGAY_TRUOC = 7
#: Giờ réo chuông trong ngày hạn gọi — đầu buổi làm việc, không nửa đêm.
GIO_BAO = time(7, 0)
#: Nguồn chuông trong `thong_bao` (khoá chống trùng theo việc + ngày hẹn).
NGUON_CHUONG = "nhac_tai_kham"
#: Mã nhật ký mỗi lần ngày hẹn đổi (nhãn ở `audit_labels`).
SU_KIEN_HEN_DOI = "nhac_tai_kham.hen_doi"

_DUOI_NGAY = "_follow_date"
_DUOI_KIEM_TRA = "_follow_tests"
_DUOI_GHI_CHU = "_follow_note"

#: dong_vi → câu cho người đọc (cột `ghi_chu` của việc).
LY_DO_DONG: dict[str, str] = {
    "DA_CO_LICH": "Khách đã có lịch hẹn",
    "BS_BO_HEN": "Bác sĩ bỏ hẹn tái khám",
    "BS_DOI_NGAY": "Bác sĩ đã đổi ngày hẹn",
    "TRUNG_VIEC": "Trùng việc gọi đã có cho cùng ngày",
    "NGAY_DA_QUA": "Ngày hẹn đã qua",
}

_LICH_SONG = ("SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN")


# ---------------------------------------------------------------------------
# Hàm thuần — test không cần database
# ---------------------------------------------------------------------------
def la_o_ngay_hen(ma: str) -> bool:
    """Ô "Ngày tái khám" của mọi phiếu — cùng quy ước bộ quét SQL."""
    return ma.endswith(_DUOI_NGAY)


def doc_ngay_hen(o: Any) -> date | None:
    """Giá trị ô ngày hẹn (`{gia_tri}` hoặc chuỗi) → ngày. Rác → None, không ném."""
    gia = o.get("gia_tri") if isinstance(o, Mapping) else o
    return doc_ngay(gia) if isinstance(gia, str) else None


def han_goi(ngay_hen: date, hom_nay: date) -> date:
    """Ngày phải gọi = ngày hẹn − 7. Hẹn gần hơn 7 ngày thì gọi từ HÔM NAY —
    việc vừa sinh không được đỏ "quá hạn" ngay lúc bác sĩ vừa gõ ngày."""
    return max(ngay_hen - timedelta(days=SO_NGAY_TRUOC), hom_nay)


def cho_toi_luc_bao(han: date, bay_gio: datetime) -> timedelta:
    """Bao lâu nữa réo chuông: 07:00 giờ VN của ngày hạn; đã qua → ngay."""
    moc = datetime.combine(han, GIO_BAO, tzinfo=CLINIC_TZ)
    return max(moc - bay_gio, timedelta(0))


def ngay_hen_cua_luot(
    phieu: Sequence[tuple[str, Mapping[str, Any]]],
) -> tuple[date | None, str | None]:
    """(ngày hẹn, form_id) từ các phiếu của lượt — ngày hợp lệ MUỘN nhất (cùng
    luật `max()` của bộ quét SQL). Không phiếu nào có ngày → (None, None)."""
    tot: tuple[date | None, str | None] = (None, None)
    for form_id, du_lieu in phieu:
        for ma, o in du_lieu.items():
            if not la_o_ngay_hen(ma):
                continue
            d = doc_ngay_hen(o)
            if d is not None and (tot[0] is None or d > tot[0]):
                tot = (d, form_id)
    return tot


def ten_can_kiem_tra(form_id: str | None, du_lieu: Mapping[str, Any]) -> list[str]:
    """Các mục "Cần kiểm tra lại khi tái khám" đã tick → TÊN theo khung phiếu.
    Mã lạ / phiếu lạ → bỏ qua, không ném."""
    if not form_id:
        return []
    try:
        o_khung = cac_o(dinh_nghia(form_id)["khung"])
    except Exception:  # noqa: BLE001 — phiếu lạ thì không có tên để dịch
        return []
    ra: list[str] = []
    for ma, o in du_lieu.items():
        if not ma.endswith(_DUOI_KIEM_TRA):
            continue
        gia = o.get("gia_tri") if isinstance(o, Mapping) else None
        if not isinstance(gia, list):
            continue
        ten = {c["ma"]: c["ten"] for c in o_khung.get(ma, {}).get("lua_chon", [])}
        ra.extend(ten[m] for m in gia if isinstance(m, str) and m in ten)
    return ra


def ghi_chu_hen(du_lieu: Mapping[str, Any]) -> str | None:
    for ma, o in du_lieu.items():
        if ma.endswith(_DUOI_GHI_CHU):
            gia = o.get("gia_tri") if isinstance(o, Mapping) else None
            if isinstance(gia, str) and gia.strip():
                return gia.strip()
    return None


def tinh_trang(
    trang_thai: str, dong_vi: str | None, han: date | None, hom_nay: date
) -> str:
    """Mã tình trạng cho màn (nhãn là việc của màn, luật ở đây)."""
    if trang_thai == "CHO_GOI":
        return "CHUA_TOI_HAN" if han is not None and han > hom_nay else "CHO_GOI"
    if trang_thai == "DA_GOI":
        return "DA_GOI"
    if dong_vi == "DA_CO_LICH":
        return "DA_CO_LICH"
    if dong_vi == "BS_BO_HEN":
        return "DA_HUY"
    return "KHONG_CAN"


# ---------------------------------------------------------------------------
# Đọc
# ---------------------------------------------------------------------------
def _dl(v: Any) -> dict[str, Any]:
    if isinstance(v, str):
        v = json.loads(v)
    return v if isinstance(v, dict) else {}


async def _phieu_cua_luot(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> list[tuple[str, dict[str, Any]]]:
    rows = await conn.fetch(
        "SELECT form_id, du_lieu FROM phieu_kham_luot"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid ORDER BY sua_luc DESC",
        clinic_id,
        visit_id,
    )
    return [(r["form_id"], _dl(r["du_lieu"])) for r in rows]


async def doc_hen_luot(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    """Ngày hẹn + mục cần kiểm tra + ghi chú bác sĩ — đọc từ phiếu của lượt."""
    phieu = await _phieu_cua_luot(conn, clinic_id, visit_id)
    ngay, form_id = ngay_hen_cua_luot(phieu)
    du_lieu = next((d for f, d in phieu if f == form_id), phieu[0][1] if phieu else {})
    return {
        "ngay_hen": ngay,
        "form_id": form_id,
        "can_kiem_tra": ten_can_kiem_tra(
            form_id or (phieu[0][0] if phieu else None), du_lieu
        ),
        "ghi_chu_bac_si": ghi_chu_hen(du_lieu),
    }


async def chi_tiet_viec(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str | None
) -> dict[str, Any] | None:
    """Đủ để CSKH gọi: bác sĩ chỉ định, loại khám + ngày khám lần trước, chẩn
    đoán lần trước, mục cần kiểm tra lại, ghi chú bác sĩ. Lượt không còn → None."""
    if not visit_id:
        return None
    v = await conn.fetchrow(
        """
        SELECT st.name AS loai_kham,
               (coalesce(v.checked_in_at, v.created_at)
                  AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay_kham,
               coalesce(d.full_name, (
                   SELECT s.full_name FROM consultation c
                     JOIN staff s ON s.id = c.doctor_staff_id
                    WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id
                      AND c.kind = 'PRIMARY'
                    ORDER BY c.round_no LIMIT 1)) AS bac_si
          FROM visit v
          LEFT JOIN service_type st ON st.id = v.service_type_id
          LEFT JOIN staff d ON d.id = v.attending_doctor_id
         WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
        """,
        clinic_id,
        visit_id,
    )
    if v is None:
        return None
    hen_luot = await doc_hen_luot(conn, clinic_id, visit_id)
    return {
        "visit_id": visit_id,
        "bac_si": v["bac_si"],
        "loai_kham": v["loai_kham"],
        "ngay_kham": v["ngay_kham"].isoformat() if v["ngay_kham"] else None,
        "chan_doan": await doc_chan_doan(conn, clinic_id=clinic_id, visit_id=visit_id),
        "can_kiem_tra": hen_luot["can_kiem_tra"],
        "ghi_chu_bac_si": hen_luot["ghi_chu_bac_si"],
    }


# ---------------------------------------------------------------------------
# Ghi — chạy TRONG giao dịch lưu phiếu
# ---------------------------------------------------------------------------
async def _dong(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    viec_id: str,
    dong_vi: str,
) -> None:
    await conn.execute(
        "UPDATE nhac_tai_kham SET trang_thai = 'KHONG_CAN', dong_vi = $2,"
        " ghi_chu = $3, dong_luc = now(), updated_at = now()"
        " WHERE id = $1::uuid AND trang_thai = 'CHO_GOI'",
        viec_id,
        dong_vi,
        LY_DO_DONG[dong_vi],
    )
    await huy_hen(
        conn, clinic_id=identity.clinic_id, loai=HEN_NHAC_TAI_KHAM, ve_cai_gi=viec_id
    )
    await _dong_chuong(conn, identity, viec_id, giu_ngay=None)


async def _dong_chuong(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    viec_id: str,
    *,
    giu_ngay: date | None,
) -> None:
    """Chuông của việc cho ngày CŨ (hoặc mọi ngày) → đã xử lý: chuông không
    được nói một ngày hẹn bác sĩ đã bỏ."""
    await conn.execute(
        "UPDATE thong_bao SET da_xu_ly_luc = now(), da_xu_ly_boi = $3::uuid,"
        "       ghi_chu_xu_ly = 'Bác sĩ đã đổi / bỏ hẹn tái khám',"
        "       da_doc_luc = coalesce(da_doc_luc, now())"
        " WHERE clinic_id = $1::uuid AND nguon = $4"
        "   AND nguon_id LIKE $2 || ':%' AND da_xu_ly_luc IS NULL"
        "   AND ($5::text IS NULL OR nguon_id <> $2 || ':' || $5)",
        identity.clinic_id,
        viec_id,
        identity.staff_id,
        NGUON_CHUONG,
        giu_ngay.isoformat() if giu_ngay else None,
    )


async def _ghi_lich_su(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    visit_id: str,
    viec_id: str | None,
    tu: date | None,
    toi: date | None,
    ket_qua: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, event_published)
        VALUES ($1::uuid, $2, 'visit', $3::uuid, $4::jsonb, $5::jsonb,
                'api:phieu-kham', FALSE)
        """,
        identity.clinic_id,
        SU_KIEN_HEN_DOI,
        visit_id,
        json.dumps(
            {
                "visit_id": visit_id,
                "viec_id": viec_id,
                "tu": tu.isoformat() if tu else None,
                "toi": toi.isoformat() if toi else None,
                "ket_qua": ket_qua,
            }
        ),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "vai_tai_khoan": identity.vai_goc.value,
                "clinic_staff_id": identity.staff_id,
                "actor_auth_user_id": identity.auth_user_id,
                "origin": "api:phieu-kham",
            }
        ),
    )


async def dong_bo(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    visit_id: str,
    hom_nay: date,
    bay_gio: datetime,
) -> dict[str, Any]:
    """Cho việc gọi của lượt khớp ngày hẹn ĐANG CÓ trên phiếu. Chạy lại bao
    nhiêu lần cũng như một. Trả tình trạng để màn phiếu nói ra."""
    cid = identity.clinic_id
    pid = await conn.fetchval(
        "SELECT clinic_patient_id::text FROM visit"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
        cid,
        visit_id,
    )
    if pid is None:
        return {"trang_thai": "KHONG_HEN"}
    ngay = (await doc_hen_luot(conn, cid, visit_id))["ngay_hen"]

    cua_luot = await conn.fetch(
        "SELECT id::text, ngay_hen, trang_thai FROM nhac_tai_kham"
        " WHERE clinic_id = $1::uuid AND nguon_visit_id = $2::uuid"
        "   AND nguon = 'PHIEU_KHAM' AND luot_goi = 1"
        " ORDER BY (trang_thai = 'CHO_GOI') DESC, updated_at DESC FOR UPDATE",
        cid,
        visit_id,
    )
    mo = [r for r in cua_luot if r["trang_thai"] == "CHO_GOI"]
    ngay_cu: date | None = mo[0]["ngay_hen"] if mo else None

    # ── Không còn ngày (hoặc ngày đã qua) → đóng việc đang chờ ──────────────
    if ngay is None or ngay < hom_nay:
        ly = "BS_BO_HEN" if ngay is None else "NGAY_DA_QUA"
        for r in mo:
            await _dong(conn, identity, r["id"], ly)
        if mo:
            await _ghi_lich_su(
                conn,
                identity,
                visit_id=visit_id,
                viec_id=mo[0]["id"],
                tu=ngay_cu,
                toi=ngay,
                ket_qua=ly,
            )
        return {"trang_thai": "KHONG_HEN", "ngay_hen": None}

    # Việc này đã đúng ngày và đang chờ → không đổi gì (tự lưu gõ lại cùng ngày).
    if mo and ngay_cu == ngay:
        return {
            "trang_thai": "CHO_GOI",
            "viec_id": mo[0]["id"],
            "ngay_hen": ngay.isoformat(),
        }

    han = han_goi(ngay, hom_nay)
    # Một lượt = một việc: dùng lại việc cùng ngày, rồi việc đang chờ, rồi việc
    # gần nhất của lượt (kể cả đã đóng) — không đẻ dòng mới khi đã có dòng.
    dich = next((r for r in cua_luot if r["ngay_hen"] == ngay), None)
    if dich is None:
        dich = mo[0] if mo else (cua_luot[0] if cua_luot else None)

    # Cùng khách, cùng ngày, lượt 1 đã có một việc KHÁC (CSKH tự nhập, hoặc
    # lượt khác) — khoá uq_nhac_tai_kham_viec chỉ cho một. Việc ĐANG MỞ của
    # người khác thì nhường nó; việc phiếu-khám đã đóng thì nhận về lượt này.
    ids = [r["id"] for r in cua_luot]
    khac = await conn.fetchrow(
        "SELECT id::text, nguon, trang_thai FROM nhac_tai_kham"
        " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid"
        "   AND ngay_hen = $3::date AND luot_goi = 1"
        "   AND NOT (id = ANY($4::uuid[])) FOR UPDATE",
        cid,
        pid,
        ngay,
        ids,
    )
    if khac is not None and not (
        khac["nguon"] == "PHIEU_KHAM" and khac["trang_thai"] != "CHO_GOI"
    ):
        for r in mo:
            await _dong(conn, identity, r["id"], "TRUNG_VIEC")
        await _ghi_lich_su(
            conn,
            identity,
            visit_id=visit_id,
            viec_id=khac["id"],
            tu=ngay_cu,
            toi=ngay,
            ket_qua="TRUNG_VIEC",
        )
        return {
            "trang_thai": "TRUNG_VIEC",
            "viec_id": khac["id"],
            "ngay_hen": ngay.isoformat(),
        }

    # Đóng mọi việc đang chờ KHÁC của lượt trước (khoá một-việc-mở-mỗi-lượt).
    giu = khac["id"] if khac is not None else (dich["id"] if dich else None)
    for r in mo:
        if r["id"] != giu:
            await _dong(conn, identity, r["id"], "BS_DOI_NGAY")

    lich = await conn.fetchval(
        "SELECT id::text FROM appointment"
        " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid"
        "   AND status = ANY($3::text[])"
        "   AND (slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date >= $4::date"
        " ORDER BY slot_start LIMIT 1",
        cid,
        pid,
        list(_LICH_SONG),
        han,
    )
    dong_vi = "DA_CO_LICH" if lich else None
    trang_thai = "KHONG_CAN" if lich else "CHO_GOI"
    gia_tri = (
        ngay,
        han,
        trang_thai,
        dong_vi,
        LY_DO_DONG["DA_CO_LICH"] if lich else None,
        lich,
    )
    if giu is None:
        viec_id = await conn.fetchval(
            """
            INSERT INTO nhac_tai_kham
                (clinic_id, clinic_patient_id, luot_goi, ngay_hen, han_goi,
                 nguon_visit_id, nguon, trang_thai, dong_vi, ghi_chu,
                 appointment_id, dong_luc)
            VALUES ($1::uuid, $2::uuid, 1, $4, $5, $3::uuid, 'PHIEU_KHAM', $6, $7,
                    $8, $9::uuid, CASE WHEN $6 = 'CHO_GOI' THEN NULL ELSE now() END)
            RETURNING id::text
            """,
            cid,
            pid,
            visit_id,
            *gia_tri,
        )
    else:
        viec_id = giu
        # Mở lại cả việc ĐÃ GỌI: ngày mới là một cuộc gọi mới. Cuộc gọi cũ vẫn
        # nằm trong `cskh_log` (sổ tương tác của khách).
        await conn.execute(
            """
            UPDATE nhac_tai_kham
               SET nguon_visit_id = $2::uuid, ngay_hen = $3, han_goi = $4,
                   trang_thai = $5, dong_vi = $6, ghi_chu = $7,
                   appointment_id = $8::uuid,
                   dong_luc = CASE WHEN $5 = 'CHO_GOI' THEN NULL ELSE now() END,
                   ket_qua = NULL, goi_luc = NULL, nguoi_goi_staff_id = NULL,
                   updated_at = now()
             WHERE id = $1::uuid
            """,
            viec_id,
            visit_id,
            *gia_tri,
        )

    await huy_hen(conn, clinic_id=cid, loai=HEN_NHAC_TAI_KHAM, ve_cai_gi=viec_id)
    await _dong_chuong(conn, identity, viec_id, giu_ngay=None if lich else ngay)
    if not lich:
        await hen(
            conn,
            clinic_id=cid,
            loai=HEN_NHAC_TAI_KHAM,
            sau=cho_toi_luc_bao(han, bay_gio),
            ve_cai_gi=viec_id,
            correlation_id=visit_id,
            chi_tiet={"nguoi_goi": identity.staff_id, "ngay_hen": ngay.isoformat()},
        )
    await _ghi_lich_su(
        conn,
        identity,
        visit_id=visit_id,
        viec_id=viec_id,
        tu=ngay_cu,
        toi=ngay,
        ket_qua="DA_CO_LICH" if lich else "CHO_GOI",
    )
    return {
        "trang_thai": "DA_CO_LICH" if lich else "CHO_GOI",
        "viec_id": viec_id,
        "ngay_hen": ngay.isoformat(),
        "han_goi": han.isoformat(),
    }


__all__ = [
    "GIO_BAO",
    "HEN_NHAC_TAI_KHAM",
    "LY_DO_DONG",
    "NGUON_CHUONG",
    "SO_NGAY_TRUOC",
    "SU_KIEN_HEN_DOI",
    "chi_tiet_viec",
    "cho_toi_luc_bao",
    "doc_hen_luot",
    "doc_ngay_hen",
    "dong_bo",
    "ghi_chu_hen",
    "han_goi",
    "la_o_ngay_hen",
    "ngay_hen_cua_luot",
    "ten_can_kiem_tra",
    "tinh_trang",
]
