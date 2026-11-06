# KẾ HOẠCH — Trợ lý AI trả lời khách (bản thử trên khung chat giả lập)

Mức 3 (hạ tầng gọi AI bên ngoài + bảng mới). Soạn 30/10/2026.

**Trạng thái:** Tuyền chốt dữ liệu thử = **(a) staging đã che** (30/10). PR1 (bộ não,
chạy bằng script) đã làm; PR2 (bảng + màn) chưa. Các câu 2–4 dưới chưa chốt —
PR1 tạm dùng: Claude + adapter OpenAI-compatible, xưng "em"/gọi "chị", trần 2 USD.

Chạy chấm (cần khoá, xem `adapters/mo_hinh/__init__.py`):

    .venv/bin/python scripts/cham-tro-ly.py --mo-hinh anthropic:claude-haiku-5-5 --gioi-han 10

## Mục tiêu

Một "bộ não" trả lời tin nhắn khách, **cắm model nào cũng chạy** (Claude, GPT,
Gemini, model mở chạy tại chỗ), thử trên một màn chat giả lập trong ClinicAI.
Khi có Zalo OA / Messenger thì chỉ thêm một adapter kênh, bộ não không đổi.

## Nền đã có trong repo (dùng lại, không viết lại)

| Có sẵn | Ở đâu | Dùng thế nào |
|---|---|---|
| Client Anthropic: retry, prompt cache, ghi token + USD, **trần tiền ngày** | `llm/anthropic_client.py`, `llm/chi_phi.py`, bảng `llm_lan_goi` | thành adapter đầu tiên; mọi adapter đều ghi `llm_lan_goi` |
| Khuôn port/adapter | `ports/pos.py` + `adapters/pos/` (ADR-0010) | chép khuôn cho `ports/mo_hinh.py` và `ports/kenh_chat.py` |
| Tool registry xuất schema cho Claude | `tools/registry.py`, `tools/scheduling/*`, `tools/kb/read_policy.py` | lấy tool đọc lịch trống / chính sách; thêm đổi schema sang dạng OpenAI |
| Khoá AI tách bằng tệp secret | `services/agent_tom_tat.py` | khoá riêng cho trợ lý, **không** dùng `ANTHROPIC_API_KEY` (biến đó bật AI phân loại xét nghiệm) |
| Orchestrator LangGraph | `orchestrator/` (tắt ở prod, gắn chặt với Anthropic) | **không dùng.** Vòng lặp gọi tool viết thẳng (~150 dòng), dễ đọc, không phụ thuộc hãng. Lịch sử hội thoại lưu ở bảng của mình, không cần checkpointer |

`llm/models.py` (Sonnet 4.6 / Haiku 4.5) để nguyên: AI phân loại xét nghiệm gửi
`temperature=0.2`, đời 5.5 trả 400 với tham số đó. Trợ lý chọn model riêng qua cấu hình
của nó, không đi qua `tier`.

## Thiết kế

```
Kênh (giả lập | Zalo OA sau | Messenger sau)
   │  tin vào chuẩn hoá: {kenh, ma_hoi_thoai, noi_dung}
   ▼
Bộ não  services/tro_ly_khach.py
   1. Chặn bằng CODE trước khi gọi AI (từ khoá khẩn: ra máu, đau dữ dội, ngất…;
      hỏi chẩn đoán / liều thuốc)  → trả câu cố định + "chuyển người", dừng
   2. Nạp memory: N tin gần nhất của hội thoại + tóm tắt hội thoại cũ
   3. Vòng lặp: model ⇄ tool (tối đa 5 vòng). Tool CHỈ ĐỌC:
      giờ mở cửa · danh sách dịch vụ + giá · lịch trống theo ngày/bác sĩ · chính sách
   4. Đặt lịch = tạo ĐỀ XUẤT nháp, không ghi lịch thật
   5. Kết quả = NHÁP + lý do; người bấm Duyệt / Sửa / Chuyển người
   ▼
Port mô hình  ports/mo_hinh.py   ← một hàm: tra_loi(he_thong, tin, tools) → {chu, goi_tool[], token}
   ├─ adapters/mo_hinh/anthropic.py      (bọc client có sẵn)
   └─ adapters/mo_hinh/openai_compat.py  (một adapter dùng cho OpenAI, Gemini qua cổng tương thích,
                                          DeepSeek/Qwen, và Ollama/vLLM chạy tại chỗ — gọi bằng httpx, không thêm thư viện)
```

Chọn model bằng cấu hình theo **vai**: `phan_loai`, `tra_loi`, `tom_tat`. Mỗi vai một
cặp (adapter, model), đổi được không cần deploy lại code.

**"Thông minh" đo bằng số, không bằng cảm giác:**
- Bộ câu vàng `src/tests/tro_ly/cau_vang.yaml`, 60–100 tin mẫu viết theo giọng khách thật
  (không dấu, viết tắt, hỏi dồn), mỗi câu có đáp án: ý định đúng, tool phải gọi,
  câu bắt buộc chuyển người.
- `scripts/cham-tro-ly.py --model …` chấm và in bảng: % đúng ý định, % gọi đúng tool,
  % chặn đúng câu khẩn (phải 100%), token, tiền, độ trễ. **So các model trên cùng một bảng.**
- Mỗi câu AI trả lời đều lưu model, prompt (phiên bản), tool đã gọi, `lan_goi_id`, để trả lời được câu "sao AI nói vậy".

## Dữ liệu (cần Tuyền + Quang quyết, xem mục cuối)

Bảng mới (một migration, dải giờ riêng):
- `tro_ly_hoi_thoai` (kênh, mã người gửi ngoài, trạng thái, tóm tắt)
- `tro_ly_tin` (vai, nội dung, model, tool gọi, `lan_goi_id`, nháp/đã duyệt/đã sửa, người duyệt)

Màn `/tro-ly-thu` (quyền `ops.view`, chỉ hiện khi bật cờ): bên trái là khung chat đóng vai khách,
bên phải là "bên trong": ý định, tool đã gọi kèm kết quả, model, token, tiền, nháp + 3 nút.
Không mang logo hay màu của Zalo.

## Chia PR (mỗi PR ≤ ~400 dòng, không tính test/migration)

1. **PR1 backend:** port mô hình + 2 adapter + vòng lặp + luật chặn + 4 tool đọc + bộ câu vàng + script chấm. Chưa có bảng, chưa có màn; chạy được bằng script.
2. **PR2:** migration 2 bảng + API hội thoại + màn `/tro-ly-thu`, bấm thật 375/1280.
3. (sau, khi có OA) adapter `kenh_chat/zalo_oa.py` nhận webhook.

## KHÔNG làm trong đợt này

Nối Zalo/Facebook thật · tự gửi tin không qua người duyệt · tư vấn chẩn đoán/thuốc ·
ghi lịch thật · ảnh/voice/sticker · đọc phiếu khám, kết quả xét nghiệm.

## Tuyền / Quang quyết trước khi làm

1. **Dữ liệu thử** (xem lý do ở câu trả lời trong phiên):
   - (a) **staging đã che** + `DEMO-*` gửi lên AI cloud. *Khuyên dùng:* đúng phân bố thật, không lộ ai.
   - (b) dữ liệu thật **chỉ với model chạy tại chỗ trên Mac** (Ollama, máy M4 Pro 48 GB), dữ liệu không rời máy. Chậm hơn và kém thông minh hơn model cloud.
   - (c) dữ liệu thật gửi lên AI cloud: **không khuyên.** Trái với tiền lệ repo (bỏ Sentry, xử lý audio tại chỗ — NĐ 13/2023), phải có đồng ý của từng khách + hồ sơ chuyển dữ liệu ra nước ngoài. Phòng khám đồng ý không thay được đồng ý của khách.
2. **Model so ở đợt đầu:** Claude (Haiku/Sonnet 5.5) + một hãng nữa (OpenAI? Gemini?) + một model mở chạy tại chỗ? Cần khoá API của hãng nào thì Tuyền tự tạo, đặt vào tệp secret.
3. **Giọng:** xưng "em", gọi khách "chị"? Câu chào và câu chuyển người do ai viết?
4. **Trần tiền:** giữ `LLM_TRAN_NGAY_USD=2` hay nâng riêng cho đợt thử?
