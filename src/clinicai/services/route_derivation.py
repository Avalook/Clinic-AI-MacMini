"""Suy ra tuyến điều phối từ những gì bác sĩ ĐÃ CHỈ ĐỊNH.

VÌ SAO CẦN CÁI NÀY.

Bảng Trưởng ca có cột "bước kế tiếp", và nó đọc từ `visit_route`. Nhưng trên
prod hôm nay **0/25 lượt khám có tuyến** — vì tuyến chỉ được ghi khi có người
bấm tay "Áp tuyến", mà không ai bấm. Nghĩa là cột đó trống với mọi bệnh nhân, và
Trưởng ca không được gợi ý gì cả.

Nguồn sự thật đúng đã có sẵn: bác sĩ chỉ định gì thì bệnh nhân phải đi qua đó.
Nên tuyến được suy ra từ chỉ định, thay vì bắt ai đó chọn lại bằng tay một thứ
hệ thống đã biết.

VÌ SAO KHÔNG VIẾT CỨNG ĐUÔI TUYẾN.

Ba tuyến mẫu hiện có khác nhau đúng ở thứ tự siêu âm / lấy máu, còn đuôi thì
giống hệt: duyệt kết quả → thuốc → kết thúc. Viết cứng cái đuôi đó vào Python
nghĩa là hôm nào Quang sửa tuyến mẫu, code lặng lẽ sai. Nên đuôi được ĐỌC RA từ
chính các tuyến mẫu: phần hậu tố chung dài nhất của mọi tuyến đang bật.

Thứ tự phần đầu cũng lấy từ tuyến mẫu (bước nào xuất hiện trước thì đi trước),
để tuyến suy ra không mâu thuẫn với thứ tự khoa phòng mà phòng khám đã thống
nhất.
"""

from __future__ import annotations


def common_suffix(lists: list[list[str]]) -> list[str]:
    """Hậu tố chung dài nhất. Rỗng khi không có gì chung."""
    if not lists or any(not x for x in lists):
        return []
    out: list[str] = []
    for i in range(1, min(len(x) for x in lists) + 1):
        step = lists[0][-i]
        if all(x[-i] == step for x in lists):
            out.insert(0, step)
        else:
            break
    return out


def canonical_order(templates: list[list[str]]) -> list[str]:
    """Thứ tự khoa phòng theo tuyến mẫu: xuất hiện sớm hơn thì đi trước.

    Dùng vị trí NHỎ NHẤT của mỗi bước trên các tuyến. Ba tuyến mẫu đảo thứ tự
    siêu âm/lấy máu, nên bước nào từng đứng trước ở BẤT KỲ tuyến nào thì được
    coi là đứng trước — đủ để có một thứ tự ổn định, và không tuyến nào bị coi
    là "tuyến chuẩn" hơn tuyến kia.
    """
    first: dict[str, int] = {}
    for steps in templates:
        for i, s in enumerate(steps):
            if s not in first or i < first[s]:
                first[s] = i
    return sorted(first, key=lambda s: (first[s], s))


def derive_route(
    ordered_nodes: list[str], templates: list[list[str]]
) -> list[str]:
    """Tuyến = các bước còn phải đi (theo thứ tự khoa phòng) + đuôi chung.

    ``ordered_nodes`` là node của những việc đang chờ/đang làm của lượt khám —
    tức là chỉ định chưa xong. Bước ĐÃ XONG không nằm trong đây, và cũng không
    nên: tuyến nói bệnh nhân còn phải đi đâu, không phải đã đi đâu.
    """
    head: list[str] = []
    tail = common_suffix(templates)
    for node in ordered_nodes:
        if node and node not in tail and node not in head:
            head.append(node)
    if not head and not any(n for n in ordered_nodes):
        # Không còn việc gì đang chờ thì KHÔNG có tuyến. Trả về mỗi cái đuôi là
        # bịa ra cho bệnh nhân mấy bước không ai chỉ định — và bảng Trưởng ca sẽ
        # giục đi những chỗ đó.
        return []

    rank = {s: i for i, s in enumerate(canonical_order(templates))}
    # Bước có trong tuyến mẫu đi theo thứ tự tuyến mẫu; bước lạ (dịch vụ mới
    # chưa được đưa vào tuyến nào) xếp sau, giữ nguyên thứ tự bác sĩ chỉ định —
    # đoán thứ tự cho một bước chưa ai khai là đoán bừa. Vị trí gốc phải chốt
    # TRƯỚC khi sắp: gọi head.index() trong khoá sắp xếp là đọc một danh sách
    # đang bị xáo.
    was = {s: i for i, s in enumerate(head)}
    head.sort(key=lambda s: (rank.get(s, len(rank)), was[s]))
    return head + tail
