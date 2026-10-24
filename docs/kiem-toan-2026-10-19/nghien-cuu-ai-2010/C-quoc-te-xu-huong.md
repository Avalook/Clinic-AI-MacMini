# Nhóm C: AI y tế quốc tế và xu hướng "hàng hoá hoá" (nghiên cứu ngày 20/10/2026)

Ký hiệu loại nguồn: **(a)** số liệu độc lập (nghiên cứu, cơ quan, khảo sát có phương pháp) · **(b)** nhà cung cấp tự công bố (marketing, thông cáo, trang giá) · **(c)** báo chí/nhà phân tích đưa tin, tổng hợp lại. Số trong ngoặc vuông là số thứ tự ở mục "Nguồn". Mọi số tiền là USD trừ khi ghi khác.

---

## 1. Tóm tắt 5–8 ý quan trọng nhất

1. **Ghi chép bằng giọng nói (ambient scribe) đang thành tính năng có sẵn, giá tiến về 0 ở tầng "chép thành ghi chú".** Có ba dấu hiệu. Doximity cho bác sĩ Mỹ dùng miễn phí từ 07/2025 [14]. athenahealth gộp athenaAmbient vào phí EHR, không thu thêm, với hơn 170.000 người dùng (08/2026) [9][10]. Epic phát hành AI Charting gắn sẵn trong EHR ngày 04/02/2026 [7]. API thô (AWS HealthScribe) có giá khoảng 0,10 USD/phút âm thanh [31]. Menlo Ventures viết rằng khách hàng coi việc ghi chép là thứ "becoming commoditized" và chi phí chuyển nhà cung cấp thấp [16].
2. **Bằng chứng độc lập cho thấy ích lợi có thật nhưng KHIÊM TỐN, không phải "tiết kiệm 1–2 giờ/ngày" như quảng cáo.** Theo JAMA (04/2026, 5 hệ thống, khoảng 8.600 người), thời gian ghi chép giảm 16 phút cho mỗi 8 giờ khám (giảm 10%), còn giờ làm ngoài giờ không đổi [2]. Thử nghiệm ngẫu nhiên đăng trên NEJM AI (11/2025): Nabla giảm thời gian viết ghi chú nhiều hơn nhóm chứng 9,5%, DAX không khác biệt có ý nghĩa, và chỉ số kiệt sức cải thiện khoảng 7% [1]. Lợi ích tài chính chưa được chứng minh [3]. Ghi chú do AI viết có tỷ lệ lỗi trung bình 26%, phần lớn là bỏ sót; bản miễn phí sai tới 46% [5].
3. **Tiền đầu tư vẫn đổ vào scribe, nhưng các hãng lớn đang chạy ra khỏi "ghi chú" để vào luồng việc ăn tiền.** Abridge gọi 300 triệu USD với định giá khoảng 5,3 tỷ USD (06/2025) [20], rồi lấn sang xin phép trước (prior auth) cùng Availity (01/2026) và rà hồ sơ trước khi gửi hoá đơn [28]. Nabla (70 triệu USD, 06/2025) tự định vị là "agentic" [24]. Oracle gắn thêm mã hoá phí khám vào agent của mình (08/2026) [29]. McKinsey (01/2026) cũng cho rằng scribe đang từ thứ tạo khác biệt thành "đầu vào hàng hoá" [17].
4. **"Kết quả xét nghiệm bị bỏ sót theo dõi" là nỗi đau có thật, được đo nhiều lần.** Tổng quan hệ thống về ngoại trú cho thấy 6,8–62% kết quả xét nghiệm bất thường và tới khoảng 36% kết quả chẩn đoán hình ảnh không được theo dõi [33]. Một cuộc kiểm tra ở Anh năm 2024 (57 phòng khám) thấy 47% bệnh nhân không có ghi nhận nào về việc đã báo kết quả máu [34]. Gần với sản phụ khoa: sau Pap/HPV bất thường, 39,5% không có ghi nhận soi cổ tử cung tiếp theo (Mississippi, 2024) [35]. Joint Commission đưa việc báo kết quả xét nghiệm quan trọng vào Mục tiêu An toàn Người bệnh Quốc gia [37].
5. **Có người trả tiền cho việc "đóng vòng" kết quả, nhưng chủ yếu là hệ thống lớn và đang bị EHR lấn sang.** Eon (theo dõi phát hiện tình cờ trên phim chụp) có hơn 70 hệ thống y tế dùng (12/2025) [40]. Northwestern tự xây hệ thống này [38]. Epic giới thiệu Art tự trích phát hiện cần theo dõi và tự đặt lịch (HIMSS 03/2026) [39]. Tức là "đóng vòng" là việc ăn tiền, nhưng giá trị nằm ở dữ liệu quy trình và tích hợp, không nằm ở model.
6. **Agent vận hành (gọi điện, nhắc lịch, xử lý fax, tiếp nhận) có doanh thu thật và được định giá cao.** Hippocratic AI định giá 3,5 tỷ USD (11/2025) [41]. Artera đạt 100 triệu USD doanh thu định kỳ theo hợp đồng (12/2025) [44]. Qventus gọi 105 triệu USD (01/2025) [43]. Insight Health gọi 11 triệu USD để làm agent xử lý fax, chuyển tuyến (04/2026) [47]. Ở tầng hạ tầng, giọng nói AI chỉ tốn khoảng 0,07–0,30 USD/phút [32], nên lợi thế không nằm ở công nghệ giọng nói mà ở quy trình và tích hợp.
7. **AI sức khoẻ phụ nữ quốc tế chủ yếu là mô hình B2B2C: bán cho bên trả tiền (bảo hiểm, chủ doanh nghiệp), không bán phần mềm cho phòng khám.** Pomelo (định giá 1,7 tỷ USD, 01/2026) ký hợp đồng trả theo giá trị với bảo hiểm và chủ doanh nghiệp [51]. Maven (1,7 tỷ USD, 10/2024) có lớp AI "Maven Intelligence" ra mắt 03/2026, dựa trên khoảng 1 tỷ điểm dữ liệu dọc [49][50]. Midi (mãn kinh, hơn 1 tỷ USD, 02/2026) thu tiền qua bảo hiểm thương mại [52]. Phần mềm EHR sản khoa (athenaOne Women's Health) chủ yếu là biểu mẫu, bảng theo dõi thai kỳ cộng scribe chung, chưa thấy AI riêng cho sản khoa [54].
8. **Nhà đầu tư và nhà phân tích nói gần như cùng một ý:** ghi chú là hàng phổ thông; lợi thế nằm ở dữ liệu độc quyền, tích hợp sâu vào luồng việc, và bán "kết quả công việc" thay vì công cụ. Bessemer (01/2026) gọi đó là "systems of action" và "AI-services-as-software" [18]. Rock Health (01/2026) cảnh báo năng lực có thể nhanh chóng từ khác biệt thành hàng hoá [19]. Menlo (10/2025) ghi nhận khách hàng muốn mua AI từ nhà cung cấp EHR họ đang dùng cho mã hoá, xin phép trước, đặt lịch [16].

---

## 2. Chi tiết

### 2.1. Ghi chép bằng giọng nói (ambient scribe)

#### a) Bảng giá (theo bác sĩ/tháng), bản miễn phí

| Sản phẩm | Giá công khai | Bản miễn phí | Nguồn / loại |
|---|---|---|---|
| Abridge | Không công bố ("liên hệ"). Sacra **ước tính** khoảng 2.500 USD/bác sĩ/năm (~208 USD/tháng); một ghi chú khác của Sacra ước 300–600 USD/tháng. Hai ước tính này mâu thuẫn nhau | Không | [6] (c), [59] (c, ước tính) |
| Microsoft Dragon Copilot (gồm DAX cũ) | Microsoft **không công bố** giá thuê bao. Gói Physician Flex tính theo lượt dùng, 0,01 USD/đơn vị; một ghi chú ambient = 300 đơn vị ≈ **3 USD/ghi chú** (hiệu lực 01/05/2025, theo hướng dẫn cấp phép Microsoft do SAMexpert dẫn lại) | Không | [12] (c) |
| Dragon Copilot, theo đại lý bán lại ABT | Flex 604,80 USD/tháng + phí dùng; Per User 1.512 USD/tháng, **giảm 57%** từ 3.528 USD ngày 01/05/2026 (đại lý tự nêu, chưa đối chiếu với Microsoft) | Không | [13] (b, đại lý) |
| Epic AI Charting | Không công bố. Nằm trong bộ Art của EHR; chỉ dành cho khách đang dùng Epic. Khách hàng Epic **kỳ vọng** rẻ hơn hàng ngoài (KLAS, 35 cuộc phỏng vấn) | Không rõ | [7] (c), [8] (a, mẫu nhỏ) |
| athenahealth athenaAmbient | **Không tính thêm phí**, gộp vào phí athenaOne | Có (đã gộp) | [10] (b), [9] (c) |
| Oracle Health Clinical AI Agent | Không công bố. healthsystemCIO khuyên CIO kiểm tra xem tính năng có nằm sẵn trong giấy phép EHR không | Không rõ | [29] (c) |
| Doximity Scribe | **Miễn phí** cho bác sĩ, NP, PA, sinh viên y Mỹ đã xác minh (từ 07/2025); bản doanh nghiệp báo giá riêng | Có | [14] (c) |
| Heidi Health | Trang giá **không hiện số**; bản miễn phí vĩnh viễn: chép lời không giới hạn, nhưng không tích hợp EHR, không mã hoá, agent bị giới hạn theo tuần. Bên thứ ba báo bản Clinician 110–150 USD/tháng (mâu thuẫn) | Có | [22] (b), [21] (c) |
| Freed | 39 USD (40 ghi chú) / 59 hoặc 79 USD (không giới hạn; trang hiện cả hai số) / 104–119 USD (có đẩy vào EHR, mã ICD-10/CPT) | Thử 7 ngày | [23] (b) |
| Suki | Không công bố; trang review **ước** 299–399 USD/tháng | Không | [26] (c, ước tính) |
| DeepScribe | Không công bố; trang review **ước** 350–500+ USD/tháng | Không | [27] (c, ước tính) |
| Nabla | Không tìm được trang giá công khai | Không rõ | — |
| AWS HealthScribe (API thô) | 0,001667 USD/giây ≈ **0,10 USD/phút** âm thanh; dùng thử 300 phút/tháng trong 2 tháng đầu | Dùng thử | [31] (b) |
| OpenAI ChatGPT for Clinicians | Miễn phí cho bác sĩ Mỹ đã xác minh (22/04/2026). **Không** phải scribe nghe khám: dùng để soạn thư chuyển tuyến, xin phép trước, hướng dẫn bệnh nhân | Có | [30] (c) |

**Tín hiệu giá giảm / bị gộp miễn phí (theo thời gian):**
- 07/2025: Doximity cho dùng scribe miễn phí. Axios gọi đây là dấu hiệu chỉ chép lời thôi thì không còn đủ sống [14] (c).
- 08/2025: Rock Health nhận định các hãng lớn vào cuộc (Doximity, Oracle, Epic) tạo nguy cơ hàng hoá hoá; người dùng có thể nhận công cụ "just good enough" [15] (c).
- 09/2025: KLAS hỏi 35 khách hàng Epic. Đa số định dùng công cụ của Epic trong 2 năm và kỳ vọng giá thấp hơn. Công cụ này làm cùng Microsoft [8] (a, mẫu nhỏ).
- 10/2025: Menlo ghi nhận khách coi ghi chép đang thành hàng hoá; 67% bên ngoại trú có khả năng đổi nhà cung cấp; khách dự báo "pricing pressure to intensify" [16] (c/khảo sát).
- 11/2025: athenahealth công bố athenaAmbient không tính thêm phí [10] (b).
- 01/2026: McKinsey viết scribe có thể đi từ thứ tạo khác biệt thành đầu vào hàng hoá [17] (c; chỉ đọc được tiêu đề và mô tả, trang chính bị quá thời gian).
- 02/2026: Epic AI Charting ra mắt rộng; HLTH viết các hệ thống y tế có thể xét lại hợp đồng riêng với Abridge, Ambience, Nabla [7] (c).
- 05/2026: đại lý ABT báo Microsoft giảm 57% giá gói Per User [13] (b, chưa kiểm).
- 08/2026: Oracle gắn thêm mã hoá phí khám, đọc chính tả, rà hồ sơ vào agent của mình; báo chí khuyên kiểm tra phần trùng với giấy phép EHR [29] (c).

#### b) Gọi vốn / định giá gần đây

| Công ty | Vòng gần nhất | Nguồn / loại |
|---|---|---|
| Abridge | Series E 300 triệu USD, định giá khoảng 5,3 tỷ USD, a16z dẫn đầu, 24/06/2025. Năm 2026 chỉ có ước tính thị trường thứ cấp 5,7–7,0 tỷ USD, không có vòng định giá chính thức | [20] (c); ước tính thứ cấp: trueup/premieralts (c, không dùng làm số chính) |
| Abridge, doanh thu | Sacra **ước** khoảng 100 triệu USD ARR (05/2025); TechCrunch dẫn The Information: 117 triệu USD ARR theo hợp đồng (Q1/2025) | [59] (c, ước tính) |
| Ambience Healthcare | Series C 243 triệu USD, định giá 1,25 tỷ USD, 07/2025 | [25] (c) |
| Nabla | Series C 70 triệu USD (HV Capital dẫn đầu), 06/2025; tổng vốn 120 triệu USD; chuyển hướng sang agent làm mã hoá, chuẩn bị trước khám | [24] (c) |
| Heidi Health (Úc) | Series B 65 triệu USD, Point72 dẫn đầu, định giá 465 triệu USD (≈ 704 triệu AUD), 05–06/10/2025 | [21] (c) |
| Suki | Series D 70 triệu USD (2024, Reuters dẫn nguồn tin: định giá khoảng 500 triệu USD); có tin Series E 90 triệu USD, dự kiến doanh thu 60–80 triệu USD, **chưa xác định được ngày** | [26] (c) |
| DeepScribe | Không tìm được vòng 2025–2026; Caplight ghi Series B 07/2024 | [27] (c) |
| Microsoft (Nuance) | Ra mắt Dragon Copilot 03/2025 (gộp Dragon Medical One với DAX) | [12] (c) |

**Thị phần (tham khảo):** Menlo (10/2025): DAX 33%, Abridge 30%, Ambience 13% [16] (c/khảo sát). KLAS (09/2025, 35 khách Epic): Microsoft 40%, Abridge 29% [8] (a, mẫu nhỏ). Abridge đứng đầu Best in KLAS 2026 mảng Ambient Speech, 94,7/100 (04/02/2026) [c, Becker's, tìm qua tìm kiếm, chưa mở trang].

#### c) Bằng chứng hiệu quả độc lập

| Nghiên cứu | Thiết kế | Kết quả chính | Hạn chế | Nguồn / loại |
|---|---|---|---|---|
| Lukac và cs., *NEJM AI*, 26/11/2025 (UCLA) | Thử nghiệm ngẫu nhiên, 238 bác sĩ, 14 chuyên khoa, khoảng 72.000 lượt khám, chia ba nhánh: DAX / Nabla / chứng | Nabla: thời gian mỗi ghi chú từ 4:30 xuống 3:49 (giảm 41 giây; nhóm chứng giảm 18 giây), tức giảm hơn chứng 9,5%, có ý nghĩa. DAX: không có ý nghĩa. Kiệt sức cải thiện khoảng 7%. Có lỗi "đôi khi" đáng kể về lâm sàng; 1 sự cố an toàn nhẹ | Một trung tâm, 2 tháng; người dùng chỉ bật trong khoảng 30% lượt khám | [1] (a) |
| Rotenstein và cs., *JAMA*, 01/04/2026 (MGB, UCSF và 3 hệ thống khác) | Quan sát, so sánh trước–sau có nhóm chứng (difference-in-differences); 1.809 người dùng và 6.770 người không dùng | Ghi chép giảm khoảng 16 phút cho mỗi 8 giờ khám (−10%); tổng thời gian EHR −13 phút (−3%); thêm khoảng 0,5 lượt khám/tuần; doanh thu tăng 167 USD/tháng/bác sĩ ("danh nghĩa"). **Giờ ngoài giờ không đổi.** Chỉ 32% dùng ở hơn một nửa số lượt khám | Không đánh giá chất lượng ghi chú hay kết cục điều trị | [2] (a) |
| PHTI (Peterson Health Technology Institute), 25/03/2025 | Đánh giá tổng hợp | Bằng chứng tốt cho việc giảm kiệt sức và gánh nặng nhận thức; **chưa thấy cải thiện tài chính** (số khám, độ chính xác hoá đơn); mức dùng không đều | Phần lớn số liệu là thí điểm tự báo cáo | [3] (a, qua báo chí) |
| Kaiser Permanente (TPMG), *NEJM Catalyst*, 2025 | Quan sát; 7.260 bác sĩ, khoảng 2,5 triệu lượt khám, 63 tuần | Ước tiết kiệm 15.791 giờ, tức khoảng 2,2 giờ mỗi bác sĩ trong 63 tuần (mình tự chia). Bác sĩ và bệnh nhân hài lòng | Số giờ là ước tính của chính tổ chức | [4] (a, qua AMA/Becker's) |
| OHSU + MedStar, *Mayo Clin Proc Digital Health*, 09/10/2025 | 5 nền tảng (4 trả phí, 1 miễn phí), 14 ca khám giả lập | Tỷ lệ lỗi trung bình 26,3%; **76% lỗi là bỏ sót**; nền tảng miễn phí sai 46,1%; trung bình 3 lỗi/ca có thể gây hại vừa đến nặng | Ca giả lập, mẫu nhỏ | [5] (a) |
| Tổng hợp của Beri, 25/09/2026 | Tổng hợp các nghiên cứu trên | Tựa bài: tiết kiệm "16 phút/ngày, không phải một giờ"; giá các hãng lớn đều "liên hệ" | Nguồn thứ cấp | [6] (c) |

**Nhận xét:** Lợi ích độc lập nằm ở **kiệt sức và trải nghiệm**, còn thời gian và tiền thì nhỏ. Đây là lý do người mua coi scribe là "tiện ích nên có", không phải thứ quyết định doanh thu.

#### d) EHR lớn tự tích hợp scribe
- **Epic:** công bố AI Charting tại UGM 08/2025, phát hành rộng 04/02/2026. Tính năng: nghe lượt khám, soạn ghi chú và **đơn chỉ định**, đọc toàn bộ hồ sơ dọc của bệnh nhân [7] (c). Được phát triển cùng Microsoft [8] (c). Epic vẫn cho dùng scribe bên thứ ba song song [c, bài tổng hợp, chưa kiểm nguồn gốc].
- **Oracle Health:** Clinical AI Agent soạn đơn chỉ định từ 02/02/2026; thêm mã hoá phí khám ngoại trú, đọc chính tả, rà hồ sơ từ 19–20/08/2026; Oracle báo đã tiết kiệm hơn 400.000 giờ [29] (c, số do Oracle công bố).
- **athenahealth:** Ambient Notes (Suki, iScribe) có cho mọi khách hàng từ 05/2025 [11] (b). athenaAmbient tự xây, không tính thêm phí; kèm gợi ý chẩn đoán, loại đơn chỉ định, cảnh báo thiếu sót chăm sóc; đang thử hộp thư lâm sàng AI gợi ý bước tiếp theo [9][10] (b/c).

### 2.2. AI theo luồng công việc / vận hành (agentic workflow)

#### a) Các công ty và tín hiệu "có người trả tiền"

| Công ty | Làm gì | Tiền / quy mô | Nguồn / loại |
|---|---|---|---|
| Hippocratic AI | Agent giọng nói không chẩn đoán: gọi bệnh nhân trước và sau khám, đối chiếu thuốc, nhắc việc | Series C 126 triệu USD, định giá 3,5 tỷ USD (03/11/2025); tổng vốn 404 triệu USD. Giá báo chí đưa: khoảng 9 USD/giờ agent (03/2024), không có bảng giá công khai | [41] (b/c), [42] (c) |
| Qventus | Tự động hoá vận hành bệnh viện (phòng mổ, giường) | Series D 105 triệu USD do KKR dẫn đầu (01/2025); có hệ thống y tế đầu tư chiến lược | [43] (c) |
| Notable | Agent cho tiếp nhận bệnh nhân, đặt lịch, doanh thu, tổng đài | Không thấy vòng 2025–2026; khách mới: Inova (12/01/2026), MUSC | [46] (c) |
| Artera | Liên lạc bệnh nhân bằng agent: tự đặt lịch, tiếp nhận, biểu mẫu, thu tiền | 65 triệu USD (03/12/2025); **100 triệu USD ARR theo hợp đồng**; Best in KLAS 2026 mảng liên lạc bệnh nhân | [44] (b) |
| Luma Health | Spark (10/2024): Fax Transform đọc fax đến thành việc trong EHR (chỉ cho Epic); Navigator là trợ lý gọi điện vào/ra | Tự báo tiết kiệm hơn 2 triệu giờ nhân sự năm 2025; vòng gần nhất là Series C 11/2021 | [45] (b) |
| Insight Health | Agent tiếp nhận, phân loại qua điện thoại, xử lý fax và chuyển tuyến | Series A 11 triệu USD (03/04/2026) | [47] (c) |
| Infinitus | Agent gọi bảo hiểm: xác minh quyền lợi, xin phép trước | Series C 51,5 triệu USD (10/2024); không thấy vòng 2025 | [48] (c) |
| Eon | Theo dõi **phát hiện tình cờ** trên phim chụp đến khi bệnh nhân vào luồng theo dõi | Hơn 70 hệ thống y tế, hơn 1.200 cơ sở (17/12/2025); 15,7 triệu bất thường đã phát hiện (11/02/2025); vòng vốn ngoài đầu tiên 16 triệu USD (chưa rõ ngày) | [40] (b) |
| Epic (gắn sẵn) | Art trích nốt phổi, Lung-RADS, khuyến nghị theo dõi từ báo cáo X-quang rồi **tự đặt lịch**; The Christ Hospital báo tỷ lệ phát hiện ung thư phổi giai đoạn sớm 69% (trung bình quốc gia 46%) | HIMSS 03/2026; số do Epic công bố | [39] (c) |
| Northwestern Medicine (tự xây) | NLP đọc báo cáo hình ảnh, cảnh báo bác sĩ chỉ định, theo dõi đến khi có hành động, nhắc lại nếu chưa làm | Hơn 460.000 phim năm đầu, 5% có khuyến nghị theo dõi phổi (khoảng 70/ngày); đăng *NEJM Catalyst*; **tự xây toàn bộ** | [38] (b, kèm bài báo khoa học) |

**Chi phí hạ tầng giọng nói:** agent giọng nói tốn khoảng 0,07–0,30 USD/phút tất cả chi phí; Retell/Vapi khoảng 0,10–0,31 USD/phút, chưa gồm cước điện thoại và phụ phí HIPAA [32] (c, so sánh của bên thứ ba 2026).

#### b) Bằng chứng "kết quả xét nghiệm bị bỏ sót theo dõi"

| Bằng chứng | Số liệu | Nguồn / loại |
|---|---|---|
| Callen, Westbrook, Georgiou, Li. *J Gen Intern Med* 27(10):1334–48 (online 2011, in 10/2012). Tổng quan hệ thống 19 nghiên cứu ngoại trú ở Mỹ (1995–2010) | 6,8–62% kết quả **xét nghiệm** bất thường và 1–35,7% kết quả **hình ảnh** không được theo dõi; có liên quan rõ với chẩn đoán bị muộn hoặc bị sót; EHR giúp được nhưng vẫn sót nhiều | [33] (a) |
| Watson và cs., *BMJ Open Quality* 13(3), 07/2024: kiểm tra toàn nước Anh, 57 phòng khám, 2.572 bệnh nhân | **47%** không có ghi nhận nào trong EHR về việc đã báo kết quả máu, kể cả kết quả bất thường | [34] (a) |
| *Cancer Causes & Control*, 17/08/2024: Mississippi, 1.458 người cần soi cổ tử cung sau sàng lọc bất thường | Chỉ 43% soi trong vòng 4 tháng; **39,5% không có ghi nhận theo dõi** | [35] (a) — **gần nhất với sản phụ khoa** |
| CRICO (dữ liệu bồi thường sai sót y khoa, báo cáo 2014; khoảng 23.500 vụ) | 57% vụ kiện liên quan chẩn đoán xảy ra ở ngoại trú; trong vụ chẩn đoán ngoại trú: bác sĩ không liên hệ lại bệnh nhân chiếm 21% (CRICO) / 18% (Candello) | [36] (a, dữ liệu cũ) |
| Joint Commission | Báo kết quả xét nghiệm quan trọng là Mục tiêu An toàn Người bệnh Quốc gia; "đóng vòng" = gửi, nhận, xác nhận, xử lý, có ghi trong hồ sơ. Ví dụ hay bị lọt ở ngoại trú: nốt phổi tình cờ, giải phẫu bệnh, vi sinh | [37] (a) |
| ECRI | Năm 2019 xếp "quản lý kết quả xét nghiệm trong EHR" đứng **số 1** trong 10 mối lo an toàn người bệnh. **Không tìm được** danh sách 2025–2026 | [c, báo chí đưa tin 2019] |

**Có phải nỗi đau được trả tiền không?** Có, nhưng theo cách riêng (đây là suy luận của mình từ các nguồn [38][39][40][37][36]):
- Người trả tiền là bên chịu rủi ro pháp lý và kiểm định: hệ thống y tế lớn qua Eon, Epic, hoặc tự xây như Northwestern. Phần lớn giải pháp quốc tế tập trung vào **hình ảnh** (nốt phổi, tuyến giáp, buồng trứng), không phải xét nghiệm ngoại trú từ **phòng xét nghiệm đối tác**.
- Phần "bám đến khi xử lý xong" (nhắc lại, chuyển cho điều dưỡng, báo bệnh nhân) mới là phần ăn tiền. Phần trích chữ từ báo cáo thì Epic đã làm sẵn.
- Không tìm được sản phẩm thương mại nào chuyên đóng vòng kết quả **xét nghiệm và giải phẫu bệnh** cho phòng khám sản phụ khoa ngoại trú nhỏ.

### 2.3. AI cho sức khoẻ phụ nữ

| Công ty | Mảng | Mô hình kinh doanh | Tiền / số liệu | Nguồn / loại |
|---|---|---|---|---|
| Maven Clinic | Hiếm muộn, thai sản, nuôi con, mãn kinh (phòng khám ảo kèm chương trình chăm sóc) | Bán cho **chủ doanh nghiệp và bảo hiểm** như một phúc lợi; từ 05/2026 bán thẳng cho người dùng | Series F 125 triệu USD, định giá khoảng 1,7 tỷ USD (10/2024). Maven Intelligence (17/03/2026): lớp AI điều phối dựa trên khoảng 1 tỷ điểm dữ liệu cấu trúc sau khoảng 10 năm, dùng model OpenAI/Google; tự báo giảm 28% nhập NICU, giảm 15% mổ lấy thai | [49] (c), [50] (b/c) |
| Pomelo Care | Thai sản, sau sinh, sơ sinh; đang mở rộng sang nhi và mãn kinh | B2B: bảo hiểm (có Medicaid) và chủ doanh nghiệp; **mọi hợp đồng trả theo giá trị**, không bán thẳng người dùng | Series C 92 triệu USD, định giá 1,7 tỷ USD (08/01/2026). Tự báo: phủ hơn 25 triệu người, khoảng 7% số ca sinh ở Mỹ, giảm 37% sinh non, ROI 3–5 lần | [51] (c + b) |
| Midi Health | Mãn kinh, sau mở rộng sang tim mạch, nội tiết, béo phì | Thu qua **bảo hiểm thương mại** (không nhận Medicare/Medicaid) và chủ doanh nghiệp | Series D 100 triệu USD, định giá hơn 1 tỷ USD (03/02/2026); CEO tự báo doanh thu chạy khoảng 150 triệu USD/năm | [52] (c) |
| Mahmee | Điều phối chăm sóc thai sản và sau sinh: điều dưỡng xem huyết áp từ xa, tư vấn sữa mẹ, nối với bác sĩ sản/nhi | Bảo hiểm chi trả (đối tác: Aetna, Cigna, Kaiser…), hoặc thành viên tự trả 30 USD/tháng; Blue Shield of California triển khai cho chủ doanh nghiệp | Series A 9,2 triệu USD (Goldman Sachs, **chưa rõ ngày**). **Trang chủ không nhắc đến AI** | [53] (b + c) |
| athenaOne for Women's Health | EHR sản phụ khoa: hồ sơ thai kỳ theo mẫu ACOG, tự tính ngày dự sinh, tự điền sẵn chỉ định theo tuần thai, sàng lọc trầm cảm sau sinh (EPDS) | Phần mềm bán cho phòng khám; AI là scribe chung, không thấy AI riêng cho sản khoa | Một khách ở Connecticut tự báo đặt được lịch hậu sản 80% | [54] (b) |
| Sonio (Samsung Medison) | AI hỗ trợ siêu âm thai theo thời gian thực | Bán kèm và độc lập với máy siêu âm; bản 2 được FDA 510(k) năm 2024 | Samsung mua với giá khoảng 92 triệu USD (2024) | [55] (c) |

**Bằng chứng cho theo dõi sau sinh từ xa:** phân tích gộp các thử nghiệm ngẫu nhiên (*J Perinatal Med*, 03/2025) cho thấy đo huyết áp từ xa **không** làm giảm tái nhập viện vì tăng huyết áp, và còn làm tăng lượt vào cấp cứu. Dữ liệu quan sát (*Obstet Gynecol* 2024) thấy cứ 100 người thì bớt khoảng 1 ca tái nhập viện, nhưng có thể do khác biệt giữa nhóm tham gia và không tham gia [56] (a).

**Mô hình kinh doanh rút ra:** các công ty sức khoẻ phụ nữ được định giá trên 1 tỷ USD đều **bán kết quả cho bên trả tiền** (bảo hiểm, chủ doanh nghiệp), và AI chỉ là lớp tăng năng suất cho đội chăm sóc của họ. Không công ty nào trong số này bán "phần mềm AI cho phòng khám sản phụ khoa". Phần mềm cho phòng khám thì EHR đã làm (athena), và AI trong đó là scribe chung [49]–[54].

### 2.4. Kết luận xu hướng 2025–2026

#### a) Đang thành hàng phổ thông (giá giảm hoặc có sẵn trong EHR)

| Năng lực | Dấu hiệu | Nguồn |
|---|---|---|
| Chép lời và soạn ghi chú khám | Miễn phí (Doximity, bản free của Heidi), gộp vào EHR (Epic, athena, Oracle), API khoảng 0,10 USD/phút, thị trường self-serve 39–119 USD/tháng | [7][9][14][22][23][31] |
| Soạn đơn chỉ định từ cuộc khám | Epic (02/2026), Oracle (02/2026) đã gắn sẵn | [7][29] |
| Trợ lý hỏi đáp lâm sàng, soạn thư chung chung | OpenAI miễn phí cho bác sĩ Mỹ (04/2026) | [30] |
| Hạ tầng gọi điện, nhắc lịch bằng giọng nói | 0,07–0,30 USD/phút, nhiều nhà cung cấp | [32] |
| Trích phát hiện cần theo dõi từ báo cáo hình ảnh (ở hệ thống dùng Epic) | Art làm sẵn và tự đặt lịch | [39] |

#### b) Vẫn là lợi thế

| Lợi thế | Vì sao | Nguồn |
|---|---|---|
| **Dữ liệu quy trình dọc độc quyền** | Bessemer coi dữ liệu độc quyền là hào chắn; Maven xây AI trên khoảng 1 tỷ điểm dữ liệu 10 năm; Epic thắng nhờ đọc được toàn bộ hồ sơ dọc | [18][50][7] |
| **Tích hợp sâu, ghi ngược vào hệ thống gốc** | Menlo: khách muốn mua AI từ EHR họ đang dùng cho mã hoá, xin phép trước, đặt lịch; scribe chỉ thắng khi ghi ngược được chẩn đoán, chỉ định, hoá đơn | [16][28] |
| **Đóng vòng việc đến khi xử lý xong** (bán kết quả, không bán công cụ) | Bessemer gọi là "systems of action", "AI-services-as-software" (biên lợi nhuận gộp 70–80%+); Artera đạt 100 triệu USD ARR; Eon bán việc đưa bệnh nhân vào luồng theo dõi | [18][44][40] |
| **Chuyên khoa và luồng việc phức tạp** | KLAS: khách muốn giữ công cụ chuyên khoa riêng bên cạnh công cụ Epic; HLTH: hàng ngoài phải vượt hẳn ở luồng chuyên khoa mới sống được | [8][7] |
| **ROI đo được bằng tiền** | PHTI: scribe chưa chứng minh được ROI tài chính; Bessemer: ROI rõ thì giữ được giá cao | [3][18] |

#### c) Nhà đầu tư / nhà phân tích nói gì

| Tổ chức | Ngày | Ý chính | Loại |
|---|---|---|---|
| Menlo Ventures, "2025: The State of AI in Healthcare" | 21/10/2025 | Chi cho AI y tế khoảng 1,4 tỷ USD năm 2025 (gấp khoảng 3 lần), riêng scribe 600 triệu USD. Startup đang chiếm 85% doanh thu nhưng khách thích mua từ EHR cho mã hoá, xin phép trước, đặt lịch. Ghi chép "becoming commoditized" | (c; khảo sát của quỹ) [16] |
| Bessemer, "State of Health AI 2026" | 22/01/2026 | 92% hệ thống y tế đang triển khai hoặc thí điểm scribe (03/2025). Đi từ công cụ sang "hạ tầng sống còn" và "systems of action". Hào chắn = dữ liệu độc quyền + tích hợp luồng việc + kiểm chứng lâm sàng. Tự thừa nhận ứng dụng AI chưa "dính" bằng hệ thống lưu hồ sơ gốc | (c) [18] |
| Rock Health, tổng kết 2025 | 12/01/2026 | Vốn digital health 14,2 tỷ USD; công ty AI nhận 54% số tiền. Cảnh báo năng lực có thể nhanh chóng từ khác biệt thành hàng hoá; các hãng lớn có lợi thế nhờ khách hàng sẵn có | (a/c) [19] |
| Rock Health, "Disrupting the disruptor" | 18/08/2025 | Hãng lớn vào làm scribe; startup phải chuyển sang việc liền kề giá trị cao | (c) [15] |
| McKinsey, "Ambient scribing at the crossroads" | 01/2026 | Scribe có thể thành đầu vào hàng hoá; tích hợp EHR và mã hoá ăn mòn giá trị của sản phẩm đứng riêng | (c) [17], chỉ đọc được tóm tắt |
| KLAS | 29/09/2025 | Khách Epic kỳ vọng công cụ gắn sẵn rẻ hơn; đa số định dùng trong 2 năm | (a, mẫu 35) [8] |
| a16z | — | **Không tìm được** bài luận điểm 2025–2026 do chính a16z viết về hàng hoá hoá scribe. a16z là nhà đầu tư dẫn đầu ở Abridge, đồng dẫn đầu Ambience, và có mặt ở Pomelo, Hippocratic | [20][25][41][51] |
| CB Insights | — | **Không tìm được** báo cáo 2025–2026 công khai về chủ đề này | — |

#### d) Hàm ý cho ClinicAI (suy luận của người nghiên cứu, không phải số liệu)
- **Đừng tự xây scribe làm mũi nhọn.** Giá quốc tế đang tiến về 0 và EHR lớn gắn sẵn [7][9][14]. Nếu cần, mua hoặc gắn API (loại HealthScribe hoặc model đa ngôn ngữ). Lưu ý tiếng Việt: Capterra liệt kê Heidi có tiếng Việt, nhưng **chưa xác minh độ chính xác** [c, Capterra]. Ghi chú AI vẫn lỗi khoảng 26%, chủ yếu bỏ sót [5], nên vẫn bắt buộc có bước bác sĩ duyệt.
- **Dồn sức vào "đóng vòng việc" trên dữ liệu quy trình của mình.** Ví dụ: kết quả xét nghiệm từ đối tác → ai phải xử lý → nhắc lại → báo bệnh nhân → có ghi vết. Bằng chứng nỗi đau mạnh và gần chuyên khoa (39,5% Pap bất thường không được soi tiếp [35]; 47% không có ghi nhận đã báo kết quả [34]). Quốc tế chưa thấy ai làm cho phòng khám sản phụ khoa nhỏ; thị trường lớn thì EHR chỉ làm mảng hình ảnh [39][40].
- Ở Việt Nam không có cơ chế bảo hiểm tư trả theo giá trị như Mỹ, nên mô hình Pomelo/Maven khó bê nguyên. ROI phải đo bằng thứ phòng khám thấy được: không sót kết quả, khách quay lại tái khám, giảm việc tay của lễ tân và điều dưỡng.

---

## 3. Điều chưa chắc / chưa tìm được

- **Giá chính thức** của Abridge, Epic AI Charting, Oracle, Nabla, Suki, DeepScribe: không công bố. Các số trong bảng là ước tính của bên thứ ba hoặc đại lý, và mâu thuẫn nhau (Abridge: khoảng 208 USD hay 300–600 USD/tháng).
- **Microsoft giảm 57% giá Dragon Copilot (01/05/2026):** chỉ có một đại lý nêu [13]; chưa đối chiếu được với trang của Microsoft. SAMexpert (12/2025) nói Microsoft chưa công bố giá thuê bao [12].
- **Epic AI Charting có tính thêm phí không:** không có nguồn nào nói rõ.
- **Abridge 2026:** không có vòng định giá chính thức; các số 5,7–7,0 tỷ USD là ước tính thị trường thứ cấp, nên không dùng.
- **Suki Series E 90 triệu USD:** không xác định được ngày (trang mobihealthnews trả lỗi 403).
- **ECRI 2025–2026:** không tìm được danh sách mối lo an toàn người bệnh mới, chỉ có bản 2019.
- **Dữ liệu CRICO/Candello về sót theo dõi kết quả:** chỉ có số liệu 2011–2016; bản tin CRICO 02/2026 không mở được (403).
- **Tỷ lệ sót theo dõi kết quả xét nghiệm ở phòng khám sản phụ khoa ngoại trú** (ngoài sàng lọc cổ tử cung): không tìm được nghiên cứu riêng.
- **McKinsey (01/2026)** và **bài của a16z:** trang McKinsey quá thời gian chờ, chỉ dùng được tiêu đề và tóm tắt; không tìm được bài luận điểm do chính a16z viết.
- **Mahmee:** không thấy vòng vốn hay tính năng AI nào trong 2025–2026; ngày Series A không rõ.
- **Hippocratic AI 9 USD/giờ:** là con số báo chí đưa năm 2024, không có bảng giá công khai.
- Hầu hết số liệu kết quả của Maven, Pomelo, Artera, Luma, Eon, Epic là **do chính công ty công bố**, chưa có kiểm chứng độc lập.
- **Scribe có hỗ trợ tiếng Việt tốt không:** chưa có nguồn đánh giá độc lập.

---

## 4. Nguồn

1. "UCLA study finds AI scribes may reduce documentation time and improve physician well-being" (bài *NEJM AI* 2025;2(12), Lukac và cs.) — UCLA Health — 26/11/2025 — https://www.uclahealth.org/news/release/ucla-study-finds-ai-scribes-may-reduce-documentation-time — (a, nghiên cứu qua thông cáo của viện)
2. "AI scribes linked to modest reductions in EHR documentation time" (Rotenstein và cs., *JAMA*, doi 10.1001/jama.2026.2253) — Mass General Brigham — 01/04/2026 — https://news.massgeneralbrigham.org/en/ai-scribes-linked-to-modest-reductions-in-ehr-documentation-time — (a)
3. "Early evaluation of AI scribes finds decreased burnout but limited financial ROI" (báo cáo PHTI) — Fierce Healthcare / Peterson Health Technology Institute — 25–27/03/2025 — https://www.fiercehealthcare.com/ai-and-machine-learning/early-evaluation-ai-scribes-finds-decreased-burnout-limited-financial-roi ; https://www.axios.com/2025/03/27/ai-scribes-reduce-burnout-financial-improvement — (a, qua báo chí)
4. "AI scribes save 15,000 hours—and restore the human side of medicine" (TPMG, *NEJM Catalyst*) — AMA — 2025 — https://www.ama-assn.org/practice-management/digital-health/ai-scribes-save-15000-hours-and-restore-human-side-medicine — (a, qua báo chí)
5. "Evaluating the Quality and Safety of Ambient Digital Scribe Platforms Using Simulated Ambulatory Encounters" — *Mayo Clinic Proceedings: Digital Health* 3(4):100292, OHSU + MedStar — 09/10/2025 — https://pmc.ncbi.nlm.nih.gov/articles/PMC12605248/ — (a)
6. "Best Ambient AI Scribes Save 16 Minutes a Day, Not an Hour" — Rajesh Beri, The D*AI*LY Brief — 25/09/2026 — https://www.beri.net/article/best-ambient-ai-scribes-health-systems-abridge-epic-ai-charting-dragon-copilot — (c)
7. "Epic releases native AI Charting for integrated clinical documentation" — HLTH — 06/02/2026 — https://hlth.com/insights/news/epic-releases-native-ai-charting-for-integrated-clinical-documentation-2026-02-06 — (c)
8. "Epic ambient speech draws cautious optimism, KLAS finds" — healthsystemCIO (dẫn KLAS Flash Insights, 35 khách Epic) — 29/09/2025 — https://healthsystemcio.com/2025/09/29/epic-ambient-speech-draws-cautious-optimism-klas-finds/ ; https://hitconsultant.net/2025/09/29/klas-report-epics-native-ambient-speech-tool-reshapes-customer-ai-strategies/ — (a mẫu nhỏ, qua báo chí)
9. "athenahealth launches native AI ambient capabilities across athenaOne" — HIT Consultant — 13/08/2026 — https://hitconsultant.net/2026/08/13/athenahealth-launches-native-ai-ambient-capabilities-athenaone/ — (c, dẫn tuyên bố của hãng)
10. "athenahealth's AI-native Clinical Encounter…" — Business Wire / athenahealth — 04/11/2025 — https://www.businesswire.com/news/home/20251104083540/en — (b; đọc qua kết quả tìm kiếm, trang gốc trả 403)
11. "Suki and athenahealth Expand Partnership With General Availability of Ambient Notes" — Suki / Business Wire — 01/05/2025 — https://www.suki.ai/news/suki-and-athenahealth-expand-partnership-with-general-availability-of-ambient-notes-using-sukis-ambient-technology/ — (b)
12. "Dragon Copilot licensing guide" — SAMexpert — 22/12/2025 — https://samexpert.com/dragon-copilot-licensing-guide/ — (c, đơn vị tư vấn cấp phép)
13. "Dragon Copilot for Small Practices: The CSP-Channel-Only Launch Explained" — Access Business Technologies (đại lý Microsoft) — 05/2026, cập nhật 02/07/2026 — https://www.myabt.com/blog/dragon-copilot-physician-practices-deployment-guide — (b, đại lý)
14. "Doximity jumps into AI scribe market, offering a free tool for doctors" — HLTH / Fierce Healthcare — 29/07/2025 — https://hlth.com/insights/news/doximity-jumps-into-ai-scribe-market-offering-a-free-tool-for-doctors-2025-07-29 ; Axios 24/07/2025: https://www.axios.com/pro/health-tech-deals/2025/07/24/doximity-free-ai-scribe-commoditization-competition — (c)
15. "Disrupting the disruptor" — Rock Health — 18/08/2025 — https://rockhealth.com/rock-weekly/disrupting-the-disruptor/ — (c, nhà phân tích)
16. "2025: The State of AI in Healthcare" — Menlo Ventures — 21/10/2025 — https://menlovc.com/perspective/2025-the-state-of-ai-in-healthcare/ — (c; khảo sát của quỹ đầu tư)
17. "Ambient scribing at the crossroads: What comes next?" — McKinsey (Baxi, Patil, Heim, Prisacaru) — 01/2026 — https://www.mckinsey.com/industries/healthcare/our-insights/ambient-scribing-at-the-crossroads-what-comes-next — (c; chỉ đọc được tiêu đề và tóm tắt)
18. "State of Health AI 2026" — Bessemer Venture Partners — 22/01/2026 — https://www.bvp.com/atlas/state-of-health-ai-2026 — (c, nhà đầu tư)
19. "2025 year-end digital health funding overview: A tale of two markets" — Rock Health — 12/01/2026 — https://rockhealth.com/insights/2025-year-end-digital-health-funding-overview-a-tale-of-two-markets/ — (a/c, dữ liệu gọi vốn có phương pháp)
20. "Latham & Watkins advises Abridge in US$300 million Series E" — Latham & Watkins — 24/06/2025 — https://www.lw.com/en/news/2025/06/latham-watkins-advises-abridge-in-us300-million-series-e-funding-round ; Axios 24/06/2025: https://www.axios.com/pro/health-tech-deals/2025/06/24/abridge-raise-300m-5b-valuation-billing-scribe — (c)
21. "Heidi Health raises $65M Series B led by Point72" — TechCrunch — 05/10/2025 — https://techcrunch.com/2025/10/05/heidi-health-raises-65m-series-b-led-by-steve-cohens-point72/ ; SmartCompany 06/10/2025: https://www.smartcompany.com.au/startupsmart/heidi-health-98-million-raise-valuation-704-million — (c)
22. Trang giá Heidi — Heidi Health — truy cập 20/10/2026 — https://www.heidihealth.com/pricing — (b)
23. Trang giá Freed — Freed — truy cập 20/10/2026 — https://www.getfreed.ai/pricing — (b)
24. "AI Clinical Care Platform Nabla Secures $70M in New Funding" — Built In NYC — 18/06/2025 — https://www.builtinnyc.com/articles/nabla-secures-70m-new-funding-20250618 — (c)
25. "Ambience reels in $243M series C…" — Fierce Healthcare / Becker's — 29/07/2025 — https://fiercehealthcare.com/health-tech/ambience-banks-243m-series-c-investors-continue-bet-big-ambient-ai — (c)
26. Suki: Series D (Goodmans, 2024; Reuters dẫn định giá khoảng 500 triệu USD) — https://goodmans.ca/insights/post/goodmans-tech-blog/startup-company-raises--70-million-to-advance-ai-powered-assistants-in-the-healthcare-sector ; Series E (mobihealthnews, chưa rõ ngày) — https://mobihealthnews.com/news/suki-raises-90m-ai-clinical-workflows ; giá ước tính — https://www.plaud.ai/blogs/articles/suki-ai-review — (c)
27. DeepScribe: Caplight — truy cập 20/10/2026 — https://www.caplight.com/company/deepscribe ; giá ước tính — https://www.veroscribe.com/blog/deepscribe-review-2026 — (c, trang tổng hợp/đối thủ)
28. "Abridge and Availity Collaborate to Redefine Payer-Provider Synergy at the Point of Conversation" — Abridge — 12/01/2026 — https://abridge.com/press-release/abridge-availity-collaboration-announcement ; "Abridge expands into revenue cycle with AI-powered pre-bill claim review" — Fierce Healthcare — 2026 — https://fiercehealthcare.com/ai-and-machine-learning/abridge-expands-revenue-cycle-ai-powered-pre-bill-claim-review — (b + c)
29. "Oracle Health expands Clinical AI Agent with automated coding, dictation and chart review" — HLTH / HIT Consultant — 19–20/08/2026 — https://hlth.com/insights/news/oracle-health-expands-clinical-ai-agent-with-automated-coding-dictation-and-chart-review ; https://hitconsultant.net/2026/08/19/oracle-health-expands-clinical-ai-agent-coding-dictation-chart-review/ ; healthsystemCIO — https://healthsystemcio.com/?p=93973 — (c)
30. "OpenAI launches ChatGPT for Clinicians" — MobiHealthNews / Quartz — 22–24/04/2026 — https://www.mobihealthnews.com/news/openai-launches-chatgpt-clinicians ; https://qz.com/openai-chatgpt-clinicians-free-doctors-pharmacists-us-042426 — (c; trang gốc của OpenAI trả 403)
31. AWS HealthScribe pricing — Amazon Web Services — truy cập 20/10/2026 — https://aws.amazon.com/healthscribe/pricing/ — (b)
32. "AI voice agent pricing" (2026) — techsy.io / speechify.ai — 2026 — https://techsy.io/en/blog/ai-voice-agent-pricing ; https://speechify.ai/blog/best-voice-agent-platforms-2026 — (c, so sánh của bên thứ ba)
33. Callen J, Westbrook J, Georgiou A, Li J. "Failure to follow-up test results for ambulatory patients: a systematic review" — *J Gen Intern Med* 27(10):1334–48 — online 2011 / in 10/2012 — https://psnet.ahrq.gov/issue/failure-follow-test-results-ambulatory-patients-systematic-review — (a)
34. "Patient safety in actioning and communicating blood test results in primary care: a UK-wide audit (PACT)" — *BMJ Open Quality* 13(3):e002632 — 07/2024 — https://bmjopenquality.bmj.com/content/13/3/e002632 ; https://psnet.ahrq.gov/issue/patient-safety-actioning-and-communicating-blood-test-results-primary-care-uk-wide-audit — (a)
35. "Evaluation of follow-up colposcopy procedures after abnormal cervical screening result across a statewide study in Mississippi" — *Cancer Causes & Control* 35(11) — 17/08/2024 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11561063/ — (a)
36. CRICO, báo cáo đối chuẩn chẩn đoán 2014 và bảng ca bệnh — Harvard Risk Management Foundation — 2014 — https://www.rmf.harvard.edu/Risk-Prevention-and-Education/Article-Catalog-Page/Articles/2014/CBS-Testing-and-Results — (a, dữ liệu bồi thường, cũ)
37. Joint Commission NPSG về báo kết quả xét nghiệm quan trọng / Quick Safety "closed-loop" — Joint Commission (qua PSNet và tài liệu JC) — https://digitalassets.jointcommission.org/api/public/content/77c6421712dc463eae4b2398f9bf01a5 ; https://psnet.ahrq.gov/issue/health-it-safe-practices-closing-loop — (a)
38. "Using artificial intelligence to solve one of health care's most enduring problems" — Northwestern Medicine — 16/03/2022 — https://news.nm.org/using-artificial-intelligence-to-solve-one-of-health-cares-most-enduring-problems/ — (b, kèm bài *NEJM Catalyst*)
39. "Epic highlights AI systems' success metrics at HIMSS26" — Healthcare IT News — 03/2026 — https://www.healthcareitnews.com/news/epic-highlights-ai-systems-success-metrics-himss26 — (c; số do Epic công bố)
40. Eon: "Eon solidifies market leader position with 1,000 sites…" (11/02/2025); "Eon launches 5.0 platform…" (17/12/2025) — Eon — https://www.eonhealth.com/news/eon-solidifies-market-leader-position-with-1-000-sites-and-15-7-million-abnormalities-identified ; https://www.eonhealth.com/news/eon-launches-5-0-platform-to-address-healthcares-growing-validation-burden — (b)
41. "Hippocratic AI Raises $126 Million in Series C at $3.5 Billion Valuation" — Business Wire / SiliconANGLE — 03/11/2025 — https://siliconangle.com/2025/11/03/hippocratic-ais-valuation-soars-3-5b-raising-126m-new-funding/ — (b/c)
42. "Nvidia announces AI-powered health care 'agents'… cost $9 an hour" — Fox Business — 03/2024 — https://www-ak-ms.foxbusiness.com/technology/nvidia-announces-ai-powered-health-care-agents-outperform-nurses-cost-9-hour — (c)
43. "Qventus pockets $105M series D backed by KKR" — Fierce Healthcare — 01/2025 — https://www.fiercehealthcare.com/finance/qventus-raises-105m-series-d-new-level-resonance-decade-old-company — (c)
44. "Artera Secures $65M Growth Investment and Reaches $100M CARR" — Artera — 03/12/2025 — https://artera.io/news/artera-secures-65m-growth-investment/ — (b)
45. "Luma Health announces Spark…" — Luma Health — 15/10/2024 — https://www.lumahealth.io/newsroom/press-releases/luma-health-announces-spark-multi-model-generative-ai-to-tackle-staff-work-and-get-patients-the-care-they-need-more-efficiently/ — (b)
46. "Inova Health taps Notable to utilize intelligent AI agents" — HLTH / MobiHealthNews — 12/01/2026 — https://hlth.com/insights/news/inova-health-taps-notable-to-utilize-intelligent-ai-agents-2026-01-12 — (c)
47. "The startup looking to solve health care's fax machine problem" (Insight Health, Series A 11 triệu USD) — Fortune — 03/04/2026 — https://fortune.com/2026/04/03/health-care-fax-machine-problem-insight-health-series-a-11-million-ai-assistants — (c)
48. "Infinitus Systems secures $51.5M for automating healthcare calls" — MobiHealthNews — 10/2024 — https://www.mobihealthnews.com/news/infinitus-systems-secures-515m-automating-healthcare-calls — (c)
49. "Women's health startup Maven Clinic pockets $125M…" — Fierce Healthcare — 10/2024 — https://www.fiercehealthcare.com/finance/maven-clinic-clinches-125m-invest-tech-value-based-care — (c)
50. "Maven Clinic Introduces Maven Intelligence, an AI-Powered Orchestration Layer…" — Maven (thông cáo) / Fierce Healthcare / eMarketer — 17/03/2026 — https://www.fiercehealthcare.com/health-tech/maven-clinic-expands-ai-capabilities-generative-ai-openai-google ; https://www.emarketer.com/content/maven-leans-agentic-ai-women-s-health — (b/c)
51. "Pomelo Care raises $92M, reaches $1.7B valuation" — MobiHealthNews — 08/01/2026 — https://www.mobihealthnews.com/news/pomelo-care-raises-92m-reaches-17b-valuation ; trang cho bên trả tiền của Pomelo — https://www.pomelocare.com/payers-maternity ; Fierce (mọi hợp đồng trả theo giá trị) — https://www.fiercehealthcare.com/digital-health/virtual-maternity-care-provider-pomelo-clinches-46m-scale — (c + b)
52. "Midi Health raises $100 million Series D, surpasses $1 billion valuation" — FemTech Insider — 03/02/2026 — https://femtechinsider.com/midi-health-raises-100-million-series-d-surpasses-1-billion-valuation/ — (c)
53. Trang chủ Mahmee — truy cập 20/10/2026 — https://www.mahmee.com/ ; "Maternal Health Startup Mahmee Raises $9.2M Series A…" — FinTech Futures (chưa rõ ngày) — https://www.fintechfutures.com/press-releases/maternal-health-startup-mahmee-raises-9-2m-series-a-led-by-goldman-sachs-asset-management — (b + c)
54. athenaOne for Women's Health — athenahealth — truy cập 20/10/2026 — https://www.athenahealth.com/who-we-serve/obgyn ; https://help.athenahealth.com/Ohelp/Content/Womens%20Health/OB-PM-C-Prenatal-Tracking.htm — (b)
55. "Samsung finalizes $92M acquisition of French ultrasound AI firm Sonio" — Radiology Business — 2024 — https://radiologybusiness.com/topics/healthcare-management/mergers-and-acquisitions/samsung-finalizes-92m-acquisition-french-ultrasound-ai-firm-sonio — (c)
56. Theo dõi huyết áp sau sinh từ xa: phân tích gộp các thử nghiệm ngẫu nhiên, *J Perinatal Med* (03/2025), và nghiên cứu nhóm *Obstet Gynecol* (2024) — https://pmc.ncbi.nlm.nih.gov/articles/PMC11326966 ; https://opqic.org/?p=18491 — (a; đọc qua tóm tắt)
57. (bỏ trống, không dùng)
58. (bỏ trống, không dùng)
59. Sacra — hồ sơ Abridge (ước tính ARR và giá) — truy cập 20/10/2026 — https://sacra.com/c/abridge/ ; TechCrunch dẫn The Information — https://techcrunch.com/?p=3021813 — (c, ước tính)
