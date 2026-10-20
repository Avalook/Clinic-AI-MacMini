import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import api_read as A
good = json.loads((A.SP / "out" / "new-good.json").read_text())
slim = [{"t": g.get("title"), "d": (g.get("detail") or "")[:220]} for g in good]
SYSTEM = """Bạn chọn lọc các "mẫu thiết kế tốt" mà nhiều người đọc code ghi lại cho một hệ thống quản lý phòng khám. Đầu vào là danh sách dài, nhiều mục trùng ý. Hãy chọn đúng 14 mẫu KHÁC NHAU và quan trọng nhất đáng nhân rộng cho toàn hệ thống (ưu tiên: an toàn dữ liệu, chống lặp, chống ghi đè, để lại dấu vết, tách cấu hình theo phòng khám, khôi phục). Viết lại bằng tiếng Việt đời thường cho chủ phòng khám, không thuật ngữ kỹ thuật, 1–2 câu mỗi mẫu, trung thực theo dữ liệu, không thêm chi tiết không có. CHỈ TRẢ VỀ MẢNG JSON [{"title": "", "detail": ""}]."""
r = A.call(A.anthropic.Anthropic(api_key=A.load_key(), max_retries=4, timeout=900), "good", SYSTEM, json.dumps(slim, ensure_ascii=False), 8000, "low")
arr = A.extract_json(r[0])
(A.SP / "out" / "good-curated.json").write_text(json.dumps(arr, ensure_ascii=False, indent=1))
print("mẫu tốt chọn:", len(arr))
