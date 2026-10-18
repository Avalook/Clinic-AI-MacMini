"""BỘ BẤT BIẾN DỮ LIỆU — những câu hỏi "dữ liệu có đang sai không" chạy được bằng SQL.

Mỗi bất biến là MỘT câu SELECT trả về các dòng VI PHẠM (0 dòng = đúng). Luật:

* Chỉ SELECT. Chỉ trả id / mã / con số — KHÔNG tên, SĐT, ghi chú (dữ liệu cá nhân
  không được rời database vào báo cáo; hiến pháp §10, §11).
* Chạy trong giao dịch `READ ONLY` có `statement_timeout`; `kiem_chi_select` ép
  ở mức mã nguồn (bài test `test_agent_soat_chi_doc.py` canh).
* Tên cột/giá trị trạng thái lấy từ schema thật (migration), có chú thích khi một
  luật nghiệp vụ là SUY RA (vd dấu của sổ kho) để người đọc biết chỗ nào có thể sai.

Hai đường chạy cùng một bộ câu hỏi:
  1. `doc_du_lieu.py --dsn …` — vào database local/staging (host bị kiểm).
  2. `doc_du_lieu.py --in-sql` — in ra MỘT tệp SQL chỉ-đọc để người có quyền chạy
     trên máy chủ (`ssh … 'bash -s' < tệp`) rồi nạp kết quả về bằng `--nap`.
     Agent KHÔNG tự ssh vào máy chủ, không có thông tin đăng nhập prod.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .khuon import LoaiVanDe, UuTien


@dataclass(frozen=True)
class BatBien:
    ma: str
    ten: str
    uu_tien: UuTien
    loai: LoaiVanDe
    sql: str  # SELECT trả dòng vi phạm
    vi_sao: str  # vì sao vi phạm là sai (đủ để người không đọc SQL hiểu)
    rui_ro: str
    de_xuat: str
    #: Luật này suy ra từ cách đọc code, chưa được ai xác nhận → mức bằng chứng thấp.
    suy_ra: bool = False
    muc_viec: int = 2


BAT_BIEN: tuple[BatBien, ...] = (
    BatBien(
        "D01",
        "Tồn lô thuốc âm",
        UuTien.P0,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT id::text AS id, batch_code, quantity_on_hand::text AS ton
           FROM drug_batch WHERE quantity_on_hand < 0""",
        "Kho thuốc chặn xuất quá tồn (khác vật tư, chỉ cảnh báo) nên tồn âm là "
        "dấu hiệu có đường ghi lách luật kho.",
        "Số tồn kho sai → báo cáo kho, giá vốn và cảnh báo hết thuốc sai theo.",
        "Truy dòng sổ `inventory_txn` của lô, tìm lệnh gây âm; sửa đường ghi.",
        muc_viec=3,
    ),
    BatBien(
        "D02",
        "Tồn lô lệch tổng sổ kho",
        UuTien.P0,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT b.id::text AS id, b.batch_code,
                  b.quantity_on_hand::text AS ton_lo,
                  COALESCE(s.tong, 0)::text AS tong_so
           FROM drug_batch b
           LEFT JOIN (SELECT drug_batch_id, SUM(quantity) AS tong
                      FROM inventory_txn GROUP BY drug_batch_id) s
                  ON s.drug_batch_id = b.id
           WHERE b.quantity_on_hand <> COALESCE(s.tong, 0)""",
        "Tồn lô phải bằng tổng các dòng sổ kho (trigger `inventory_txn_apply` cộng "
        "từ sổ). Lệch nghĩa là có ai sửa tồn không qua sổ, hoặc dòng sổ bị mất.",
        "Không còn tin được số tồn: kiểm kê và báo cáo kho đều dựa vào nó.",
        "Đối chiếu từng lô lệch với phiếu kho; nếu do dữ liệu mẫu/nhập tay cũ thì "
        "ghi nhận, nếu mới thì tìm đường ghi.",
        suy_ra=True,
        muc_viec=3,
    ),
    BatBien(
        "D03",
        "Vật tư tồn âm",
        UuTien.P6,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT id::text AS id, vat_tu_id::text AS vat_tu, so_luong::text AS ton
           FROM vat_tu_ton WHERE so_luong < 0""",
        "Quang chốt 17/10: vật tư tồn âm KHÔNG chặn, chỉ cảnh báo. Nên đây là "
        "danh sách để người kho biết cần nhập bù sổ, không phải lỗi hệ thống.",
        "Số vật tư thực tế chưa được ghi nhận đủ.",
        "Cho người kho xem danh sách, nhập phiếu bù.",
    ),
    BatBien(
        "D04",
        "Giao thuốc nhiều hơn số đã gán lô",
        UuTien.P0,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT id::text AS id, prescription_id::text AS don,
                  quantity::text AS gan, handed_over_qty::text AS da_giao
           FROM prescription_allocation WHERE handed_over_qty > quantity""",
        "Số đã giao tay không thể vượt số đã gán từ lô.",
        "Trừ kho thiếu hoặc khách nhận nhiều hơn đơn.",
        "Truy dòng giao, đối chiếu với phiếu kho cùng ngày.",
        muc_viec=3,
    ),
    BatBien(
        "D05",
        "Lịch hẹn kết thúc trước khi bắt đầu",
        UuTien.P1,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT id::text AS id, slot_start::text AS bat_dau, slot_end::text AS het
           FROM appointment WHERE slot_end <= slot_start""",
        "Khoảng giờ rỗng/ngược làm mọi phép tính sức chứa phòng sai.",
        "Lịch trống bị tính nhầm, có thể xếp trùng hoặc ẩn slot.",
        "Tìm đường tạo/sửa lịch cho phép giờ ngược; thêm ràng buộc CHECK ở Postgres.",
    ),
    BatBien(
        "D06",
        "Phiếu thu huỷ thiếu lý do hoặc thiếu mốc huỷ",
        UuTien.P0,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT id::text AS id, status, voided_at::text AS luc_huy
           FROM payment
           WHERE (status = 'VOIDED' AND (voided_at IS NULL
                  OR void_reason IS NULL OR btrim(void_reason) = ''))
              OR (status <> 'VOIDED' AND voided_at IS NOT NULL)""",
        "Huỷ phiếu thu là thao tác tiền: phải có thời điểm và lý do; trạng thái "
        "và dấu huỷ không được mâu thuẫn nhau.",
        "Không giải trình được khoản tiền bị huỷ khi đối soát.",
        "Truy người huỷ qua sổ sự kiện; bổ sung ràng buộc CHECK.",
        muc_viec=3,
    ),
    BatBien(
        "D07",
        "Lượt khám đã chốt nhưng thiếu mốc chốt",
        UuTien.P1,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT visit_id::text AS id, status
           FROM visit WHERE status = 'FINALIZED' AND finalized_at IS NULL""",
        "Lượt FINALIZED phải có `finalized_at`; thiếu thì báo cáo theo ngày bỏ sót.",
        "Doanh thu/số lượt theo ngày lệch.",
        "Tìm đường chuyển trạng thái không đặt mốc; sửa dữ liệu qua migration.",
    ),
    BatBien(
        "D08",
        "Hoàn tiền mở quá 3 ngày chưa đóng",
        UuTien.P2,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT refund_id::text AS id, amount::text AS so_tien,
                  created_at::text AS tao_luc
           FROM payment_refund
           WHERE completed_at IS NULL AND closed_at IS NULL
             AND created_at < now() - interval '3 days'""",
        "Khách đã được hứa hoàn tiền nhưng lệnh vẫn mở: việc có nguy cơ rơi.",
        "Khách chờ tiền không rõ lý do; sai lệch quỹ.",
        "Giao người thu ngân xử lý hoặc đóng có lý do.",
        muc_viec=3,
    ),
    BatBien(
        "D09",
        "Thuốc khách trả chờ kiểm quá 2 ngày",
        UuTien.P2,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT id::text AS id, returned_qty::text AS so_luong,
                  returned_at::text AS tra_luc
           FROM drug_return
           WHERE disposition IS NULL AND returned_at < now() - interval '2 days'""",
        "Thuốc trả về chưa ai quyết nhập lại hay huỷ → vừa không bán được vừa "
        "không tính hao hụt.",
        "Tồn kho thật và tồn sổ lệch nhau cho đến khi có quyết định.",
        "Nhắc dược sĩ vào màn 'Thuốc khách trả chờ kiểm'.",
    ),
    BatBien(
        "D10",
        "Sự kiện chưa xử lý quá 15 phút",
        UuTien.P2,
        LoaiVanDe.MAT_DU_LIEU,
        """SELECT event_id::text AS id, consumer, status, attempts::text AS lan
           FROM event_delivery
           WHERE processed_at IS NULL
             AND created_at < now() - interval '15 minutes'""",
        "Mỗi sự kiện giao cho từng bên nghe và phải xử lý trong vài giây. Sự kiện "
        "kẹt = bên nghe chết hoặc lỗi lặp: việc tự động (chuông, nhắc, trách "
        "nhiệm dịch vụ) không xảy ra.",
        "Việc nghiệp vụ bị rơi mà không ai thấy.",
        "Xem `last_error` của dòng kẹt trên màn /ops → Lỗi & cảnh báo.",
        suy_ra=True,
    ),
    BatBien(
        "D11",
        "Thuốc đã giao nhưng chưa gán lô quá 1 ngày",
        UuTien.P0,
        LoaiVanDe.MAT_DU_LIEU,
        """SELECT id::text AS id, prescription_id::text AS don,
                  giao_luc::text AS giao_luc
           FROM thuoc_giao_chua_gan_lo
           WHERE drug_batch_id IS NULL AND giao_luc < now() - interval '1 day'""",
        "Thuốc đã rời quầy nhưng kho chưa trừ vào lô nào → tồn sổ cao hơn thật.",
        "Mất dấu truy xuất lô khi cần thu hồi thuốc.",
        "Gán lô từ màn kho thuốc (sau khi chuyển lô ra quầy nếu cơ sở tách kho).",
        muc_viec=3,
    ),
    BatBien(
        "D12",
        "Lô hết hạn vẫn còn tồn",
        UuTien.P2,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT id::text AS id, batch_code, expiry_date::text AS het_han,
                  quantity_on_hand::text AS ton
           FROM drug_batch
           WHERE expiry_date < current_date AND quantity_on_hand > 0""",
        "Thuốc quá hạn còn trong sổ tồn có thể bị cấp nhầm hoặc làm tồn ảo.",
        "An toàn khách (thuốc hết hạn) và số tồn.",
        "Huỷ lô hết hạn (có sẵn lệnh 'huỷ lô hết hạn' trên màn kho).",
        muc_viec=3,
    ),
    BatBien(
        "D13",
        "Lô nhập khác đơn vị bán của thuốc",
        UuTien.P2,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT b.id::text AS id, b.batch_code, b.unit AS don_vi_lo,
                  c.don_vi_ban
           FROM drug_batch b JOIN drug_catalog c ON c.id = b.drug_catalog_id
           WHERE c.don_vi_ban IS NOT NULL
             AND lower(btrim(b.unit)) <> lower(btrim(c.don_vi_ban))
             AND b.quantity_on_hand > 0""",
        "Lô đếm bằng 'hộp' mà thuốc bán theo 'gói' thì số giao bị trừ sai đơn vị "
        "(đợt 17/10 sửa lúc nhập; lô cũ vẫn lệch).",
        "Giao thuốc không trừ đúng kho; có thể tưởng còn hàng mà hết.",
        "Chuyển đơn vị lô bằng màn quy đổi (đợt dot/1710-kho) hoặc nhập lại.",
        muc_viec=3,
    ),
    BatBien(
        "D14",
        "Lượt khám mở/đang khám quá 2 ngày",
        UuTien.P2,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT visit_id::text AS id, status, created_at::text AS tao_luc
           FROM visit
           WHERE status IN ('OPEN', 'IN_PROGRESS')
             AND created_at < now() - interval '2 days'""",
        "Một lượt khám không kéo dài quá hai ngày; còn mở nghĩa là khách đã về mà "
        "hệ thống vẫn nghĩ đang ở phòng khám (hiến pháp §1: thực tế ≠ trạng thái).",
        "Hàng chờ, tải phòng và báo cáo ngày sai.",
        "Đóng lượt treo qua luồng 'chưa hoàn tất' có lý do (không xoá).",
    ),
    BatBien(
        "D15",
        "Lịch đã xác nhận nhưng quá hạn 1 ngày chưa check-in/huỷ",
        UuTien.P2,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT id::text AS id, slot_start::text AS gio_hen
           FROM appointment
           WHERE status = 'CONFIRMED'
             AND slot_start < now() - interval '1 day'""",
        "Lịch qua ngày mà vẫn 'đã xác nhận' → không biết khách đến hay bỏ hẹn; "
        "làm sai thống kê vắng mặt và danh sách gọi nhắc.",
        "CSKH không biết gọi ai; slot bị coi là đã dùng.",
        "Chạy lại bước đóng lịch cuối ngày hoặc đánh dấu 'không đến' có lý do.",
    ),
    BatBien(
        "D16",
        "Bảng có clinic_id, role đăng nhập đọc được nhưng chưa bật RLS",
        UuTien.P0,
        LoaiVanDe.DU_LIEU_SAI,
        """SELECT c.relname AS id
           FROM pg_class c
           JOIN pg_namespace n ON n.oid = c.relnamespace
           JOIN pg_attribute a ON a.attrelid = c.oid
                AND a.attname = 'clinic_id' AND NOT a.attisdropped
           WHERE n.nspname = 'public' AND c.relkind = 'r'
             AND NOT c.relrowsecurity
             AND (has_table_privilege('anon', c.oid, 'SELECT')
                  OR has_table_privilege('authenticated', c.oid, 'SELECT'))""",
        "Bảng chứa dữ liệu theo phòng khám mà ai đăng nhập cũng đọc được qua "
        "PostgREST nếu không có RLS: lộ dữ liệu giữa các phòng khám.",
        "Rò dữ liệu xuyên phòng khám.",
        "Bật RLS + policy theo clinic_id (migration, mức 3), hoặc thu quyền SELECT.",
        muc_viec=3,
    ),
)

_CAM = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|"
    r"vacuum|call|do|execute|set|reset|lock|comment|refresh|merge|"
    r"nextval|setval|pg_sleep|pg_advisory\w*|pg_terminate\w*|pg_cancel\w*|"
    r"lo_import|lo_export|dblink\w*|pg_read_\w+|set_config)\b|"
    r"\bfor\s+(update|share|no\s+key)\b",
    re.IGNORECASE,
)


def kiem_chi_select(sql: str) -> None:
    """Ném lỗi nếu câu SQL không thuần SELECT. Hàng rào thứ hai, sau READ ONLY."""
    s = re.sub(r"'[^']*'", "''", sql).strip().rstrip(";")
    if not re.match(r"(?is)^\s*select\b", s):
        raise ValueError(f"không bắt đầu bằng SELECT: {sql[:60]}")
    if ";" in s:
        raise ValueError("nhiều câu lệnh trong một bất biến")
    m = _CAM.search(s)
    if m:
        raise ValueError(f"từ khoá cấm `{m.group(1)}` trong bất biến")


def bao_boc(b: BatBien) -> str:
    """Bọc để mỗi bất biến trả MỘT dòng JSON (jsonb::text không xuống dòng)."""
    kiem_chi_select(b.sql)
    sql = b.sql.strip().rstrip(";")
    return (
        "SELECT jsonb_build_object("
        f"'ma', '{b.ma}', "
        f"'so_dong', (SELECT count(*) FROM ({sql}) q), "
        f"'mau', (SELECT COALESCE(jsonb_agg(t), '[]'::jsonb) "
        f"FROM (SELECT * FROM ({sql}) q2 LIMIT 5) t))::text"
    )


def tao_tep_sql() -> str:
    """Một tệp psql chỉ-đọc, chạy được trên máy chủ: mỗi bất biến một giao dịch."""
    ra = [
        "-- Agent soát hệ thống — BỘ BẤT BIẾN DỮ LIỆU (chỉ đọc).",
        "-- Chạy:  psql -X -q -t -A -v ON_ERROR_STOP=0 < tệp   (mỗi dòng ra là JSON)",
        "\\set ON_ERROR_STOP off",
    ]
    for b in BAT_BIEN:
        ra += [
            f"-- {b.ma}: {b.ten}",
            "BEGIN READ ONLY;",
            "SET LOCAL statement_timeout = '20s';",
            "SET LOCAL lock_timeout = '1s';",
            bao_boc(b) + ";",
            "ROLLBACK;",
        ]
    return "\n".join(ra) + "\n"
