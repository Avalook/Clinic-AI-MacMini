# Nhóm D — Công nghệ và chi phí để xây AI cho phòng khám Việt Nam, xu hướng giá

Ngày nghiên cứu: 20/10/2026. Người làm: agent nghiên cứu nhóm D.
Ký hiệu loại nguồn: **(ĐL)** độc lập (nghiên cứu, viện nghiên cứu, bảng xếp hạng cộng đồng có phương pháp) · **(NCC)** công bố của nhà cung cấp, kể cả bảng giá · **(BC)** báo chí, blog bên thứ ba · **(BL)** nhà bán lẻ niêm yết giá.
Nguồn có dấu **†** chỉ đọc qua phần tóm tắt của công cụ tìm kiếm, chưa mở được trang gốc. Cần kiểm lại trước khi dùng số đó để ra quyết định.

Tỷ giá dùng xuyên suốt: **1 USD ≈ 26.400 VND**. Đây là giả định làm tròn từ giá bán ra của Vietcombank ngày 02/07/2026 là 26.465 [43†]. Không tìm được tỷ giá tháng 10/2026.

---

## 1. Tóm tắt 7 ý quan trọng nhất

1. **Nhận dạng giọng nói tiếng Việt thông thường đã khá tốt, nhưng với hội thoại y khoa thì vẫn kém.** Theo số tác giả tự công bố, PhoWhisper-large đạt WER 4,7% trên VIVOS và 8,1% trên Common Voice. Trên lời nói tự nhiên có nhiễu (VLSP 2020 Task-2), WER lên 26,7% [1][2]. Trên dữ liệu y khoa tiếng Việt (VietMed, MultiMed), mô hình tốt nhất công bố vẫn có WER khoảng 27–30% [5][6][7]. Không tìm được ai đo các API thương mại (FPT, Viettel, Google, OpenAI) trên tiếng Việt y khoa. Hệ quả: ghi âm bác sĩ (voice scribe) phải có bác sĩ duyệt lại bản nháp, không được ghi thẳng vào hồ sơ.
2. **Giá chép lời qua API đã rất thấp.** OpenAI tính 0,003–0,006 USD/phút [16], tức khoảng 80–160 VND/phút. Google xử lý theo lô (Chirp, V2) 0,003 USD/phút [13†]. FPT.AI tính 540–700 VND/phút theo gói [9]. Một lượt khám 10 phút tốn chừng 0,8–7 nghìn VND tiền chép lời, tùy nhà cung cấp.
3. **Ở cùng một mức năng lực, giá LLM giảm khoảng 13 lần mỗi năm** (47%/quý từ 2023). Đây là số của Epoch AI công bố 22/09/2026 [22]. Các ước tính trước đó: a16z khoảng 10 lần/năm (11/2024) [20], Epoch 9–900 lần/năm tùy mốc (03/2025) [21]. Riêng mức năng lực vừa mới đạt đỉnh thì giá rơi nhanh nhất, khoảng 66%/quý. Hai năm sau tốc độ chỉ còn khoảng 32%/quý [22].
4. **Giá của gói mô hình đầu bảng không giảm, và có gói đang tăng giá.** Mô hình đắt nhất của Anthropic và OpenAI hôm nay vẫn ở mức 10 USD vào / 50 USD ra cho mỗi triệu token [17][16]. Dòng Gemini Flash đi từ 0,30/2,50 USD (2.5 Flash) lên 0,75/3,75 USD (3.6–3.8 Flash), và sẽ **tăng gấp đôi lên 1,50/7,50 USD từ 01/01/2027** [18]. "Rẻ đi" là rẻ đi ở *năng lực cũ*, không phải ở *tên gói*.
5. **Các tác vụ phòng khám tốn rất ít tiền mỗi lần gọi API.** Với giá công bố hôm nay và giả định ở mục 2.3: soạn 1 tin nhắn tốn khoảng 8–320 VND; tóm tắt 1 hồ sơ khoảng 50–1.900 VND; đọc 1 PDF kết quả 3–4 trang khoảng 40–2.700 VND. Một kịch bản 3.000 lượt khám/tháng tốn khoảng 0,4 triệu VND/tháng với Haiku 5.5, hoặc 7,8 triệu với Sonnet 5.5.
6. **Phần cứng tự chạy đang lên giá chứ không xuống.** RTX 5090 tại Phong Vũ ngày 20/10/2026 niêm yết 154–200 triệu VND [36], trong khi giá đề xuất lúc ra mắt là 1.999 USD (khoảng 53 triệu) [45†]. Nguyên nhân được báo là thiếu bộ nhớ DRAM/GDDR do nhu cầu AI [37†][38†]. Mac Studio M5 Max 36GB có giá khoảng 68–70 triệu VND [39]. Tự chạy LLM gần như không bao giờ hoàn vốn so với API ở quy mô một phòng khám. Tự chạy nhận dạng giọng nói (PhoWhisper) chỉ hoàn vốn được khi so với giá FPT.AI, không hoàn vốn khi so với giá OpenAI hay Google.
7. **Hàm ý:** thuê qua API các năng lực đã thành hàng phổ thông (chép lời, đọc PDF, sinh chữ, gọi điện). **Tự xây** lớp luồng việc, dữ liệu, bộ chấm đúng/sai tiếng Việt y khoa, và một lớp chuyển đổi nhà cung cấp. Rủi ro phụ thuộc là có thật: giá tăng theo lịch (Gemini Flash) [18], tên mô hình bị đổi hoặc ngừng [19], thêm phí xử lý theo vùng [16], và giá dịch vụ trong nước không công khai [34][35].

---

## 2. Chi tiết

### 2.1. Nhận dạng giọng nói tiếng Việt (ASR)

**a) Độ chính xác công bố (WER thấp hơn là tốt hơn)**

| Mô hình / hệ thống | Kết quả | Nguồn |
|---|---|---|
| PhoWhisper-large (VinAI, 1,55 tỷ tham số) | WER 8,14% Common Voice-vi · 4,67% VIVOS · 13,75% VLSP2020-T1 · **26,68% VLSP2020-T2 (lời nói tự nhiên, nhiễu)** | [1][2] (ĐL, nghiên cứu nhưng do tác giả tự đo) |
| PhoWhisper-medium (769 triệu tham số) | 8,27 · 4,97 · 14,12 · 26,85 — gần bằng bản large mà chỉ nặng một nửa | [1] (ĐL, tác giả tự đo) |
| PhoWhisper: dữ liệu huấn luyện | Tinh chỉnh trên 844 giờ tiếng Việt nhiều giọng vùng miền | [2] (ĐL) |
| Whisper large-v3 (OpenAI), chưa tinh chỉnh | WER 13,74% Common Voice · 8,59% FLEURS · 17,94% GigaSpeech2 (theo bảng của bài VietASR) | [4] (ĐL) |
| VietASR (Interspeech 2025) | Huấn luyện trước trên khoảng 70.000 giờ chưa gán nhãn và tinh chỉnh với 50 giờ có nhãn. Tác giả nói vượt Whisper large-v3 và "các hệ thống ASR thương mại" trên dữ liệu thực, nhưng tóm tắt không nêu tên hệ thống thương mại | [4] (ĐL) |
| Bảng xếp hạng Vietnamese Open ASR (cộng đồng) | Hạng 1 PhoWhisper-medium: O-WER trung bình 16,73. Hạng 2 Zipformer-30M-RNNT (chỉ 30 triệu tham số): 17,51. Qwen3-ASR-1.7B: 18,76. Không có API thương mại nào trong bảng. Trang không định nghĩa O-WER/N-WER và không ghi ngày | [3] (ĐL, cộng đồng, phương pháp chưa rõ) |
| **Y khoa:** VietMed (16 giờ có nhãn) | Mô hình tốt nhất (XLSR-53-Viet) đạt **WER 29,6%** trên tập test | [5] (ĐL) |
| **Y khoa:** MultiMed (ACL 2025) | wav2vec2 tinh chỉnh tiếng Việt đạt WER 28,8–29,0% | [6] (ĐL) |
| **Y khoa:** MultiMed-ST (2025) | Whisper-small đơn ngữ dùng làm khâu chép lời: WER tiếng Việt 29,6% | [7] (ĐL) |
| Đo các API thương mại trên tiếng Việt y khoa | **Không tìm được nguồn.** Dự án MedVoice (sinh viên RMIT, 02/2025) nói đã tối ưu cho thuật ngữ y khoa nhưng không công bố WER | [44†] (BC) |

Nhận xét của người viết: WER khoảng 27–30% nghĩa là cứ 10 từ thì sai khoảng 3. Những con số này đo trên mô hình nghiên cứu cỡ nhỏ và dữ liệu y khoa có ít giờ gán nhãn. Chúng không cho biết API thương mại năm 2026 làm tốt đến đâu. Muốn biết thì phải tự đo trên ghi âm thật của phòng khám (xem mục 2.5).

**b) Giá theo phút và khả năng tự chạy**

| Nhà cung cấp | Giá công bố | Hỗ trợ tiếng Việt | Tự chạy được? | Nguồn |
|---|---|---|---|---|
| OpenAI gpt-4o-mini-transcribe | 0,003 USD/phút (≈ 79 VND) | Có, theo người viết biết; trang giá không nêu từng ngôn ngữ | Không | [16] (NCC, truy cập 20/10/2026) |
| OpenAI gpt-4o-transcribe / whisper | 0,006 USD/phút (≈ 158 VND) | Có | Mô hình Whisper mã nguồn mở thì tự chạy được | [16][8] (NCC) |
| Google Cloud STT V2 – Chirp 3 | Theo lô động 0,003 USD/phút. Thời gian thực 0,016 USD/phút cho 500.000 phút đầu | vi-VN **GA**. Tách người nói (diarization) có thể chưa hỗ trợ tiếng Việt | Không | [12] (NCC) · giá [13†] (NCC) |
| Azure Speech | Lô 0,18 USD/giờ (= 0,003 USD/phút). Thời gian thực 1,60 USD/giờ | Không kiểm được | Không | [15] (NCC đối thủ tự so sánh, cập nhật 23/09/2026). Trang giá Azure hiện ô trống |
| AWS Transcribe | Có vi-VN cho cả lô lẫn luồng (từ 12/2022). Giá bậc 1 khoảng 0,024 USD/phút theo các trang bên thứ ba, chưa kiểm được trên trang AWS | Có | Không | [14] (NCC) · giá: không tìm được nguồn đáng tin |
| FPT.AI Speech-to-Text | Dùng thử 60 phút/năm. Gói 2.000 phút giá 1,4 triệu VND (700 VND/phút). 5.000 phút: 3,1 triệu (620/phút). 10.000 phút: 5,4 triệu (**540 VND/phút**). Trên 10.000 phút thì liên hệ | Có (sản phẩm trong nước) | Trang giá không nhắc tới tự chạy | [9] (NCC, ghi bản quyền 2025, truy cập 20/10/2026) |
| Viettel AI Speech-to-Text | **Không tìm được bảng giá công khai.** Trang sản phẩm không đọc được nội dung. 04/2026 Viettel Telecom ký hợp tác với iFLYTEK (Trung Quốc) về STT/TTS, triển khai trên hạ tầng Viettel | Có | Không rõ | [10] (NCC) · [11†] (BC, 10/04/2026) |
| Zalo AI | **Không tìm được API STT công khai.** Chỉ thấy thư viện TTS do cộng đồng viết | — | — | không tìm được nguồn đáng tin |
| Soniox / ElevenLabs / Deepgram / AssemblyAI | Lô 0,10–0,39 USD/giờ. Thời gian thực 0,12–0,75 USD/giờ | Không kiểm từng hãng | Không | [15] (NCC đối thủ) |

**c) Phần cứng để tự chạy mô hình cỡ medium/large**

- Theo bảng trong README của Whisper: medium (769 triệu tham số) cần khoảng 5 GB VRAM; large (1,55 tỷ) khoảng 10 GB; turbo (809 triệu) khoảng 6 GB [8] (NCC). PhoWhisper dùng cùng kiến trúc và cùng cỡ tham số [1]. Từ đó người viết suy ra yêu cầu VRAM tương đương; điều này **chưa được đo**.
- Zipformer-30M đứng hạng 2 trên bảng xếp hạng cộng đồng với chỉ 30 triệu tham số [3]. Người viết ước tính mô hình cỡ này chạy được trên CPU, nhưng chưa kiểm.
- Giấy phép: PhoWhisper ghi Apache-2.0 trên GitHub, còn trang Hugging Face của bản large ghi BSD-3-Clause (theo tóm tắt tìm kiếm). Cần đối chiếu trước khi dùng thương mại [1].

**d) Voice agent gọi điện (đặt lịch, nhắc lịch bằng giọng nói)**

| Nền tảng | Giá/phút | Ghi chú | Nguồn |
|---|---|---|---|
| Retell AI | 0,07–0,31 USD. Triển khai thực tế khoảng 0,13–0,15 USD | Gồm hạ tầng giọng 0,055 + TTS 0,015 + LLM + cước gọi khoảng 0,015 | [31†] (BC, blog bên thứ ba, một số là đối thủ) |
| Vapi | Phí nền tảng 0,05 USD. Tổng thực tế 0,08–0,33 USD | STT/LLM/TTS tính riêng theo giá gốc của từng hãng | [32†] (BC, 30/07/2026) |
| ElevenLabs Agents | 0,08 USD + LLM + cước gọi | Không nguồn nào xác nhận hỗ trợ tiếng Việt | [33†] (BC) |
| OpenAI Realtime | gpt-realtime-2.1-mini: 10 USD vào / 20 USD ra cho mỗi triệu token âm thanh | Không quy đổi được ra phút vì thiếu số token/phút | [16] (NCC) |
| FPT AI Engage (voicebot) | **Không có giá công khai** | NCC nói hiểu đúng ngôn ngữ 92%. Home Credit thực hiện hơn 5 triệu cuộc gọi/tháng, tiết kiệm 50% chi phí vận hành (số của NCC) | [34†] (NCC) |
| Viettel Cyberbot (callbot) | **Không có giá công khai** | Hỗ trợ giọng Bắc và giọng Nam. Một triển khai: 95.000 cuộc gọi thành công trong 4 tháng, tiết kiệm 67 triệu VND/tháng tiền nhân sự (số NCC đưa qua báo) | [35†] (BC đưa lại số NCC) |

Ví dụ tính tay (giả định của người viết): một cuộc gọi đặt lịch dài 3 phút, giá 0,15 USD/phút thì tốn khoảng 0,45 USD, tức khoảng 11.900 VND. Chưa có nguồn đo chất lượng tiếng Việt của các nền tảng quốc tế này.

### 2.2. Giá mô hình ngôn ngữ lớn, 2023 → 2026

**a) Xu hướng (nguồn độc lập và phân tích)**

| Phát hiện | Nguồn |
|---|---|
| Ở cùng mức năng lực, chi phí giảm khoảng **47%/quý, tức khoảng 13 lần/năm** từ 2023, đo trên 5 bộ benchmark (AIME, Chess Puzzles, FrontierMath, GPQA Diamond, Mystery Game Puzzles). Đo bằng *chi phí để đạt một điểm số*, có tính token suy luận, chứ không chỉ giá mỗi token | [22] (ĐL, Epoch AI, 22/09/2026) |
| Mức năng lực vừa mới đạt đỉnh: giá rơi khoảng 66%/quý (75 lần/năm). Hai năm sau chỉ còn khoảng 32%/quý (4,7 lần/năm). Toán rơi nhanh (50–52%/quý), câu đố trò chơi chậm hơn (39–43%/quý) | [22] (ĐL) |
| Lưu ý của chính Epoch: benchmark có thể bị "học tủ"; điểm benchmark không bằng việc hữu ích; người dùng thực tế không luôn chuyển sang mô hình rẻ nhất nên khoản tiết kiệm thật nhỏ hơn; dữ liệu mới có khoảng 3 năm; nhu cầu AI đang đẩy giá chip và điện lên | [22] (ĐL) |
| Bản trước của Epoch: tùy mốc năng lực, giá giảm 9–900 lần/năm. Để đạt mức GPT-4 trên GPQA Diamond, giá giảm 40 lần/năm. Ví dụ MMLU 86: GPT-4-0314 (03/2023) 37,50 USD/triệu token so với Gemini 2.0 Flash (02/2025) 0,18 USD | [21] (ĐL, Epoch AI, 12/03/2025) |
| "LLMflation": cùng năng lực thì giá giảm khoảng 10 lần/năm. GPT-3 (11/2021) 60 USD/triệu token so với Llama 3.2 3B (11/2024) 0,06 USD, tức giảm khoảng 1.000 lần trong 3 năm. Tác giả lưu ý gói đầu bảng không đua giá thấp (o1 có giá ra bằng GPT-3 lúc ra mắt) | [20] (phân tích của quỹ đầu tư a16z, 12/11/2024 — không phải nghiên cứu bình duyệt) |

**b) Giá công bố hiện hành (USD/triệu token, vào / ra)**

| Hãng | Mô hình | Vào / Ra | Ghi chú | Nguồn |
|---|---|---|---|---|
| Anthropic | Fable 5.1 | 10 / 50 | Gói đầu bảng | [17] (NCC, truy cập 20/10/2026; trang không ghi ngày) |
| | Opus 5.5 | 4 / 20 | | [17] |
| | Sonnet 5.5 | 2 / 10 | | [17] |
| | Haiku 5.5 (prompt ≤100K token) | **0,10 / 0,50** | Prompt trên 100K token: 0,50 / 2,50 | [17] |
| | Chạy theo lô (batch) | −50% | Đọc cache rẻ khoảng 10–20 lần so với giá vào thường | [17] |
| OpenAI | gpt-6-astra | 10 / 50 | Gói đầu bảng | [16] (NCC, truy cập 20/10/2026) |
| | gpt-6.1-sol / gpt-6-sol | 2 / 10 | | [16] |
| | gpt-6-luna | 0,10 / 0,50 | Gói nhỏ | [16] |
| | Xử lý theo vùng (data residency) | +10% | Áp cho các mô hình phát hành từ 05/03/2026 | [16] |
| Google | Gemini 3.1 Pro Preview | 2 / 12 (≤200K) | | [18] (NCC, cập nhật 19/10/2026) |
| | Gemini 3.6 / 3.8 Flash | 0,75 / 3,75 đến hết 2026 → **1,50 / 7,50 từ 01/01/2027** | Tăng giá theo lịch đã định | [18] (NCC) · [23†] (BC) |
| | Gemini 2.5 Flash / 3.1 Flash-Lite / 2.5 Flash-Lite | 0,30/2,50 · 0,25/1,50 · 0,10/0,40 | | [18] |
| DeepSeek | deepseek-flash (V4.1) | 0,30 / 1,20 giờ cao điểm. Ngoài giờ cao điểm: 0,15 / 0,60 | Giờ cao điểm tính theo UTC trong tuần. Tên mô hình cũ được chuyển sang mô hình mới | [19] (NCC, ©2026, trang không ghi ngày áp dụng) |
| | deepseek-v4-pro | 1,32 / 3,96 giờ cao điểm | | [19] |
| Mô hình mở trên dịch vụ bên thứ ba | Llama 3.3 70B khoảng 0,88/0,88. Qwen3 32B khoảng 0,10/0,44. Qwen 3.6 Plus khoảng 0,50/3,00 | Các trang tổng hợp ghi số khác nhau | (BC, trang tổng hợp giá; độ tin thấp) |

**Đọc bảng.** So sánh của người viết, không cùng phương pháp với Epoch: GPT-4 (03/2023) có giá trung bình khoảng 37,5 USD/triệu token [21]; gói nhỏ hôm nay là 0,10/0,50 USD [17][16]. Gói đầu bảng thì đứng yên ở khoảng 10/50 USD [17][16]. Một "dòng" mô hình có thể tăng giá khi đời mới mạnh hơn (Gemini Flash) [18].

### 2.3. Chi phí ước tính cho từng tác vụ, theo giá công bố ngày 20/10/2026

**Giả định (của người viết, chưa đo trên dữ liệu ClinicAI):**
- PDF kết quả: trung bình 3,5 trang. Với Claude, mỗi trang tốn 1.500–3.000 token chữ [24] cộng ảnh trang. Ảnh trang tốn khoảng 1.500 token ở độ phân giải thường, tối đa khoảng 4.800 token ở độ phân giải cao cho các mô hình từ Claude 4.7 trở đi [25]. Người viết **lấy 6.000 token/trang** làm mức trung bình hơi cao. Với Gemini, mỗi trang PDF khoảng 258 token [26].
- Thêm 500 token chỉ dẫn. Đầu ra 800 token (JSON có cấu trúc).
- Tóm tắt hồ sơ: đầu vào 15.000 token (nhiều lượt khám, xét nghiệm dạng chữ), đầu ra 600 token.
- Soạn tin nhắn: đầu vào 2.000 token, đầu ra 200 token.
- Không tính token suy luận (thinking). Nếu mô hình suy luận thêm 2.000 token ra, Sonnet tốn thêm khoảng 0,02 USD (530 VND) mỗi lần.
- Không tính giảm giá do cache hay chạy theo lô. Chạy theo lô giảm 50% [17].

| Tác vụ | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | Khác |
|---|---|---|---|---|
| Đọc 1 PDF 3,5 trang (21.500 vào / 800 ra) | 0,0026 USD ≈ **67 VND** | 0,051 USD ≈ **1.350 VND** | 0,102 USD ≈ **2.690 VND** | Gemini 3.1 Flash-Lite (1.403 vào): ≈ 0,0016 USD ≈ **41 VND**. Gemini 3.8 Flash: ≈ 107 VND (giá 2026), ≈ 214 VND (giá 2027) |
| Tóm tắt 1 hồ sơ (15.000 / 600) | 0,0018 USD ≈ **48 VND** | 0,036 USD ≈ **950 VND** | 0,072 USD ≈ **1.900 VND** | gpt-6-luna ≈ 48 VND. DeepSeek flash (giờ cao điểm) ≈ 138 VND. Gemini 3.1 Pro ≈ 980 VND |
| Soạn 1 tin nhắn (2.000 / 200) | 0,0003 USD ≈ **8 VND** | 0,006 USD ≈ **158 VND** | 0,012 USD ≈ **317 VND** | |

Nguồn giá: [17][18][16][19].

**Kịch bản tháng (giả định, không phải số đo của Dr4Women):** 3.000 lượt khám/tháng; mỗi lượt có 1 tóm tắt, 1 PDF và 2 tin nhắn.
- Haiku 5.5: khoảng 15 USD, tức **≈ 0,4 triệu VND/tháng**.
- Sonnet 5.5: khoảng 297 USD, tức **≈ 7,8 triệu VND/tháng**.
- Opus 5.5: khoảng 594 USD, tức ≈ 15,7 triệu VND/tháng.

**Ghi âm bác sĩ (voice scribe), giả định 10 phút ghi âm mỗi lượt:**
- Tiền chép lời mỗi lượt: OpenAI mini 0,03 USD (≈ 790 VND); Google lô / Azure lô khoảng 790 VND; FPT.AI gói 10.000 phút 5.400 VND; FPT.AI gói 2.000 phút 7.000 VND [16][13†][15][9].
- Dựng thành phiếu khám có cấu trúc. Giả định 6.000 token vào (bản chép lời tiếng Việt; người viết ước tính tiếng Việt tốn token hơn tiếng Anh) và 1.000 token ra. Sonnet tốn khoảng 580 VND; Haiku khoảng 29 VND [17].
- Theo tháng (3.000 lượt × 10 phút = 30.000 phút): FPT.AI ≈ 16,2 triệu VND; OpenAI mini ≈ 2,4 triệu VND; thêm Sonnet để dựng phiếu ≈ 1,7 triệu VND.

### 2.4. Đọc tài liệu / OCR tiếng Việt

| Hạng mục | Thông tin | Nguồn |
|---|---|---|
| Google Document AI – Enterprise OCR | 1,50 USD/1.000 trang (1–5 triệu trang/tháng). Trên 5 triệu trang: 0,60 USD. Phần bổ sung (add-on) 6 USD/1.000 trang. Bảng giá không chia theo ngôn ngữ | [27†] (NCC) |
| LLM đa phương thức đọc PDF | Claude: 1.500–3.000 token chữ mỗi trang cộng ảnh trang, không thu thêm phí PDF [24][25]. Gemini: khoảng 258 token mỗi trang, tối đa 1.000 trang [26]. Ước tính chi phí ở mục 2.3 | (NCC) |
| Độ chính xác đọc chữ tiếng Việt của các mô hình đa phương thức | Bài VMMU (bản 5, 23/09/2026) nói các mô hình thương mại đọc chữ tiếng Việt "mạnh", nhưng chỉ đạt **66% độ chính xác trung bình** khi phải hiểu và suy luận trên ảnh. Lỗi chính nằm ở gắn chữ với hình và suy luận, không ở khâu đọc chữ. Phần tóm tắt không có số OCR riêng cho từng mô hình | [29] (ĐL) |
| Vintern-1B (5CD-AI) | Mô hình đa phương thức tiếng Việt 1 tỷ tham số (Qwen2-0.5B + InternViT-300M). Nhắm tới OCR, trích xuất tài liệu, hỏi đáp trên ảnh. Tác giả nói đủ nhỏ để chạy trên thiết bị. Có bản v3.5 do tài khoản khác đăng, chưa xác minh | [30] (ĐL, 08/2024) |
| FPT.AI Reader / OCR | Hỗ trợ tiếng Việt và tiếng Anh. Giá công khai chỉ thấy cho đối chiếu khuôn mặt và đọc bằng lái xe: 1.000 VND/yêu cầu nếu dưới 10.000 yêu cầu/tháng. **Không tìm được giá OCR tài liệu chung** | [28†] (NCC) |
| VinAI OCR | **Không tìm được sản phẩm hoặc số đo OCR công khai của VinAI** cho tài liệu | — |
| Đo OCR trên phiếu xét nghiệm y khoa tiếng Việt | **Không tìm được nguồn** | — |

### 2.5. Phần cứng tự chạy (on-prem) so với API

| Thiết bị | Giá tại VN | Nguồn |
|---|---|---|
| RTX 5090 32GB (chỉ card) | **153,99–199,99 triệu VND** (17 mẫu, Phong Vũ, truy cập 20/10/2026). Trước đó kết quả tìm kiếm lưu mức 112–129 triệu, không ghi ngày [36]. Giá đề xuất lúc ra mắt 1.999 USD ≈ 53 triệu | [36] (BL) · [45†] (BC) |
| Lý do tăng giá GPU | Nvidia/AMD được báo tăng giá từ quý 1/2026. GDDR6/7 tăng vài trăm phần trăm. Nvidia được báo tăng giá bán theo bộ 3 lần trong 2026, lần gần nhất 20–30% | [37†] (BC ngành, TrendForce 05/01/2026) · [38†] (BC) |
| Mac Studio M5 Max 18CPU/32GPU, 36GB/512GB | **68,49–69,99 triệu VND** (Phong Vũ, Hoàng Hà, Phúc Anh, Di Động Việt) | [39†] (BL) |
| Mac Studio M5 Ultra, cấu hình cao nhất | Khoảng 512 triệu VND theo niêm yết Apple VN. Bài báo ghi mâu thuẫn giữa RAM 256GB và 512GB | [40] (BC, VietTimes 26/08/2026) |
| Apple tăng giá Mac 06/2026 | M4 Max tăng 500 USD, M3 Ultra tăng 1.300 USD | [41†] (BC) |
| Thuê GPU trong nước | FPT AI Factory: H100 khoảng 2,54 USD/giờ (gồm 192GB RAM, 16 nhân CPU). Trang không ghi ngày | [42†] (NCC) |

**So sánh hoàn vốn (ước tính của người viết, chỉ tính tiền máy; chưa tính điện, công vận hành, khấu hao, chênh lệch độ chính xác):**
- **Tự chạy chép lời (PhoWhisper-medium) trên Mac Studio khoảng 70 triệu.** So với FPT.AI ở 30.000 phút/tháng (16,2 triệu/tháng): hoàn vốn sau khoảng 4–5 tháng. So với OpenAI mini (2,4 triệu/tháng): khoảng 29 tháng. Chưa kiểm một máy có chép kịp 30.000 phút/tháng hay không.
- **Tự chạy LLM thay cho API.** So với kịch bản Haiku 0,4 triệu/tháng: không bao giờ hoàn vốn. So với kịch bản Sonnet 7,8 triệu/tháng: một máy RTX 5090 (khoảng 154–200 triệu cho riêng card) cần 20–26 tháng. Người viết đánh giá mô hình mở chạy vừa 32–36GB bộ nhớ khó đạt năng lực cỡ Sonnet. Trong khi đó, theo Epoch, giá API cho cùng năng lực giảm khoảng 13 lần/năm [22]. Nghĩa là máy mua hôm nay mất giá so với API nhanh hơn thời gian hoàn vốn.
- Lý do chính đáng để tự chạy không nằm ở tiền mà ở **dữ liệu không rời khỏi phòng khám**. Phần pháp lý thuộc nhóm khác, nhóm D không nghiên cứu.

### 2.6. Hàm ý: mua/thuê gì, tự xây gì

**Nên MUA/THUÊ** (đã thành hàng phổ thông, giá rơi nhanh, nhiều nhà cung cấp thay thế được):
- **Chép lời tiếng Việt.** Có ít nhất 4–5 nhà cung cấp hỗ trợ vi-VN, giá 0,003–0,006 USD/phút [16][12][14][9]. Không nên tự huấn luyện mô hình: PhoWhisper và VietASR đã mở [1][4].
- **Sinh chữ và tóm tắt (LLM).** Mỗi tác vụ chỉ tốn từ vài chục đến vài nghìn VND (mục 2.3).
- **Đọc PDF/ảnh** bằng mô hình đa phương thức qua API [24][26].
- **Hạ tầng gọi điện cho voice agent** (cước gọi, TTS) [31†][32†].

**Nên TỰ XÂY** (người viết suy luận từ dữ liệu trên, cần đối chiếu với các nhóm khác):
- **Bộ đo tiếng Việt y khoa của riêng mình.** Gồm ghi âm thật đã được duyệt, phiếu xét nghiệm thật, đáp án chuẩn. Ngoài kia chưa ai công bố số đo cho API thương mại trên dữ liệu kiểu này [5][6][7], và WER y khoa vẫn khoảng 27–30%. Bộ đo cũng là thứ cho phép đổi nhà cung cấp mà không sợ.
- **Lớp luồng việc và dữ liệu:** trạng thái việc, ai chịu trách nhiệm, trích nguồn khi tóm tắt, bước người duyệt. Phần này không rẻ đi theo đường cong giá mô hình.
- **Lớp chuyển đổi nhà cung cấp (adapter).** Mỗi năng lực gọi qua một giao diện của mình, để đổi mô hình hoặc nhà cung cấp chỉ cần sửa cấu hình.

**Rủi ro phụ thuộc nhà cung cấp, đều có bằng chứng:**
- **Giá tăng theo lịch:** Gemini Flash gấp đôi từ 01/01/2027 [18]. GPU và máy Mac tăng giá trong 2026 [37†][41†].
- **Mô hình bị thay hoặc ngừng:** DeepSeek tự chuyển tên mô hình cũ sang mô hình mới và tính theo giá mới [19]. Đầu ra có thể đổi mà mình không hay.
- **Phí xử lý theo vùng:** OpenAI cộng 10% [16]. DeepSeek định giá theo giờ cao điểm UTC [19].
- **Giá trong nước không minh bạch:** Viettel STT/callbot và FPT AI Engage không công bố giá [10][34†][35†]. Viettel bắt tay iFLYTEK (Trung Quốc), có thể kéo theo thay đổi công nghệ nền [11†].

**Tốc độ rẻ đi.** Khoảng 10–13 lần/năm ở cùng năng lực [20][22]. Nhanh nhất ngay sau khi một mức năng lực mới xuất hiện, sau đó chậm dần [22]. Hệ quả thực hành:
1. Tính năng nào hôm nay cần Sonnet thì 12–24 tháng nữa có thể chạy bằng gói rẻ hơn khoảng 20 lần. Vì vậy thiết kế sao cho đổi mô hình dễ, và dùng bộ đo để biết lúc nào đổi được.
2. Đừng bỏ vốn lớn vào tinh chỉnh hay tự host mô hình riêng, vì mô hình mở hoặc mô hình rẻ đời sau thường vượt qua.
3. Chi phí AI theo lượt khám đã nhỏ hơn nhiều so với công người. Thứ khan hiếm là **độ đúng trên dữ liệu y khoa tiếng Việt** và **khả năng gắn vào luồng việc**, không phải tiền gọi mô hình.

---

## 3. Điều chưa chắc / chưa tìm được

- **WER của API thương mại (FPT, Viettel, Google Chirp 3, OpenAI, Azure) trên tiếng Việt y khoa:** không tìm được nguồn nào. Số 27–30% ở trên là của mô hình nghiên cứu cỡ nhỏ.
- **Giá STT của Viettel AI**, **API STT của Zalo AI** (có tồn tại hay không), **giá AWS Transcribe tiếng Việt** (chỉ có số bên thứ ba khoảng 0,024 USD/phút, các nguồn mâu thuẫn), **giá Azure** (trang chính thức hiện ô trống; số dùng ở đây lấy từ đối thủ Soniox).
- **Giá voicebot/callbot trong nước** (FPT AI Engage, Viettel Cyberbot): không công khai. Chất lượng tiếng Việt của Retell/Vapi/ElevenLabs: không có nguồn. Giá các nền tảng này chỉ từ blog bên thứ ba.
- **Giá OCR tài liệu chung của FPT.AI**, **OCR của VinAI**, và **độ chính xác OCR trên phiếu xét nghiệm tiếng Việt**: không tìm được.
- **Số token mỗi trang PDF và số token mỗi phút hội thoại tiếng Việt** là giả định của người viết. Cần đo bằng API đếm token trên 20–30 tệp thật của Dr4Women.
- **Năng lực và tốc độ của mô hình mở chạy trên Mac Studio / RTX 5090** cho LLM và ASR tiếng Việt: chưa có số đo. Phần hoàn vốn ở mục 2.5 chỉ là ước tính.
- **Ngày áp dụng** của bảng giá Anthropic, DeepSeek và FPT.AI không ghi trên trang; ở đây dùng ngày truy cập 20/10/2026. Tỷ giá dùng số tháng 7/2026.
- Lý do Gemini Flash tăng giá: chỉ có blog bên thứ ba, chưa có thông báo chính thức của Google [23†].
- Các nguồn có dấu † chưa mở được trang gốc.

---

## 4. Nguồn

1. PhoWhisper — README, bảng WER và tải mô hình. VinAI Research. Truy cập 20/10/2026. https://github.com/VinAIResearch/PhoWhisper — (ĐL, tác giả tự đo)
2. "PhoWhisper: Automatic Speech Recognition for Vietnamese". VinAI. 06/2024. https://arxiv.org/abs/2406.02555 — (ĐL)
3. Vietnamese Open ASR Leaderboard. vietaudio-team (Hugging Face Space). Không ghi ngày, truy cập 20/10/2026. https://vietaudio-team-vietnamese-asr-leaderboard.hf.space/ — (ĐL, cộng đồng)
4. "VietASR: Achieving Industry-level Vietnamese ASR with 50-hour labeled data…". Zhuo và cộng sự, Interspeech 2025. 23/05/2025 (bản 2: 29/05/2025). https://arxiv.org/abs/2505.21527 — (ĐL)
5. "VietMed: A Dataset and Benchmark for ASR of Vietnamese in the Medical Domain". Khai Le-Duc. 04/2024. https://arxiv.org/abs/2404.05659 — (ĐL)
6. "MultiMed: Multilingual Medical Speech Recognition via Attention Encoder Decoder". ACL 2025 Industry. 09/2024 (có sửa đổi sau). https://arxiv.org/abs/2409.14074 — (ĐL)
7. "MultiMed-ST: Large-scale Many-to-many Multilingual Medical Speech Translation". 04/2025. https://arxiv.org/abs/2504.03546 — (ĐL)
8. openai/whisper — README, bảng cỡ mô hình và VRAM. OpenAI. Truy cập 20/10/2026. https://github.com/openai/whisper — (NCC)
9. FPT.AI — STT Pricing. FPT Smart Cloud. Ghi ©2025, truy cập 20/10/2026. https://docs.fpt.ai/docs/en/speech/documentation/stt-pricing/ — (NCC)
10. Viettel AI — Speech to text (trang sản phẩm, không đọc được nội dung). Truy cập 20/10/2026. https://viettelai.vn/en/speech-to-text — (NCC)
11. "Vietnam's Viettel Telecom, China's iFLYTEK to jointly advance Vietnamese AI voice". Technode Global. 10/04/2026. https://technode.global/2026/04/10/vietnams-viettel-telecom-chinas-iflytek-to-jointly-advance-vietnamese-ai-voice/ — (BC) †
12. Chirp 3 Transcription — danh sách ngôn ngữ (vi-VN GA). Google Cloud. Truy cập 20/10/2026. https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3 — (NCC) †
13. Speech-to-Text pricing. Google Cloud. Truy cập 20/10/2026 (trang không đọc được trực tiếp). https://cloud.google.com/speech-to-text/pricing — (NCC) †
14. Amazon Transcribe — Supported languages; "Amazon Transcribe now supports… Vietnamese" (12/2022). AWS. https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html · https://aws.amazon.com/about-aws/whats-new/2022/12/amazon-transcribe-speech-text-languages-swedish-vietnamese/ — (NCC) †
15. "Compare speech-to-text API pricing". Soniox. Cập nhật 23/09/2026. https://soniox.com/compare/stt/pricing — (NCC, đối thủ tự so sánh)
16. API Pricing. OpenAI. Truy cập 20/10/2026. https://developers.openai.com/api/docs/pricing — (NCC)
17. Pricing (API). Anthropic / Claude. Truy cập 20/10/2026. https://claude.com/pricing — (NCC)
18. Gemini API pricing. Google AI for Developers. Cập nhật 19/10/2026. https://ai.google.dev/gemini-api/docs/pricing — (NCC)
19. Models & Pricing. DeepSeek API Docs. ©2026, truy cập 20/10/2026. https://api-docs.deepseek.com/quick_start/pricing/ — (NCC)
20. "Welcome to LLMflation – LLM inference cost is going down fast". Guido Appenzeller, a16z. 12/11/2024. https://www.a16z.com/llmflation-llm-inference-cost — (phân tích của quỹ đầu tư)
21. "LLM inference prices have fallen rapidly but unequally across tasks". Epoch AI (Cottier, Snodin, Owen, Adamczewski). 12/03/2025. https://epoch.ai/data-insights/llm-inference-price-trends — (ĐL)
22. "The plunging price of thought". Epoch AI (Luke Emberson, David Roodman). 22/09/2026 (cập nhật 23/09). https://epoch.ai/publications/the-plunging-price-of-thought — (ĐL)
23. "Gemini 3.7 Flash price doubles January 2027". apicostcalc.com. 2026. https://apicostcalc.com/blog/gemini-3-7-flash-price-doubles-january-2027.html — (BC) †
24. PDF support — Estimate your costs. Anthropic docs. Truy cập 20/10/2026. https://platform.claude.com/docs/en/build-with-claude/pdf-support — (NCC)
25. Vision — kích thước ảnh và số token. Anthropic docs. Truy cập 20/10/2026. https://platform.claude.com/docs/en/build-with-claude/vision — (NCC)
26. Document understanding (258 token/trang). Google AI for Developers. Truy cập 20/10/2026. https://ai.google.dev/gemini-api/docs/document-processing — (NCC) †
27. Document AI pricing. Google Cloud. Truy cập 20/10/2026. https://cloud.google.com/document-ai/pricing — (NCC) †
28. FPT.AI — Face match pricing; License recognition pricing. FPT Smart Cloud. https://docs.fpt.ai/docs/en/vision/documentation/face-match-pricing · https://docs.fpt.ai/docs/en/vision/documentation/license-recognition-pricing — (NCC) †
29. "VMMU: A Vietnamese Multitask Multimodal Understanding and Reasoning Benchmark". Bản 5, 23/09/2026 (bản 1: 19/08/2025). https://arxiv.org/abs/2508.13680 — (ĐL)
30. "Vintern-1B: An Efficient Multimodal Large Language Model for Vietnamese". 5CD-AI. 22–23/08/2024. https://arxiv.org/abs/2408.12480 — (ĐL)
31. Retell AI pricing 2026 (bài tổng hợp). eesel.ai; costbench.com. 2026. https://eesel.ai/blog/retell-ai-pricing · https://costbench.com/software/voice-ai-agents/retell-ai/ — (BC) †
32. Vapi AI pricing. CloudTalk. Cập nhật 30/07/2026. https://cloudtalk.io/blog/vapi-ai-pricing — (BC) †
33. ElevenLabs Agents pricing explained. getmacha.com; happyrobot.ai. 2026. https://www.getmacha.com/blog/elevenlabs-agents-pricing-explained — (BC) †
34. FPT AI Engage (trang sản phẩm). FPT Smart Cloud. https://fpt.ai/products/fpt-ai-engage/ — (NCC) †
35. "Cyber Callbot: Tổng đài đầu tiên… dùng AI trả lời khách hàng bằng tiếng Việt". Thị trường Tài chính Tiền tệ. https://thitruongtaichinhtiente.vn/cyber-callbot-tong-dai-dau-tien-tren-the-gioi-dung-ai-tra-loi-khach-hang-bang-tieng-viet-27852.html — (BC, đưa lại số của NCC) †
36. Danh mục VGA RTX 5090. Phong Vũ. Truy cập 20/10/2026. https://phongvu.vn/c/vga-rtx-5090 — (BL)
37. "NVIDIA, AMD reportedly plan price hikes starting 1Q26; RTX 5090 may reach $5,000". TrendForce. 05/01/2026. https://www.trendforce.com/news/2026/01/05/news-nvidia-amd-reportedly-plan-price-hikes-starting-1q26-geforce-rtx-5090-may-reach-5000/ — (BC ngành) †
38. "Nvidia reportedly raises GPU bundle prices by up to 30%". Outlook India Respawn. 2026. https://respawn.outlookindia.com/gaming/gaming-news/nvidia-reportedly-raises-gpu-bundle-prices-by-up-to-30 — (BC) †
39. Mac Studio M5 Max 36GB/512GB — trang sản phẩm. Phong Vũ; Hoàng Hà Mobile; Phúc Anh; Di Động Việt. Truy cập 20/10/2026. https://phongvu.vn/may-tinh-apple-mac-studio-m5-max-18cpu-32gpu-36gb-512gb-bac-mhl64sa-a--s260805287 · https://hoanghamobile.com/may-tinh-de-ban/mac-studio-m5-max · https://www.phucanh.vn/pc-apple-mac-studio-m5-max.html — (BL) †
40. "Vì sao Mac Studio 2026 có giá hơn 500 triệu đồng tại Việt Nam". VietTimes. 26/08/2026. https://viettimes.vn/vi-sao-mac-studio-2026-co-gia-hon-500-trieu-dong-tai-viet-nam-post205036.html — (BC)
41. Mac Studio: Should You Buy? (roundup, có mục tăng giá 06/2026). MacRumors. https://macrumors.com/roundup/mac-studio/ — (BC) †
42. "H100 cost" — AI Insights. FPT AI Factory. Không ghi ngày. https://factory.fpt.ai/ai-insights/h100-cost — (NCC) †
43. Tỷ giá USD/VND Vietcombank (bản lưu 02/07/2026). Topi. https://topi.vn/usd-to-vnd-theo-ty-gia-vietcombank.html — (BC, trang tổng hợp) †
44. MedVoice – ứng dụng ghi chép hồ sơ y khoa tự động dựa trên AI. RMIT Việt Nam. 02/2025. https://www.rmit.edu.vn/vi/tin-tuc/tat-ca-tin-tuc/2025/feb/medvoice-ung-dung-ghi-chep-ho-so-y-khoa-tu-dong-dua-tren-ai — (BC, tin của trường) †
45. RTX 5090 (giá đề xuất 1.999 USD). Dexerto. https://www.dexerto.com/tech/nvidia-rtx-5090-2301788/ — (BC) †
