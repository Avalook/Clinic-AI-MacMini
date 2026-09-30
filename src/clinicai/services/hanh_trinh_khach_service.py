"""HÀNH TRÌNH KHÁCH — một khung cho mọi màn (Tuyền chốt 29/09/2026).

Hai dạng của CÙNG một dữ liệu:

* **gọn** (mỗi khách một dòng — trang chủ, bảng Hành trình, Xem lượt): "Đang ở /
  Đang chờ / Đã về" + TÊN PHÒNG THẬT + từ lúc nào + STT, thanh đoạn màu (xong /
  đang làm / đang chờ / chờ kết quả đối tác / chưa tới), đếm dịch vụ xong, còn
  chờ ở đâu.
* **đầy đủ** (popup): ĐANG Ở + TIẾP THEO (phòng kế, STT, số người chờ) và dòng
  thời gian dọc Check-in → Sinh hiệu → (Tư vấn) → Khám bác sĩ chính → Làm dịch
  vụ song song (mỗi chỉ định một thẻ) → Quay lại bác sĩ → Thuốc → Check-out; mỗi
  bước có giờ VÀO HÀNG / BẮT ĐẦU / XONG khi có dữ liệu.

CHỈ ĐỌC, KHÔNG LUẬT THỨ HAI, KHÔNG BẢNG MỚI. Mốc thời gian đọc đúng hàm của dải
mốc phiếu khám (`phieu_kham.hanh_trinh.dung_moc` — dựng từ projection
`luot_dong_thoi_gian`); trạng thái từng chỉ định đọc `dung_tung_dich_vu`; chỗ
khách đang đứng đọc `queue_entry` (cùng thứ tự hàng với màn hàng chờ:
`coalesce(eligible_at, created_at)`). Máy chủ chỉ trả THỜI ĐIỂM — số phút chờ /
làm do trình duyệt tính theo đồng hồ (dòng đang chạy phải nhích theo phút).
Thiếu mốc thì để trống, không bịa.

Check-out (`visit.closed_at`) = khách XONG BUỔI (Tuyền 29/09: "ấn checkout là
phải xong"): thanh đoạn tick hết; việc đối tác chờ kết quả vẫn ghi đúng là chờ
kết quả (không giữ khách).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.phieu_kham.hanh_trinh import (
    BO,
    CHO_LAM,
    CHO_THU,
    DA_XONG,
    DANG_LAM,
    _doc_su_kien_chi_dinh,
    dung_moc,
    dung_tung_dich_vu,
)
from clinicai.services.lich_su_phong import lich_su_phong_cua_luot
from clinicai.services.xem_luot_service import goi_duoc

#: Trạng thái một bước / một đoạn thanh (giao diện map sang màu token).
XONG, DANG, CHO, DOI_TAC, CHUA, KHONG = (
    "xong",
    "dang",
    "cho",
    "doi_tac",
    "chua",
    "khong",
)
#: Thẻ dịch vụ: thêm DOI_TAC (đối tác đã nhận mẫu, chờ kết quả — không giữ khách).
DV_DOI_TAC = "DOI_TAC"

#: Trần số lượt một lần hỏi dạng gọn (cùng trần bảng trạng thái trang chủ).
TRAN_LUOT = 300

_HANG_SONG = ("waiting", "called", "serving", "blocked")

# Mốc canh để xếp khi thiếu giờ (datetime.min có múi giờ tràn số khi so sánh).
_SOM = datetime(1970, 1, 1, tzinfo=UTC)
_MUON = datetime(9999, 1, 1, tzinfo=UTC)


def _gio(v: Any) -> datetime | None:
    """Giờ an toàn: không phải datetime (rỗng, chuỗi rác…) → None, KHÔNG ném."""
    return v if isinstance(v, datetime) else None


def _dau(*ds: Any) -> datetime | None:
    xs = [d for d in ds if isinstance(d, datetime)]
    return min(xs) if xs else None


def _cuoi(*ds: Any) -> datetime | None:
    xs = [d for d in ds if isinstance(d, datetime)]
    return max(xs) if xs else None


def doc_ma_luot(chuoi: Any) -> list[str]:
    """`"a,b,c"` → danh sách mã lượt hợp lệ (chữ thường, không trùng, tối đa
    TRAN_LUOT). Mã rác bị bỏ qua — trả danh sách rỗng thay vì ném."""
    if not isinstance(chuoi, str):
        return []
    ra: list[str] = []
    for manh in chuoi.split(","):
        try:
            ma = str(uuid.UUID(manh.strip()))
        except (ValueError, AttributeError):
            continue
        if ma not in ra:
            ra.append(ma)
        if len(ra) >= TRAN_LUOT:
            break
    return ra


def noi_cua_hang(q: dict[str, Any], phong_bac_si: str | None = None) -> str:
    """TÊN PHÒNG THẬT của một chỗ chờ. Hàng bác sĩ không gắn phòng thì lấy phòng
    của bác sĩ ấy theo lịch trực hôm đó; không có lịch thì gọi theo bác sĩ."""
    if q.get("lane") == "TU_VAN":
        return q.get("phong") or "Bàn tư vấn"
    if q.get("lane") == "DOCTOR":
        if q.get("phong"):
            return str(q["phong"])
        if phong_bac_si:
            return phong_bac_si
        return _ban_kham_bs(q["bac_si"]) if q.get("bac_si") else "Bàn khám (BS chính)"
    return q.get("phong") or "Phòng dịch vụ"


#: Tên chỗ GIỮ CHỖ (chưa biết phòng thật) — `noi_cua_hang` và các bước chưa
#: có chỗ chờ. Hiện xám "dự kiến", không phải tên phòng.
_NOI_GIU_CHO = ("Bàn khám", "Phòng dịch vụ")


def noi_la_du_kien(noi: str | None) -> bool:
    """Thuần: chỗ này là chữ giữ chỗ (chưa biết phòng thật)?"""
    return bool(noi) and str(noi).startswith(_NOI_GIU_CHO)


def _vao_truoc(ds_vao: list[datetime], moc: datetime | None) -> datetime | None:
    """Giờ vào hàng GẦN NHẤT mà không muộn hơn `moc` (bắt đầu). Không có → None
    — thà bỏ trống còn hơn in "chờ" âm (29/09/2026: làm lại thì chỗ chờ được
    mở lại, `eligible_at` muộn hơn giờ bắt đầu của lần trước)."""
    if moc is None:
        return max(ds_vao) if ds_vao else None
    truoc = [v for v in ds_vao if v <= moc]
    return max(truoc) if truoc else None


def _cac_lan_lam(
    lan_lam: list[dict[str, Any]], ds_vao: list[datetime], cho_lan_moi: bool
) -> list[dict[str, Any]]:
    """Mỗi LẦN LÀM một dòng: vào hàng / bắt đầu / xong (hoặc dừng). Vào hàng của
    lần k nằm giữa lúc lần trước kết thúc và lúc lần k bắt đầu. `cho_lan_moi`:
    lần trước dừng, đã chuẩn bị làm lại mà chưa bắt đầu → thêm dòng đang chờ."""
    ra: list[dict[str, Any]] = []
    het_truoc: datetime | None = None
    for a in sorted(lan_lam, key=lambda x: int(x.get("attempt_no") or 0)):
        bat = _gio(a.get("started_at"))
        vao = _vao_truoc(
            [v for v in ds_vao if het_truoc is None or v >= het_truoc], bat
        )
        dung = _gio(a.get("interrupted_at"))
        ra.append(
            {
                "so": int(a.get("attempt_no") or len(ra) + 1),
                "trang_thai": a.get("status"),
                "vao": vao,
                "bat_dau": bat,
                "xong": _gio(a.get("completed_at")),
                "dung": dung,
            }
        )
        het_truoc = _gio(a.get("completed_at")) or dung or bat
    if cho_lan_moi and ra:
        sau = [v for v in ds_vao if het_truoc is None or v >= het_truoc]
        ra.append(
            {
                "so": ra[-1]["so"] + 1,
                "trang_thai": "PENDING",
                "vao": max(sau) if sau else None,
                "bat_dau": None,
                "xong": None,
                "dung": None,
            }
        )
    return ra


def _ban_kham_bs(ten: str | None) -> str:
    """ "Bàn khám BS X" — tên đã có chữ "BS" thì không lặp ("BS BS Nam")."""
    if not ten:
        return "Bàn khám"
    t = str(ten).strip()
    return (
        f"Bàn khám {t}"
        if t.upper().startswith(("BS", "BÁC SĨ"))
        else f"Bàn khám BS {t}"
    )


def _the_dich_vu(
    tung: dict[str, Any],
    goc: dict[str, Any],
    hang: dict[str, Any] | None,
    *,
    cac_hang: list[dict[str, Any]] | None = None,
    lan_lam: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Một thẻ trong bước "Làm dịch vụ song song".

    GIỜ THẬT (29/09/2026): `vao` không bao giờ muộn hơn `bat_dau` (không ra số
    phút chờ âm). Làm lại → `lan` liệt kê MỌI lần (lần 1 vẫn giữ), `so_lan`
    đếm; giờ chính của thẻ là của lần mới nhất."""
    tt = tung["trang_thai"]
    lay_mau = None
    if (
        goc.get("ngoai")
        and tt == DANG_LAM
        and goc.get("execution_status") == "COMPLETED"
    ):
        # Đối tác: phòng khám lấy mẫu xong → mẫu ở đối tác, chờ kết quả.
        tt = DV_DOI_TAC
        lay_mau = _gio(goc.get("lam_xong_luc"))
    ds_vao = sorted(
        v
        for v in (
            _gio(q.get("eligible_at")) for q in (cac_hang or ([hang] if hang else []))
        )
        if v is not None
    )
    lan = _cac_lan_lam(
        lan_lam or [],
        ds_vao,
        cho_lan_moi=goc.get("execution_status") == "PENDING"
        and bool(lan_lam)
        and all((a.get("status") == "INTERRUPTED") for a in (lan_lam or [])[-1:]),
    )
    bat_dau = (
        lan[-1]["bat_dau"]
        if lan
        else _gio(tung.get("bat_dau"))
        or (_gio(hang.get("serving_at")) if hang else None)
    )
    return {
        "id": tung.get("id"),
        "ten": tung.get("ten") or "",
        # Việc đối tác lấy mẫu ở phòng khám: "Lấy mẫu → Đối tác".
        "noi": f"{goc['phong']} → Đối tác"
        if goc.get("ngoai") and goc.get("phong")
        else tung["noi"],
        "doi_tac": bool(goc.get("ngoai")),
        "trang_thai": tt,
        # Vào hàng của phòng — lần gần nhất KHÔNG muộn hơn giờ bắt đầu.
        "vao": lan[-1]["vao"] if lan else _vao_truoc(ds_vao, bat_dau),
        "bat_dau": bat_dau,
        "xong": _gio(tung.get("xong")),
        "so_lan": len(lan) if lan else 1,
        # Chỉ trả khi LÀM LẠI (≥ 2 lần) — một lần thì giờ chính đã đủ.
        "lan": lan if len(lan) >= 2 else [],
        "thu": _gio(tung.get("thu")),
        "lay_mau": lay_mau,
        "stt": hang.get("stt") if hang else None,
        "so_truoc": hang.get("so_truoc") if hang else None,
    }


def dung_hanh_trinh_khach(
    *,
    luot: dict[str, Any],
    su_kien: list[tuple[str, datetime, dict[str, Any]]],
    chi_dinh: list[dict[str, Any]],
    hang: list[dict[str, Any]],
    phien: list[dict[str, Any]],
    phong_bac_si: dict[str, str] | None = None,
    ai: dict[str, str] | None = None,
    lan_lam: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Hàm THUẦN — kiểm được không cần DB.

    `luot`: {visit_id, status, checked_in_at, closed_at, dat_luc}.
    `su_kien`: (event_type, occurred_at, chi_tiet) — như `dung_moc`.
    `chi_dinh`: dòng của `_chi_dinh` (phiếu khám).
    `hang`: mọi chỗ chờ của lượt — {id, lane, reason, ref_id, status,
    eligible_at, serving_at, done_at, phong, bac_si, doctor_staff_id, stt,
    so_truoc, so_cho}.
    `phien`: phiên khám — {kind, status, started_at, completed_at, bac_si,
    doctor_staff_id}.
    `phong_bac_si`: doctor_staff_id → tên phòng theo lịch trực.
    `ai`: event_type → tên người làm (check-in, đo, thu tiền).
    """
    phong_bac_si = phong_bac_si or {}
    ai = ai or {}
    lan_lam = lan_lam or {}
    check_in = _gio(luot.get("checked_in_at"))
    ve_luc = _gio(luot.get("closed_at"))
    bo_ve = luot.get("status") == "INCOMPLETE"
    xong_buoi = ve_luc is not None

    moc = {
        m["ma"]: m
        for m in dung_moc(
            dat_lich_luc=_gio(luot.get("dat_luc")),
            check_in_luc=check_in,
            ve_luc=ve_luc,
            su_kien=su_kien,
            chi_dinh=chi_dinh,
        )
    }

    def noi_q(q: dict[str, Any]) -> str:
        return noi_cua_hang(q, phong_bac_si.get(q.get("doctor_staff_id") or ""))

    song = [q for q in hang if q.get("status") in _HANG_SONG]
    theo_ref = {
        str(q.get("ref_id")): q
        for q in sorted(hang, key=lambda x: _gio(x.get("eligible_at")) or _SOM)
        if q.get("reason") == "SERVICE"
    }
    moi_hang_theo_ref: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for q in hang:
        if q.get("reason") == "SERVICE":
            moi_hang_theo_ref[str(q.get("ref_id"))].append(q)

    def hang_cua(reason: str) -> dict[str, Any] | None:
        ds = [q for q in hang if q.get("reason") == reason]
        # Chỗ còn sống trước, rồi chỗ mới nhất.
        ds.sort(
            key=lambda q: (
                q.get("status") in _HANG_SONG,
                _gio(q.get("eligible_at")) or _gio(q.get("created_at")) or _SOM,
            ),
            reverse=True,
        )
        return ds[0] if ds else None

    def phien_cua(kind: str) -> dict[str, Any] | None:
        ds = [p for p in phien if p.get("kind") == kind]
        return ds[-1] if ds else None

    buoc: list[dict[str, Any]] = []

    def them(
        ma: str,
        ten: str,
        trang_thai: str,
        *,
        noi: str = "",
        ai_lam: str | None = None,
        vao: datetime | None = None,
        bat_dau: datetime | None = None,
        xong: datetime | None = None,
        ghi_chu: str | None = None,
        dich_vu: list[dict[str, Any]] | None = None,
        **them_truong: Any,
    ) -> None:
        if xong_buoi and trang_thai in (CHO, CHUA):
            trang_thai = KHONG
        # BƯỚC CHƯA XẢY RA (29/09/2026): chữ giữ chỗ ("Thuốc · nếu có đơn",
        # "đọc kết quả, khi dịch vụ xong", "Bàn khám" chưa biết phòng) là DỰ
        # KIẾN — giao diện hiện xám, KHÔNG BAO GIỜ gắn giờ.
        du_kien = trang_thai == CHUA
        if du_kien:
            vao = bat_dau = xong = None
        buoc.append(
            {
                **them_truong,
                "ma": ma,
                "ten": ten,
                "trang_thai": trang_thai,
                "du_kien": du_kien,
                "noi": noi,
                "noi_du_kien": noi_la_du_kien(noi),
                "ai": ai_lam,
                "vao": vao,
                "bat_dau": bat_dau,
                "xong": xong,
                "ghi_chu": ghi_chu,
                "dich_vu": dich_vu,
            }
        )

    def tt_moc(m: dict[str, Any] | None) -> str:
        if m is None:
            return CHUA
        return {"xong": XONG, "dang": DANG}.get(m["trang_thai"], CHUA)

    # 1. Check-in
    them(
        "CHECK_IN",
        "Check-in",
        XONG if check_in else CHUA,
        noi="Lễ tân",
        ai_lam=ai.get("visit.checked_in"),
        bat_dau=check_in,
        xong=check_in,
    )

    km = moc.get("KHAM")
    p_chinh = phien_cua("PRIMARY")
    q_chinh = hang_cua("PRIMARY")
    bat_kham = (km["bat"] if km else None) or (
        _gio(p_chinh.get("started_at")) if p_chinh else None
    )
    xong_kham = (km["ket"] if km else None) or (
        _gio(p_chinh.get("completed_at")) if p_chinh else None
    )

    # 2. Đo sinh hiệu — chờ tính từ check-in. Chưa đo mà bác sĩ đã khám = bước
    # này không làm (bỏ qua), không treo "đang chờ".
    sh = moc.get("SINH_HIEU")
    tt_sh = tt_moc(sh)
    if tt_sh == CHUA and check_in:
        tt_sh = KHONG if bat_kham else CHO
    lan_do = list(sh.get("lan_do") or []) if sh else []
    them(
        "SINH_HIEU",
        "Đo sinh hiệu",
        tt_sh,
        noi="Đo sinh hiệu",
        # Người đo LẦN 1 (lần đo lại có người riêng ở `lan_do`).
        ai_lam=(lan_do[0].get("ai") if lan_do else None) or ai.get("vitals.recorded"),
        vao=check_in,
        bat_dau=sh["bat"] if sh else None,
        xong=sh["ket"] if sh else None,
        # GIỜ THẬT: xong = lần đo ĐẦU; đo lại ghi dòng riêng, không cộng vào
        # thời gian làm.
        do_lai=list(sh.get("do_lai") or []) if sh else [],
        lan_do=lan_do,
    )

    # 3. Tư vấn (chỉ khi có).
    tv = moc.get("TU_VAN")
    q_tv = hang_cua("TU_VAN")
    if tv or q_tv:
        them(
            "TU_VAN",
            "Tư vấn",
            tt_moc(tv)
            if tv
            else (CHO if q_tv and q_tv.get("status") in _HANG_SONG else CHUA),
            noi=noi_q(q_tv) if q_tv else "Bàn tư vấn",
            vao=_gio(q_tv.get("eligible_at")) if q_tv else None,
            bat_dau=tv["bat"] if tv else None,
            xong=tv["ket"] if tv else None,
        )

    # 4. Khám bác sĩ chính — kèm "chỉ định N dịch vụ · thu tiền HH:MM (ai)".
    # Chỗ chờ khám chính có mốc vào hàng SAU lúc bắt đầu khám = khách đi làm
    # dịch vụ rồi QUAY LẠI trong cùng phiên (không phải thời gian chờ khám).
    vao_q = _gio(q_chinh.get("eligible_at")) if q_chinh else None
    quay_lai_luc = vao_q if (vao_q and bat_kham and vao_q > bat_kham) else None
    vao_kham = None if quay_lai_luc else vao_q
    lam = [o for o in chi_dinh if o.get("chon")]
    thu = moc.get("THU_TIEN")
    bs_chinh = (p_chinh or {}).get("bac_si") or (q_chinh or {}).get("bac_si")
    them(
        "KHAM",
        "Khám bác sĩ chính",
        XONG
        if xong_kham
        else DANG
        if bat_kham
        else CHO
        if q_chinh and q_chinh.get("status") in _HANG_SONG
        else CHUA,
        noi=noi_q(q_chinh)
        if q_chinh
        else (
            phong_bac_si.get((p_chinh or {}).get("doctor_staff_id") or "") or "Bàn khám"
        ),
        ai_lam=bs_chinh,
        vao=vao_kham,
        bat_dau=bat_kham,
        xong=xong_kham,
        so_chi_dinh=len(lam),
        thu_luc=thu["ket"] if thu else None,
        nguoi_thu=ai.get("payment.service_collected") if thu and thu["ket"] else None,
        cho_thu=int(thu.get("con_cho") or 0) if thu else 0,
    )

    # 5. Làm dịch vụ song song — mỗi chỉ định một thẻ.
    goc_theo_id = {str(o.get("id")): o for o in chi_dinh}
    the = [
        _the_dich_vu(
            t,
            goc_theo_id.get(str(t.get("id")), {}),
            theo_ref.get(str(t.get("id"))),
            cac_hang=moi_hang_theo_ref.get(str(t.get("id"))),
            lan_lam=lan_lam.get(str(t.get("id"))),
        )
        for t in dung_tung_dich_vu(chi_dinh)
        if t["trang_thai"] != BO
    ]
    if the:
        so_xong = sum(1 for t in the if t["trang_thai"] == DA_XONG)
        if all(t["trang_thai"] in (DA_XONG, DV_DOI_TAC) for t in the):
            tt_dv = XONG if so_xong == len(the) else DOI_TAC
        elif any(t["trang_thai"] == DANG_LAM for t in the):
            tt_dv = DANG
        else:
            tt_dv = CHO
        them(
            "LAM_DV",
            "Làm dịch vụ",
            tt_dv,
            bat_dau=_dau(*(t["bat_dau"] for t in the)),
            xong=_cuoi(*(t["xong"] for t in the)) if so_xong == len(the) else None,
            dich_vu=the,
        )

    # 6. Quay lại bác sĩ chính (đọc kết quả).
    dk = moc.get("DOC_KQ")
    p_doc = phien_cua("REVIEW")
    q_doc = hang_cua("REVIEW")
    if the or dk or p_doc or q_doc:
        bat = (dk["bat"] if dk else None) or (
            _gio(p_doc.get("started_at")) if p_doc else None
        )
        ket = (dk["ket"] if dk else None) or (
            _gio(p_doc.get("completed_at")) if p_doc else None
        )
        bs_doc = (p_doc or {}).get("bac_si") or (q_doc or {}).get("bac_si") or bs_chinh
        # Không có phiên đọc riêng mà bác sĩ bấm Khám xong SAU khi khách làm
        # dịch vụ (Tuyền 29/09): đã đọc kết quả ngay trong phiên khám chính.
        bat_dv = _dau(*(t["bat_dau"] for t in the)) if the else None
        doc_trong_phien = (
            not p_doc
            and not q_doc
            and not dk
            and xong_kham is not None
            and bat_dv is not None
            and bat_dv < xong_kham
        )
        if doc_trong_phien:
            bat = quay_lai_luc or bat
            ket = xong_kham
        them(
            "DOC_KQ",
            "Quay lại bác sĩ chính",
            XONG
            if ket
            else DANG
            if bat
            else CHO
            if q_doc and q_doc.get("status") in ("waiting", "called")
            else CHUA,
            noi=noi_q(q_doc) if q_doc else _ban_kham_bs(bs_doc),
            ai_lam=bs_doc,
            vao=_gio(q_doc.get("eligible_at")) if q_doc else None,
            bat_dau=bat,
            xong=ket,
            ghi_chu="đọc kết quả ngay trong phiên khám chính"
            if doc_trong_phien
            else (None if (bat or ket) else "đọc kết quả, khi dịch vụ xong"),
        )

    # 7. Thuốc — chỉ khi có đơn; chưa về thì để một dòng "nếu có đơn".
    th = moc.get("THUOC")
    if th:
        them(
            "THUOC",
            "Thuốc",
            # Khách đã check-out thì bước thuốc KHÉP (không còn "đang làm").
            XONG if xong_buoi else (tt_moc(th) if th["trang_thai"] != "chua" else CHO),
            noi="Quầy thuốc",
            bat_dau=th["bat"],
            xong=th["ket"] or (ve_luc if xong_buoi else None),
        )
    elif not xong_buoi and not bo_ve:
        them("THUOC", "Thuốc", CHUA, noi="Quầy thuốc", ghi_chu="nếu có đơn")

    # 8. Check-out.
    them(
        "CHECK_OUT",
        "Check-out",
        XONG if ve_luc else CHUA,
        noi="Lễ tân",
        bat_dau=ve_luc,
        xong=ve_luc,
    )

    # ── ĐANG Ở ĐÂU ─────────────────────────────────────────────────────────
    dang_phuc_vu = sorted(
        (q for q in song if q.get("status") == "serving"),
        key=lambda q: _gio(q.get("serving_at")) or _SOM,
    )
    goi = [q for q in song if q.get("status") == "called"]
    cho = sorted(
        (q for q in song if q.get("status") in ("waiting", "blocked")),
        key=lambda q: (
            q.get("status") != "waiting",
            _gio(q.get("eligible_at")) or _gio(q.get("created_at")) or _MUON,
        ),
    )
    hien_tai: dict[str, Any] | None = None
    if bo_ve:
        o = {
            "trang_thai": "BO_VE",
            "nhan": "Bỏ về",
            "noi": "giữa chừng",
            "tu_luc": ve_luc,
            "stt": None,
        }
    elif xong_buoi:
        o = {
            "trang_thai": "DA_VE",
            "nhan": "Đã về",
            "noi": "Check-out",
            "tu_luc": ve_luc,
            "stt": None,
        }
    elif dang_phuc_vu:
        hien_tai = dang_phuc_vu[-1]
        o = {
            "trang_thai": "DANG_O",
            "nhan": "Đang ở",
            "noi": noi_q(hien_tai),
            "tu_luc": _gio(hien_tai.get("serving_at")),
            "stt": None,
        }
    elif sh and sh["trang_thai"] == "dang":
        o = {
            "trang_thai": "DANG_O",
            "nhan": "Đang ở",
            "noi": "Đo sinh hiệu",
            "tu_luc": sh["bat"],
            "stt": None,
        }
    elif goi or cho:
        hien_tai = (goi or cho)[0]
        o = {
            "trang_thai": "DANG_GOI" if goi else "DANG_CHO",
            "nhan": "Đang chờ",
            "noi": noi_q(hien_tai),
            "tu_luc": _gio(hien_tai.get("eligible_at")),
            "stt": hien_tai.get("stt"),
        }
    elif check_in and (sh is None or sh["trang_thai"] == "chua"):
        o = {
            "trang_thai": "DANG_CHO",
            "nhan": "Đang chờ",
            "noi": "Đo sinh hiệu",
            "tu_luc": check_in,
            "stt": None,
        }
    else:
        o = {
            "trang_thai": "O_QUAY",
            "nhan": "Đang chờ",
            "noi": "Quầy lễ tân",
            "tu_luc": None,
            "stt": None,
        }

    # ── TIẾP THEO: các chỗ chờ khác (phòng kế, STT, số người chờ) ────────────
    tiep: list[dict[str, Any]] = []
    if not xong_buoi and not bo_ve:
        for q in [*goi, *cho]:
            if hien_tai is not None and q.get("id") == hien_tai.get("id"):
                continue
            tiep.append(
                {
                    "noi": noi_q(q),
                    "stt": q.get("stt")
                    if q.get("status") in ("waiting", "called")
                    else None,
                    "so_nguoi_cho": q.get("so_truoc")
                    if q.get("status") in ("waiting", "called")
                    else q.get("so_cho"),
                    "ghi_chu": "đọc kết quả" if q.get("reason") == "REVIEW" else None,
                    "du_kien": noi_la_du_kien(noi_q(q)),
                }
            )
        if not tiep:
            # Không còn chỗ chờ nào: bước kế trên dòng thời gian.
            ke = next(
                (
                    b
                    for b in buoc
                    if b["trang_thai"] in (CHO, CHUA)
                    and b["ma"] != "CHECK_IN"
                    and b["noi"] != o["noi"]
                ),
                None,
            )
            if ke is not None:
                tiep.append(
                    {
                        "noi": ke["noi"] or ke["ten"],
                        "stt": None,
                        "so_nguoi_cho": None,
                        "ghi_chu": ke["ten"] if ke["noi"] else ke["ghi_chu"],
                        # Bước kế trên dòng thời gian, chưa có chỗ chờ thật.
                        "du_kien": True,
                    }
                )

    # ── DẠNG GỌN ───────────────────────────────────────────────────────────
    doan: list[str] = []
    for b in buoc:
        if b["ma"] == "LAM_DV":
            for t in b["dich_vu"] or []:
                doan.append(
                    {
                        DA_XONG: XONG,
                        DANG_LAM: DANG,
                        CHO_LAM: CHO,
                        CHO_THU: CHO,
                        DV_DOI_TAC: DOI_TAC,
                    }.get(t["trang_thai"], CHUA)
                )
        elif b["ma"] == "THUOC" and b["trang_thai"] == CHUA:
            continue  # "nếu có đơn" — không chiếm một đoạn khi chưa biết có đơn
        else:
            doan.append(b["trang_thai"])
    if xong_buoi:
        # Check-out = xong buổi: tick hết.
        doan = [XONG] * len(doan)
    else:
        doan = [CHUA if d == KHONG else d for d in doan]

    con_cho: list[str] = []
    for t in the:
        if t["trang_thai"] in (CHO_LAM, CHO_THU) and t["noi"] != o["noi"]:
            ten_cho = t["noi"] if t["trang_thai"] == CHO_LAM else "Thu tiền"
            if ten_cho not in con_cho:
                con_cho.append(ten_cho)
    if any(t["trang_thai"] == DV_DOI_TAC for t in the):
        con_cho.append("KQ đối tác")

    sh_buoc = next((b for b in buoc if b["ma"] == "SINH_HIEU"), None)
    gon = {
        **o,
        # Hiện RÕ ở dòng gọn (Tuyền duyệt 29/09/2026): sinh hiệu đo lại lúc nào,
        # dịch vụ nào làm lại lần mấy.
        "do_lai": list(sh_buoc.get("do_lai") or []) if sh_buoc else [],
        "lam_lai": [
            {"ten": t["ten"], "lan": t["so_lan"]} for t in the if t["so_lan"] >= 2
        ],
        "xong_buoi": xong_buoi,
        "doan": doan,
        "dv_xong": sum(1 for t in the if t["trang_thai"] == DA_XONG),
        "dv_tong": len(the),
        "con_cho": con_cho,
    }
    return {
        "visit_id": luot.get("visit_id"),
        "gon": gon,
        "dang_o": o,
        "tiep_theo": tiep,
        "buoc": buoc,
    }


def _iso(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _iso(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_iso(x) for x in v]
    return v


# ── ĐỌC DB ──────────────────────────────────────────────────────────────────

_SQL_LUOT = """
    SELECT v.visit_id::text AS visit_id, v.status, v.checked_in_at, v.closed_at,
           a.created_at AS dat_luc,
           (coalesce(v.checked_in_at, v.created_at)
                AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay
      FROM visit v
      LEFT JOIN appointment a ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
     WHERE v.clinic_id = $1::uuid AND v.visit_id = ANY($2::uuid[])
"""

# Mọi chỗ chờ của các lượt + vị trí trong hàng. "Cùng hàng" = cùng lane, cùng
# phòng (hàng phòng) / cùng bác sĩ (hàng bác sĩ) / hàng tư vấn chung; thứ tự
# `coalesce(eligible_at, created_at), id` — y như màn hàng chờ.
_SQL_HANG = """
    SELECT q.id::text AS id, q.visit_id::text AS visit_id, q.lane, q.reason,
           q.ref_id::text AS ref_id, q.status, q.eligible_at, q.called_at,
           q.serving_at, q.done_at, q.created_at,
           -- Bác sĩ của chỗ chờ, rơi về bác sĩ của PHIÊN (29/09/2026: trợ lý
           -- bấm Bắt đầu cho khách chưa gán bác sĩ — phiên có bác sĩ, chỗ chờ
           -- đời trước thì chưa) để "đang ở" ra đúng phòng bác sĩ.
           coalesce(q.doctor_staff_id, c.doctor_staff_id)::text
               AS doctor_staff_id,
           r.name AS phong, d.full_name AS bac_si,
           CASE WHEN q.status IN ('waiting', 'called', 'blocked') THEN (
               SELECT count(*) FROM queue_entry o
                WHERE o.clinic_id = q.clinic_id AND o.lane = q.lane
                  AND o.id <> q.id AND o.status IN ('waiting', 'called')
                  AND (q.lane = 'TU_VAN'
                       OR (q.lane = 'ROOM' AND o.room_id = q.room_id)
                       OR (q.lane = 'DOCTOR'
                           AND o.doctor_staff_id
                               IS NOT DISTINCT FROM q.doctor_staff_id))
                  AND (q.status = 'blocked'
                       OR (coalesce(o.eligible_at, o.created_at), o.id)
                          < (coalesce(q.eligible_at, q.created_at), q.id))
           ) END AS so_truoc
      FROM queue_entry q
      LEFT JOIN consultation c
        ON c.id = q.ref_id AND q.reason <> 'SERVICE' AND c.clinic_id = q.clinic_id
      LEFT JOIN clinic_room r ON r.id = q.room_id
      LEFT JOIN staff d ON d.id = coalesce(q.doctor_staff_id, c.doctor_staff_id)
     WHERE q.clinic_id = $1::uuid AND q.visit_id = ANY($2::uuid[])
       AND q.status <> 'cancelled'
     ORDER BY q.created_at
"""

_SQL_PHIEN = """
    SELECT c.visit_id::text AS visit_id, c.kind, c.status, c.started_at,
           c.completed_at, c.doctor_staff_id::text AS doctor_staff_id,
           s.full_name AS bac_si
      FROM consultation c
      LEFT JOIN staff s ON s.id = c.doctor_staff_id
     WHERE c.clinic_id = $1::uuid AND c.visit_id = ANY($2::uuid[])
       AND c.status <> 'cancelled'
     ORDER BY c.round_no
"""

# Phòng của bác sĩ theo lịch trực ngày khám — cùng phép tra với con trỏ vị trí
# (`hang_cho.cap_nhat_vi_tri`).
_SQL_PHONG_BAC_SI = """
    SELECT DISTINCT ON (w.staff_id, w.work_date)
           w.staff_id::text AS staff_id, w.work_date AS ngay, r.name AS phong
      FROM work_roster w
      JOIN vi_tri_lam_viec vt ON vt.clinic_id = w.clinic_id AND vt.code = w.station
      JOIN clinic_room r ON r.id = vt.room_id
     WHERE w.clinic_id = $1::uuid AND w.staff_id::text = ANY($2::text[])
       AND w.work_date = ANY($3::date[]) AND w.status <> 'REJECTED'
       AND vt.room_id IS NOT NULL
     ORDER BY w.staff_id, w.work_date, vt.sort
"""

# Mọi LẦN LÀM của chỉ định (làm lại = lần 2, 3…) — `service_execution_attempt`.
_SQL_LAN_LAM = """
    SELECT a.service_order_id::text AS order_id, a.attempt_no, a.status,
           a.started_at, a.completed_at, a.interrupted_at
      FROM service_execution_attempt a
      JOIN service_order o
        ON o.id = a.service_order_id AND o.clinic_id = a.clinic_id
     WHERE a.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
     ORDER BY a.service_order_id, a.attempt_no
"""

_SU_KIEN_AI = ("visit.checked_in", "vitals.recorded", "payment.service_collected")


async def doc_hanh_trinh_khach(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_ids: list[str],
    kem_ai: bool = False,
) -> dict[str, dict[str, Any]]:
    """Hành trình của NHIỀU lượt trong 5–6 câu (không theo số lượt). Lượt không
    thuộc phòng khám này không có trong kết quả. Thời điểm trả dạng ISO."""
    ids = [v.lower() for v in visit_ids]
    if not ids:
        return {}
    luot = [dict(r) for r in await conn.fetch(_SQL_LUOT, clinic_id, ids)]
    if not luot:
        return {}
    ids = [x["visit_id"] for x in luot]
    su_kien, chi_dinh = await _doc_su_kien_chi_dinh(
        conn, clinic_id=clinic_id, visit_ids=ids
    )
    hang: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in await conn.fetch(_SQL_HANG, clinic_id, ids):
        q = dict(r)
        so_truoc = q.get("so_truoc")
        q["so_truoc"] = int(so_truoc) if so_truoc is not None else None
        q["so_cho"] = q["so_truoc"] if q["status"] == "blocked" else None
        q["stt"] = (
            q["so_truoc"] + 1
            if q["status"] in ("waiting", "called") and so_truoc is not None
            else None
        )
        hang[q["visit_id"]].append(q)
    phien: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in await conn.fetch(_SQL_PHIEN, clinic_id, ids):
        phien[r["visit_id"]].append(dict(r))
    bac_si = sorted(
        {
            x["doctor_staff_id"]
            for ds in (*hang.values(), *phien.values())
            for x in ds
            if x.get("doctor_staff_id")
        }
    )
    ngay: list[date] = sorted({x["ngay"] for x in luot if x.get("ngay")})
    phong: dict[tuple[str, date], str] = {}
    if bac_si and ngay:
        for r in await conn.fetch(_SQL_PHONG_BAC_SI, clinic_id, bac_si, ngay):
            phong[(r["staff_id"], r["ngay"])] = r["phong"]
    lan_lam: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in await conn.fetch(_SQL_LAN_LAM, clinic_id, ids):
        lan_lam[r["order_id"]].append(dict(r))
    ai: dict[str, dict[str, str]] = defaultdict(dict)
    if kem_ai:
        for r in await conn.fetch(
            """
            SELECT DISTINCT ON (d.visit_id, d.event_type)
                   d.visit_id::text AS visit_id, d.event_type, s.full_name
              FROM luot_dong_thoi_gian d
              JOIN staff s ON s.id = d.actor_staff_id
             WHERE d.clinic_id = $1::uuid AND d.visit_id = ANY($2::uuid[])
               AND d.event_type = ANY($3::text[])
             ORDER BY d.visit_id, d.event_type, d.occurred_at DESC
            """,
            clinic_id,
            ids,
            list(_SU_KIEN_AI),
        ):
            ai[r["visit_id"]][r["event_type"]] = r["full_name"]
    ra: dict[str, dict[str, Any]] = {}
    for x in luot:
        vid = x["visit_id"]
        ra[vid] = _iso(
            dung_hanh_trinh_khach(
                luot=x,
                su_kien=su_kien.get(vid, []),
                chi_dinh=chi_dinh.get(vid, []),
                hang=hang.get(vid, []),
                phien=phien.get(vid, []),
                phong_bac_si={
                    s: p for (s, d), p in phong.items() if d == x.get("ngay")
                },
                ai=ai.get(vid),
                lan_lam=lan_lam,
            )
        )
    return ra


async def dang_o_cac_luot(
    conn: asyncpg.Connection, *, clinic_id: str, visit_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """visit_id → khối ``gon`` (đang ở / đang chờ phòng nào) — nguồn "vị trí
    khách" cho NHÃN TRẠNG THÁI mọi màn (`core.trang_thai_lich
    .trang_thai_hien_thi`, 30/09/2026). Người gọi chỉ đưa lượt còn mở.
    Không lượt nào → không truy vấn."""
    if not visit_ids:
        return {}
    kq = await doc_hanh_trinh_khach(
        conn, clinic_id=clinic_id, visit_ids=list(dict.fromkeys(visit_ids))
    )
    return {k: v["gon"] for k, v in kq.items()}


class HanhTrinhKhachService:
    """Cửa đọc: mọi thành viên nội bộ (vai tài khoản, trừ đối tác / TV) —
    cùng cửa với Hành trình / Xem lượt (`goi_duoc`)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def mot_luot(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        if not goi_duoc(identity):
            raise SafetyGateError("Tài khoản của bạn không xem hành trình khách.")
        ma = doc_ma_luot(visit_id)
        if not ma:
            raise NotFoundError("Không tìm thấy lượt khám.")
        async with self._pool.acquire() as conn:
            kq = await doc_hanh_trinh_khach(
                conn, clinic_id=identity.clinic_id, visit_ids=ma, kem_ai=True
            )
            if ma[0] not in kq:
                raise NotFoundError("Không tìm thấy lượt khám.")
            # Lịch sử xếp / đổi phòng từng chỉ định (Tuyền 29/09/2026) — theo mã
            # chỉ định, thẻ dịch vụ vẽ dưới thẻ của mình.
            kq[ma[0]]["lich_su_phong"] = _iso(
                await lich_su_phong_cua_luot(
                    conn, clinic_id=identity.clinic_id, visit_id=ma[0]
                )
            )
        return kq[ma[0]]

    async def gon_nhieu_luot(
        self, *, luot: Any, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Dạng gọn của nhiều lượt (`luot` = "id1,id2,…"). Mã rác bị bỏ qua."""
        if not goi_duoc(identity):
            raise SafetyGateError("Tài khoản của bạn không xem hành trình khách.")
        ma = doc_ma_luot(luot)
        if not ma:
            return {"luot": {}}
        async with self._pool.acquire() as conn:
            kq = await doc_hanh_trinh_khach(
                conn, clinic_id=identity.clinic_id, visit_ids=ma
            )
        return {"luot": {k: v["gon"] for k, v in kq.items()}}


__all__ = [
    "HanhTrinhKhachService",
    "dang_o_cac_luot",
    "noi_la_du_kien",
    "doc_hanh_trinh_khach",
    "doc_ma_luot",
    "dung_hanh_trinh_khach",
    "noi_cua_hang",
]
