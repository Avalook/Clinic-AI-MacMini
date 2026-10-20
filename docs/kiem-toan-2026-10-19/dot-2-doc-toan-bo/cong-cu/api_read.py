"""Việc giao cho Messages API (chỉ đọc, không tool, không ghi repo), có TRẦN CHI TIÊU CỨNG.

  python3 -I api_read.py --run T15 T16        # đọc chunk test
  python3 -I api_read.py --plain FILE.json    # viết lại phát hiện sang tiếng đời thường
  python3 -I api_read.py --ledger             # xem đã chi bao nhiêu
Khoá đọc từ ~/.clinicai-audit.env (không in ra). Sổ chi tiêu: api-ledger.json (trần CAP_USD).
"""
import argparse, json, os, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import anthropic

SP = Path(__file__).resolve().parent
REPO = "/Users/quangdang/.codex/worktrees/audit-main-1910/Dr4Women-MacMini"
SHA = "956ba4f236b1c92f1280d2097018c199e90ce8c7"
MODEL = "claude-sonnet-5-5"
PRICES = {"claude-sonnet-5-5": (2.0e-6, 10.0e-6), "claude-opus-5-5": (4.0e-6, 20.0e-6)}
IN_USD, OUT_USD = PRICES[MODEL]
CAP_USD = 20.0
LEDGER = SP / "api-ledger.json"
_lock = threading.Lock()


def ledger():
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"cap_usd": CAP_USD, "spent_usd": 0.0, "reserved_usd": 0.0, "calls": []}


def reserve(worst: float, tag: str) -> bool:
    """Giữ chỗ chi phí xấu nhất trước khi gọi; từ chối nếu có thể vượt trần."""
    with _lock:
        L = ledger()
        if L["spent_usd"] + L["reserved_usd"] + worst > CAP_USD:
            return False
        L["reserved_usd"] += worst
        LEDGER.write_text(json.dumps(L, indent=1))
        return True


def settle(worst: float, usage_in: int, usage_out: int, tag: str, in_usd: float = IN_USD, out_usd: float = OUT_USD):
    with _lock:
        L = ledger()
        real = usage_in * in_usd + usage_out * out_usd
        L["reserved_usd"] = max(0.0, L["reserved_usd"] - worst)
        L["spent_usd"] += real
        L["calls"].append({"tag": tag, "in": usage_in, "out": usage_out, "usd": round(real, 4)})
        LEDGER.write_text(json.dumps(L, indent=1))


def load_key() -> str:
    for line in (Path.home() / ".clinicai-audit.env").read_text().splitlines():
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("Không thấy ANTHROPIC_API_KEY trong ~/.clinicai-audit.env")


def call(client, tag, system, user, max_tokens, effort, model=None):
    model = model or MODEL
    in_usd, out_usd = PRICES[model]
    """Một lệnh gọi có kiểm trần. Trả (text, usage) hoặc None nếu bị từ chối do trần."""
    est_in = int(len(system + user) / 2.6) + 500  # ước thận trọng (tiếng Việt + code)
    worst = est_in * in_usd + max_tokens * out_usd
    if not reserve(worst, tag):
        return None
    try:
        with client.messages.stream(
            model=model, max_tokens=max_tokens, system=system,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": user}],
        ) as s:
            msg = s.get_final_message()
        settle(worst, msg.usage.input_tokens, msg.usage.output_tokens, tag, in_usd, out_usd)
        text = "".join(b.text for b in msg.content if b.type == "text")
        return text, msg
    except Exception:
        settle(worst, 0, 0, tag + ":lỗi", in_usd, out_usd)
        raise


def extract_json(text: str):
    a = min([i for i in (text.find("{"), text.find("[")) if i >= 0])
    b = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[a : b + 1])


# ───────────────────────── Đọc chunk test ─────────────────────────
def blob(path: str) -> str:
    raw = subprocess.check_output(["git", "-C", REPO, "show", f"{SHA}:{path}"])
    text = raw.decode("utf-8", errors="replace")
    return "\n".join(f"{i}\t{l}" for i, l in enumerate(text.splitlines(), 1))


READ_SYSTEM = """Bạn là kiểm toán viên mã nguồn cho ClinicAI (phần mềm quản lý phòng khám Dr4Women: FastAPI + Next.js + Postgres tự dựng). Bạn nhận NGUYÊN VĂN một danh sách tệp (có số dòng) từ Git blob bất biến SHA 956ba4f2. Bạn không có công cụ; chỉ dựa trên nội dung được đưa. Không suy đoán ngoài bằng chứng.

Mục tiêu của chủ: phòng khám ít phụ thuộc trí nhớ cá nhân, gọi hỏi nhau, chat đuổi việc, người gánh team, chữa cháy, kiểm tra thủ công, phản ứng sau khi bệnh nhân phàn nàn. Hệ thống phải làm thực tế dễ thấy (Reality), thời gian chưa biết ngắn (Unknown), ownership rõ, phát hiện sớm, ít gián đoạn nhưng đúng lúc, bệnh nhân ít chờ trong bất định, nhân viên bền vững, quyết định có bằng chứng, lỗi lặp thành cải tiến. Mỗi phát hiện gắn 1–3 mục tiêu vào `alignment`.

Với tệp TEST, tìm: bất biến quan trọng KHÔNG có test (quyền theo bệnh nhân/cơ sở, tiền hoàn/đối soát, đồng thời/idempotency, danh sách bị cắt, lỗi tải hiển thị thành trống, backup/restore, worker/timer); test khẳng định hành vi sai hoặc kiểm sai thứ; dữ liệu/tên riêng Dr4Women ghi cứng trong fixture dùng chung; test phụ thuộc thứ tự/thời gian (flaky); khoảng trống mà các phát hiện đã biết cần test. Với tệp không phải test, tìm lỗi logic như thường lệ. Ghi cả mẫu tốt đáng nhân rộng.

Đã có các phát hiện (id, mức, tiêu đề) ở cuối; không lặp lại. Có thêm bằng chứng cho phát hiện có sẵn thì ghi vào `extensions`. Chỉ tạo phát hiện MỚI khi khác bản chất. Dùng ngôn ngữ điều kiện, không khẳng định đã xảy ra ở production. Chưa chắc thì đưa vào `held`. Tiếng Việt.

CHỈ TRẢ VỀ MỘT ĐỐI TƯỢNG JSON (không văn bản khác, không ```), đúng schema:
{"chunk": "...", "findings": [{"tmp_id": "T15-1", "title": "", "severity": "HIGH|MEDIUM|LOW", "category": "snake_case", "evidence_level": "confirmed_static|design_gap", "summary": "", "trigger": "", "impact": "", "evidence": [{"path": "", "line": 1, "end_line": 2, "detail": ""}], "limitations": "", "recommendation": "", "acceptance": "", "alignment": [""], "extends": [], "related_ids": []}], "extensions": [{"id": "SEC-011", "detail": ""}], "held": [{"title": "", "reason": ""}], "good_patterns": [{"title": "", "detail": "", "evidence": "path:line"}]}
Mỗi evidence phải có path và dòng thật nằm trong các tệp được đưa."""


def run_chunk(client, chunk: str):
    rows = [l.split("\t") for l in (SP / "lists" / f"{chunk}.tsv").read_text().splitlines()]
    parts = [f'<file path="{p}">\n{blob(p)}\n</file>' for p, _b, _s in rows]
    known = (SP / "known-findings.txt").read_text()
    user = (f"Chunk {chunk}: {len(rows)} tệp.\n\n" + "\n\n".join(parts)
            + f"\n\n<known_findings>\n{known}\n</known_findings>\n\nĐọc kỹ toàn bộ và trả JSON, chunk = \"{chunk}\".")
    out = SP / "out"
    err = "?"
    for attempt in range(2):
        try:
            r = call(client, chunk, READ_SYSTEM, user, 32000, "medium")
            if r is None:
                return chunk, False, "BỊ TỪ CHỐI: sẽ vượt trần chi tiêu"
            text, msg = r
            (out / f"{chunk}.raw.txt").write_text(text)
            data = extract_json(text)
            data["chunk"] = chunk
            data["coverage"] = [{"path": p, "lines": None, "full_read": True,
                                 "note": "Đưa nguyên văn vào một lượt đọc qua API (không tool, một lượt)."} for p, _b, _s in rows]
            (out / f"{chunk}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
            return chunk, True, f"{len(data.get('findings', []))} phát hiện, in={msg.usage.input_tokens} out={msg.usage.output_tokens} stop={msg.stop_reason}"
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:200]}"
            time.sleep(15)
    return chunk, False, err


# ───────────────────── Viết lại sang tiếng đời thường ─────────────────────
GROUPS = """A_danh_sach_cat: danh sách/báo cáo bị cắt ở một giới hạn mà màn hình không nói, hoặc lỗi tải hiển thị thành trống/0.
B_bao_xanh_gia: báo "xong/thành công/an toàn/xanh" khi chưa đúng hoặc chưa được chứng minh; trạng thái giả.
C_bam_lai_trung: bấm lại hoặc mất mạng giữa chừng tạo bản ghi/việc trùng, hoặc báo sai kết quả sau mất phản hồi.
D_ghi_de: hai người/hai tiến trình thao tác cùng lúc, người sau ghi đè người trước hoặc lệch trạng thái.
E_quyen_rong: quyền xem/sửa/chốt rộng hơn cần thiết, không theo đúng bệnh nhân/cơ sở/phân công; lộ thông tin cá nhân.
F_tien_kho: tiền thu/hoàn/nợ/giá/tồn kho/lô thuốc tính lệch hoặc khó đối soát.
G_viec_roi: việc không có người nhận, hạn, nhắc; chuyển giao mơ hồ; kết quả/tái khám có thể rơi.
H_sao_luu_van_hanh: sao lưu, khôi phục, cảnh báo, giám sát, deploy, worker, hạ tầng vận hành.
I_dong_goi_ban: dữ liệu/tên/luật riêng Dr4Women ghi cứng trong lõi, thiếu quy trình phòng khám mới, giả định một cơ sở, khó nhân bản cho khách khác.
J_luat_khong_canh: luật/chốt an toàn tồn tại nhưng thực tế không chặn được hoặc không để lại dấu vết.
K_khac: không thuộc nhóm trên (lỗi hiển thị, nhập liệu, hiệu năng...)."""

PLAIN_SYSTEM = f"""Bạn viết lại các phát hiện kiểm toán phần mềm phòng khám sang tiếng Việt ĐỜI THƯỜNG cho chủ phòng khám và quản lý không làm kỹ thuật. Không dùng thuật ngữ như idempotency, race, RLS, endpoint, transaction, payload, cap, fallback, tenant. Nói bằng việc nhân viên làm và điều bệnh nhân/phòng khám gặp. Giữ trung thực: dùng "có thể", không khẳng định đã xảy ra, không thổi phồng, không thêm chi tiết không có trong dữ liệu.

Với MỖI phát hiện, trả về:
- id (giữ nguyên)
- ten: tên ngắn dễ hiểu, tối đa 14 từ, không mã kỹ thuật
- chuyen_gi: 1–2 câu kể tình huống đời thường có thể xảy ra (ai làm gì, rồi điều gì xảy ra)
- anh_huong: 1 câu: hậu quả với bệnh nhân, tiền, hoặc công việc nhân viên
- nhom: đúng một mã trong danh sách nhóm dưới
- cach_sua: 1 câu hướng sửa dễ hiểu
- muc_do_de_hieu: "Nên xử lý sớm" nếu mức HIGH hoặc ảnh hưởng bệnh nhân/tiền rõ; "Nên xử lý trong đợt tới" nếu MEDIUM; "Có thể để sau" nếu LOW

Nhóm:
{GROUPS}

CHỈ TRẢ VỀ MỘT MẢNG JSON các đối tượng, không văn bản khác, không ```. Mỗi phát hiện đầu vào đúng một đối tượng đầu ra."""


def run_plain(client, src: Path, dst: Path, batch=20):
    items = json.loads(src.read_text())
    slim = []
    for x in items:
        slim.append({"id": x.get("id") or x.get("tmp_id"), "severity": x.get("severity"),
                     "title": x.get("title"), "summary": (x.get("summary") or "")[:900],
                     "trigger": (x.get("trigger") or "")[:400], "impact": (x.get("impact") or "")[:400]})
    batches = [slim[i : i + batch] for i in range(0, len(slim), batch)]
    results = {}

    def one(i_b):
        i, b = i_b
        user = "Các phát hiện:\n" + json.dumps(b, ensure_ascii=False)
        err = "?"
        for attempt in range(2):
            try:
                r = call(client, f"plain{i}", PLAIN_SYSTEM, user, 12000, "low")
                if r is None:
                    return i, None, "BỊ TỪ CHỐI: trần chi tiêu"
                return i, extract_json(r[0]), "ok"
            except Exception as e:  # noqa: BLE001
                err = f"{type(e).__name__}: {str(e)[:150]}"
                time.sleep(10)
        return i, None, err

    with ThreadPoolExecutor(4) as ex:
        for i, arr, info in ex.map(one, list(enumerate(batches))):
            print("plain batch", i, info, flush=True)
            for o in arr or []:
                results[o["id"]] = o
    dst.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    miss = [s["id"] for s in slim if s["id"] not in results]
    print(f"Đã viết {len(results)}/{len(slim)}; thiếu: {miss[:20]}")


# ───────────────────── Loại trùng / gộp phát hiện ─────────────────────
DEDUP_SYSTEM = """Bạn gộp các phát hiện kiểm toán trùng nhau. Đầu vào: danh sách phát hiện MỚI (tmp_id, tiêu đề, tóm tắt, đường dẫn bằng chứng) do nhiều người đọc các phần code khác nhau, và danh sách phát hiện ĐÃ CÓ (id, mức, tiêu đề). Nhiều phát hiện mới mô tả CÙNG một lỗi gốc (cùng hàm/cùng cơ chế) dù viết khác nhau.

Nhiệm vụ: nhóm các phát hiện mới cùng lỗi gốc thành một cụm. Mỗi cụm chọn `keep` là tmp_id mô tả đầy đủ nhất; các tmp_id còn lại vào `dups`. Nếu cả cụm thực chất là một phát hiện ĐÃ CÓ thì đặt `dup_of_known` = id đó (cụm sẽ được gộp thành bằng chứng bổ sung, không tạo phát hiện mới). Chỉ gộp khi chắc cùng cơ chế gốc; hai lỗi cùng khu vực nhưng khác cơ chế thì KHÔNG gộp. Mức `severity` của cụm: cao nhất trong cụm nếu bằng chứng ủng hộ, ngược lại chọn mức hợp lý. `prefix` là một trong SEC, CLIN, FIN, FE, INF, OPS, DB, API, AI, PHAR, PAT, LAB, TEST, ARCH (ARCH = kiến trúc/đóng gói bán được; TEST = khoảng trống test).

CHỈ TRẢ VỀ MỘT MẢNG JSON: [{"keep": "S01-1", "dups": ["S14-1"], "dup_of_known": null, "prefix": "SEC", "severity": "MEDIUM"}]. Mỗi tmp_id đầu vào phải xuất hiện đúng một lần (làm keep hoặc dups)."""


def run_dedup(client, src: Path, dst: Path):
    items = json.loads(src.read_text())
    known = (SP / "known-findings.txt").read_text()
    slim = [{"id": x["tmp_id"], "sev": x.get("severity"), "t": x.get("title"),
             "s": (x.get("summary") or "")[:260],
             "p": sorted({e.get("path") for e in (x.get("evidence") or []) if e.get("path")})[:3]} for x in items]
    user = "Phát hiện MỚI:\n" + json.dumps(slim, ensure_ascii=False) + "\n\nPhát hiện ĐÃ CÓ:\n" + known
    r = call(client, "dedup", DEDUP_SYSTEM, user, 40000, "medium")
    if r is None:
        sys.exit("Bị từ chối do trần chi tiêu")
    arr = extract_json(r[0])
    dst.write_text(json.dumps(arr, ensure_ascii=False, indent=1))
    seen = [i for c in arr for i in [c["keep"], *c.get("dups", [])]]
    miss = [x["tmp_id"] for x in items if x["tmp_id"] not in seen]
    print(f"cụm: {len(arr)}; tổng id đầu vào {len(items)}; thiếu {len(miss)}: {miss[:10]}; trùng lặp: {len(seen)-len(set(seen))}")


# ───────────────── Đối chiếu thực tế prod ─────────────────
PROD_SYSTEM = """Bạn là kiểm toán viên. Đầu vào: (1) kết quả đo THỰC TẾ trên VPS prod đang phục vụ khách (lệnh chỉ đọc, ngày 20/10/2026), (2) danh sách 545 vấn đề phát hiện khi đọc code bản prod (id, mức, tiêu đề), (3) 10 mục tiêu của chủ phòng khám. Nhiệm vụ: dùng CHỈ dữ kiện đo được để (a) xác nhận mục nào trong 545 mục có dấu hiệu thật trên prod, (b) chỉ ra mục nào bị phủ nhận hoặc giảm nhẹ bởi dữ kiện đo, (c) ghi các quan sát MỚI chỉ thấy trên prod, (d) đánh giá hiện trạng từng mục tiêu.

Quy tắc: không bịa. Mỗi kết luận phải trích đúng một dòng dữ kiện (nguyên văn ngắn) làm bằng chứng. Mục nào dữ kiện không đụng tới thì KHÔNG đưa vào. Dùng "có dấu hiệu", không khẳng định quá dữ kiện. Tiếng Việt đời thường cho chủ phòng khám; thuật ngữ kỹ thuật tối thiểu.

CHỈ TRẢ VỀ MỘT ĐỐI TƯỢNG JSON, không văn bản khác:
{"xac_nhan": [{"id": "INF-006", "bang_chung": "dòng dữ kiện", "y_nghia": "1 câu"}],
 "phu_nhan_hoac_giam_nhe": [{"id": "SEC-038", "bang_chung": "dòng dữ kiện", "y_nghia": "1 câu"}],
 "quan_sat_moi": [{"ten": "", "muc": "HIGH|MEDIUM|LOW", "chuyen_gi": "2 câu đời thường", "bang_chung": "dòng dữ kiện", "cach_sua": "1 câu", "muc_tieu": ["tên mục tiêu"]}],
 "muc_tieu": [{"ten": "đúng tên mục tiêu được đưa", "trang_thai": "Có nền|Còn hở|Chưa đo được|Chưa sẵn sàng", "thuc_te_prod": "1–2 câu dựa trên dữ kiện đo, hoặc 'chưa có dữ kiện'"}],
 "khoe_manh": ["3–6 điều đo được là tốt, mỗi điều 1 câu kèm số"]}"""


def run_prod(client, out: Path):
    facts = "\n\n".join((SP / "out" / f).read_text() for f in ("vps-facts.txt", "vps-facts2.txt"))
    items = json.loads(Path("/Users/quangdang/Projects/Dr4Women-MacMini/.claude/worktrees/clever-thompson-45b9eb/docs/kiem-toan-2026-10-19/PHAT-HIEN.json").read_text())
    new = json.loads((SP / "out" / "new-final.json").read_text())
    lst = [f"{x['id']} [{x.get('severity')}] {x.get('title')}" for x in items + new]
    goals = (SP / "goals.txt").read_text()
    user = "DỮ KIỆN ĐO TRÊN PROD:\n" + facts + "\n\nCÁC VẤN ĐỀ (" + str(len(lst)) + "):\n" + "\n".join(lst) + "\n\nCÁC MỤC TIÊU:\n" + goals
    r = call(client, "prod", PROD_SYSTEM, user, 24000, "high", model="claude-opus-5-5")
    if r is None:
        sys.exit("Bị từ chối do trần chi tiêu")
    text, msg = r
    (SP / "out" / "prod-analysis.raw.txt").write_text(text)
    data = extract_json(text)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print("xac_nhan", len(data.get("xac_nhan", [])), "phu_nhan", len(data.get("phu_nhan_hoac_giam_nhe", [])), "moi", len(data.get("quan_sat_moi", [])), "muc_tieu", len(data.get("muc_tieu", [])), f"in={msg.usage.input_tokens} out={msg.usage.output_tokens}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", nargs="*")
    ap.add_argument("--plain", nargs=2, metavar=("NGUON.json", "DICH.json"))
    ap.add_argument("--dedup", nargs=2, metavar=("NGUON.json", "DICH.json"))
    ap.add_argument("--prod", action="store_true")
    ap.add_argument("--ledger", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.ledger:
        L = ledger()
        print(f"Đã chi {L['spent_usd']:.2f} USD, đang giữ chỗ {L['reserved_usd']:.2f}, trần {L.get('cap_usd', CAP_USD)} USD, {len(L['calls'])} lệnh gọi")
        return
    client = anthropic.Anthropic(api_key=load_key(), max_retries=4, timeout=1800)
    if a.plain:
        run_plain(client, Path(a.plain[0]), Path(a.plain[1]))
    if a.prod:
        run_prod(client, SP / "out" / "prod-analysis.json")
    if a.dedup:
        run_dedup(client, Path(a.dedup[0]), Path(a.dedup[1]))
    if a.run:
        with ThreadPoolExecutor(a.workers) as ex:
            for chunk, ok, info in ex.map(lambda c: run_chunk(client, c), a.run):
                print(chunk, "OK" if ok else "LỖI", info, flush=True)
    L = ledger()
    print(f"[sổ] đã chi {L['spent_usd']:.2f} USD / trần {CAP_USD} USD")


if __name__ == "__main__":
    main()
