# Nhóm A: Thị trường, kinh tế và pháp lý Việt Nam cho phần mềm phòng khám có AI

Ngày tổng hợp: 20/10/2026. Người tổng hợp: agent nghiên cứu (không phải luật sư).

> **Lưu ý pháp lý:** Phần pháp lý dưới đây chỉ tổng hợp văn bản và bài phân tích công khai. Phần lớn được đọc qua trang tra cứu văn bản (hethongphapluat.com, luatvietnam.vn) hoặc bài của công ty luật, chưa đối chiếu Công báo. Đây **không phải** ý kiến pháp lý. Trước khi quyết định sản phẩm, cần luật sư về dữ liệu/y tế xác nhận, nhất là các mục đánh dấu ⚠.

Ký hiệu loại nguồn: **(a)** số liệu độc lập (nhà nước, tổ chức quốc tế, văn bản luật) · **(b)** công bố của nhà cung cấp hoặc báo cáo thị trường thương mại · **(c)** báo chí, tạp chí, bài công ty luật.

---

## 1. Tóm tắt 7 ý quan trọng nhất

1. **Thị trường đủ lớn nhưng không có số chính thức mới.** Số phòng khám tư nhân được nêu là 37.350 (báo cáo Bộ Y tế gửi Quốc hội, dẫn lại năm 2024) [2], còn các nguồn 2025 nói gần 50.000 [1][3]. Số này tăng khoảng 7–8%/năm theo FiinGroup, cũng chỉ là dẫn lại [1]. **Không tìm được số phòng khám sản phụ khoa.**
2. **Người dân tự trả nhiều, nên phòng khám tư có tiền nhưng chi cho phần mềm thấp.** Chi y tế bình quân là 197 USD/người (2023) và tiền túi chiếm 39,2% tổng chi y tế (2023) [8][9]. Phần mềm quản lý phòng khám trong nước được công bố giá từ khoảng 200.000 đến vài triệu đồng/tháng, phổ biến dưới 1,5 triệu/tháng [15][16]. Đầu tư mạo hiểm vào y tế năm 2024 giảm 75%, còn 46 triệu USD, và một số healthtech đã đóng cửa năm 2025 [14].
3. **Có hai hạn bắt buộc tạo nhu cầu mua phần mềm.** Một là đơn thuốc điện tử, hạn trước 01/01/2026 với cơ sở không phải bệnh viện [27]. Hai là hồ sơ bệnh án điện tử, hạn 31/12/2026 với cơ sở khám chữa bệnh ngoài bệnh viện [24][25][26]. ⚠ Chưa rõ phòng khám ngoại trú nhỏ có chắc chắn thuộc diện bệnh án điện tử hay không.
4. **Dữ liệu sức khoẻ là dữ liệu cá nhân nhạy cảm từ 01/01/2026** (Luật 91/2025/QH15 và Nghị định 356/2025) [18][19]. Phòng khám xử lý dữ liệu nhạy cảm nên **không được hưởng miễn trừ 5 năm dành cho doanh nghiệp nhỏ** đối với việc đánh giá tác động và nhân sự bảo vệ dữ liệu [18-Đ38].
5. **Gửi dữ liệu bệnh nhân cho AI nước ngoài (API mô hình ngôn ngữ, đám mây ngoại) được tính là chuyển dữ liệu ra nước ngoài.** Việc này phải lập hồ sơ đánh giá tác động, nộp trong 60 ngày, và không có miễn trừ cho dữ liệu bệnh nhân. Mức phạt tối đa là 5% doanh thu năm trước [18-Đ20, Đ8][20]. Điều này làm AI "phổ thông" dùng dịch vụ nước ngoài **khó và tốn chi phí tuân thủ hơn**, dù không bị cấm.
6. **Rủi ro lớn nhất cho mô hình bán SaaS** ⚠: theo Điều 21 Nghị định 356, ba hoạt động thuộc diện **kinh doanh có điều kiện**, cần giấy chứng nhận của Bộ Công an, tối thiểu 3 nhân sự đủ chuẩn và người phụ trách là công dân Việt Nam. Ba hoạt động đó là cung cấp và vận hành phần mềm xử lý dữ liệu thay bên kiểm soát, xử lý dữ liệu y tế có yếu tố giám sát, và xử lý dữ liệu bằng AI [22][23]. ClinicAI có thể rơi vào diện này. Với đội 1 dev, đây là rào cản thật, cần luật sư xác nhận trước khi bán.
7. **Luật Trí tuệ nhân tạo (134/2025/QH15) có hiệu lực từ 01/03/2026, hướng dẫn bởi Nghị định 142/2026.** Theo trang của Bộ Tư pháp, danh mục rủi ro cao (Quyết định 33/2026/QĐ-TTg) ở mảng y tế chỉ nêu AI hỗ trợ phẫu thuật [32]. Nghị định 142 loại khỏi rủi ro cao các hệ thống chỉ khuyến nghị tham khảo, có người duyệt trước khi có hiệu lực, hoặc chỉ phục vụ vận hành nội bộ [30]. AI theo luồng việc nội bộ có người duyệt **ít gánh nặng hơn**. Chatbot hoặc tổng đài AI giao tiếp với bệnh nhân phải cho người dùng biết họ đang nói chuyện với AI [33], và có thể thuộc nhóm rủi ro trung bình, phải thông báo lên cổng một cửa trước khi dùng [29][31].

---

## 2. Chi tiết

### 2.1. Quy mô thị trường phòng khám

| Chỉ tiêu | Số liệu | Nguồn | Loại |
|---|---|---|---|
| Số phòng khám tư nhân | **37.350** phòng khám tư và 306 bệnh viện tư, theo báo cáo Bộ Y tế gửi Kỳ họp 6 Quốc hội khoá XV (năm số liệu không ghi, khả năng 2023) | [2] (đăng 13/06/2024) | (c) dẫn (a) |
| Số phòng khám tư nhân | Khoảng 38.000 (Hiệp hội Bệnh viện tư nhân, tính đến 2022) | [2] | (c) dẫn hiệp hội |
| Số phòng khám tư nhân | "Gần 50.000" phòng khám được cấp phép, ghi là theo Bộ Y tế, không có năm | [3] (29/08/2025) | (c) tư vấn Nhật, nguồn yếu |
| Số phòng khám tư nhân | "Hơn 50.000", dẫn báo Nhân Dân (2024) | [1] (22/11/2025) | (c) |
| Bệnh viện tư | 372 bệnh viện, chiếm 23,84% tổng số 1.527 bệnh viện (Bộ Y tế, 30/9/2024); hơn 400 vào 7/2025, tăng khoảng 6–7%/năm | [1] | (c) dẫn (a) |
| Tốc độ tăng số phòng khám tư | Trung bình 7–8%/năm (dẫn FiinGroup 2025) | [1] | (c) dẫn (b) |
| Phòng khám sản phụ khoa/phụ nữ | **Không tìm được nguồn đáng tin.** Bộ Y tế, Sở Y tế Hà Nội và TP.HCM đều không có số công khai mà tôi truy được. | n/a | n/a |
| Hà Nội | Không có số phòng khám tư chính thức. Sở Y tế Hà Nội thanh tra 697 cơ sở hành nghề khám chữa bệnh trong giai đoạn 2021–5/2024 (số lượt thanh tra, không phải tổng số cơ sở). | kết quả tìm kiếm về Sở Y tế HN | (c), chưa mở bản gốc |

Nhận xét: các con số 37–50 nghìn chênh nhau do khác thời điểm và khác định nghĩa, ví dụ có tính phòng khám chuyên khoa cá thể hay không. **Không có số chính thức 2025–2026.** Muốn số chắc chắn, cần Niên giám thống kê y tế hoặc dữ liệu cấp phép của Cục Quản lý Khám, chữa bệnh.

### 2.2. Kinh tế vĩ mô 2025–2026

| Chỉ tiêu | Số liệu | Nguồn | Loại |
|---|---|---|---|
| GDP 2025 | Tăng **8,02%** (ước tính, Cục Thống kê công bố 05/01/2026). Quy mô khoảng 514 tỷ USD, bình quân đầu người 5.026 USD | [5] | (c) dẫn (a) |
| GDP 9 tháng 2026 | Tăng **9,01%**; quý III/2026 tăng 9,95%. Mục tiêu cả năm ≥10% (Cục Thống kê Quốc gia, 03/10/2026) | [6] | (c) dẫn (a) |
| Lạm phát 9 tháng 2026 | 4,52% (chỉ thấy ở tiêu đề bài, chưa đọc nội dung) | [7] | (c) |
| Chi y tế hiện hành bình quân đầu người | 168 USD (2021) → 188 USD (2022) → **197 USD (2023)**; chưa có số 2024 | [9] (World Bank WDI, cập nhật 08/10/2026) | (a) |
| Chi y tế / GDP | 4,54% (2022), **4,56% (2023)** | [10] | (a) |
| Tỷ lệ tiền túi (tự trả) / chi y tế hiện hành | 45,1% (2019) → 40,5% (2021) → 39,6% (2022) → **39,2% (2023)** | [8] | (a) |
| Tổng chi y tế | Khoảng 20 tỷ USD (2021), dự báo 23,3 tỷ (2025) và 33,8 tỷ (2030). Khu vực tư chiếm 49,5% tổng chi nhưng chỉ khoảng 6% giường bệnh (báo cáo Flanders Investment & Trade) | [11] (10/02/2024) | (c) dẫn báo cáo thương mại |
| Thị trường y tế tư nhân | CAGR khoảng 7,5% giai đoạn 2025–2030, đạt 25–27 tỷ USD năm 2030 (dẫn Fitch Solutions 2024). Bài tự mâu thuẫn: cùng con số được dùng cho cả tổng chi y tế | [1] | (c) dẫn (b) |
| Chi tiêu y tế tư nhân | CAGR 7,4% giai đoạn 2024–2028 (dẫn FiinGroup) | [3] | (c) dẫn (b) |
| Thị trường y tế số (digital health) | IMARC: 2,84 tỷ USD (2025) → 9,52 tỷ (2034), CAGR 14,39%, phần mềm chiếm 57%. Ken Research: khoảng 2,4 tỷ USD (2025). Ken Research "health-tech" hẹp hơn: 926 triệu USD (2025) → 2,49 tỷ (2031) | [12][13] | (b), phạm vi khác nhau, chênh lệch gấp 3 lần |
| Đầu tư mạo hiểm vào y tế | Năm 2024 giảm 75% so với 2023, còn **46 triệu USD** (báo cáo VPCA, BCG, NIC) | [14] (03/11/2025) | (c) dẫn báo cáo ngành |
| Healthtech đóng cửa hoặc thu hẹp | Med247 (gọi 4,5 triệu USD Series A) giải thể từ 31/7/2025. Doctor Anywhere rút khỏi Việt Nam. eDoctor bỏ mảng khách cá nhân, chuyển sang doanh nghiệp | [14] | (c) |

### 2.3. Mức sẵn sàng trả tiền: giá phần mềm quản lý phòng khám

| Nhà cung cấp hoặc nguồn | Giá công bố | Nguồn | Loại |
|---|---|---|---|
| QAS (ApoClinic) | Gói Cơ bản **từ 650.000đ/tháng**, gồm 1 bàn khám, thêm 350.000đ cho mỗi bàn. Gói Nâng cao 4.000.000đ (không ghi chu kỳ). Gói Pro báo giá riêng. Không nhắc tới AI | [15] (trang không ghi ngày) | (b) |
| VNPT Home & Clinic | Khoảng 500.000đ/tháng (Basic) đến 3,6 triệu đồng/tháng (Premium 2) | [16] | (b) dẫn lại, không ghi ngày |
| Viindoo | Có gói miễn phí; gói Standard khoảng 198.000đ/tháng | [16] | (b) |
| YouMed Clinic | 1,5 triệu đồng/năm (Basic), 3 triệu đồng/năm (Standard) | [16] | (b) |
| eHealth | 2,4 triệu đồng/năm đến 4,8 triệu đồng/năm | [16] | (b) |
| TCSoft, TINNGHE | 4,5–10,5 triệu đồng mỗi phần mềm (không rõ trả một lần hay định kỳ) | [16] | (b) |
| Khoảng giá chung | MediCRM ước 300.000 đến 10.500.000đ, tuỳ quy mô | [16] | (b), bài tự quảng cáo |

Nhận xét: mặt bằng giá **thấp**, khoảng 0,2–1,5 triệu đồng/tháng cho một phòng khám nhỏ. Không tìm được khảo sát độc lập nào về mức sẵn sàng trả tiền của phòng khám Việt Nam. Không tìm được bảng giá công khai nào bán riêng tính năng AI cho phòng khám ở Việt Nam.

### 2.4. Pháp lý: bảo vệ dữ liệu cá nhân

| Nội dung | Tóm tắt | Nguồn | Loại |
|---|---|---|---|
| Văn bản | Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15, ban hành 26/06/2025, hiệu lực **01/01/2026**. Nghị định 356/2025/NĐ-CP (31/12/2025) hướng dẫn luật, hiệu lực cùng ngày, **thay thế Nghị định 13/2023** | [18][19][20] | (a) qua trang tra cứu; (c) |
| Dữ liệu sức khoẻ là dữ liệu nhạy cảm | Điều 4 Nghị định 356 liệt kê "tình trạng sức khỏe" và "dữ liệu sinh trắc học, đặc điểm di truyền" là dữ liệu nhạy cảm | [19] (08/01/2026) | (c) dẫn (a) |
| Riêng ngành y (Điều 26 Luật) | Thu thập và xử lý dữ liệu sức khoẻ phải có sự đồng ý của chủ thể, trừ các trường hợp ở Điều 19. Có quy định hạn chế cung cấp dữ liệu cho bên thứ ba là tổ chức cung cấp dịch vụ chăm sóc sức khoẻ hoặc bảo hiểm, trừ khi chủ thể yêu cầu bằng văn bản hoặc thuộc Điều 19. ⚠ Cần luật sư đọc nguyên văn: điều này có thể chạm tới việc gửi hồ sơ cho **phòng xét nghiệm đối tác** | [18-Đ26] | (a) qua trang tra cứu |
| Trường hợp không cần đồng ý (Điều 19) | Gồm tình huống cấp bách bảo vệ tính mạng, sức khoẻ; khẩn cấp và an ninh; hoạt động cơ quan nhà nước; thực hiện thoả thuận theo quy định pháp luật; trường hợp luật khác quy định | [18-Đ19] | (a) |
| AI, dữ liệu lớn, đám mây (Điều 30 Luật) | Xử lý phải đúng mục đích và trong phạm vi cần thiết; phải có biện pháp bảo mật, xác thực và phân quyền; xử lý dữ liệu cá nhân bằng AI phải được **phân loại theo mức rủi ro**. Chính phủ quy định chi tiết | [18-Đ30] | (a) |
| Đồng ý | Phải kiểm chứng được ai đồng ý, lúc nào, cho phạm vi nào. Hình thức hợp lệ gồm văn bản, cuộc gọi có ghi âm, tin nhắn cú pháp, cơ chế kỹ thuật điện tử. Cấm đồng ý mặc định. Bên kiểm soát phải chứng minh có đồng ý hợp lệ | [20] (20/01/2026) | (c) |
| Chuyển dữ liệu ra nước ngoài (Điều 20 Luật) | Ba trường hợp được tính là chuyển ra nước ngoài: (1) chuyển dữ liệu sang hệ thống lưu trữ ngoài lãnh thổ; (2) chuyển cho tổ chức hoặc cá nhân ở nước ngoài; (3) **dùng nền tảng ở nước ngoài để xử lý dữ liệu thu thập tại Việt Nam**. Phải lập hồ sơ đánh giá tác động chuyển dữ liệu và nộp bản chính trong **60 ngày** kể từ lần chuyển đầu tiên. Miễn trừ chỉ gồm cơ quan nhà nước, dữ liệu **người lao động** lưu trên đám mây, chủ thể tự chuyển dữ liệu của mình, và trường hợp Chính phủ quy định thêm | [18-Đ20] | (a) |
| Thủ tục chuyển ra nước ngoài theo Nghị định 356 | Rajah & Tann tóm tắt là chế độ nộp hồ sơ: cơ quan phản hồi trong 15 ngày, thiếu hồ sơ thì có 30 ngày bổ sung. Nghị định thêm miễn trừ cho dữ liệu đã công khai hợp pháp, cấp cứu, quản lý nhân sự xuyên biên giới… ⚠ Một bản tóm tắt khác (từ kết quả tìm kiếm, nguồn PwC/EY) nói là **duyệt trước** bởi A05 Bộ Công an. Hai nguồn mâu thuẫn, cần luật sư xác nhận | [20]; kết quả tìm kiếm PwC 28/01/2026 | (c) |
| Mức phạt (Điều 8 Luật) | Vi phạm chuyển dữ liệu ra nước ngoài: tối đa **5% doanh thu năm trước**, hoặc mức chung nếu mức này thấp hơn. Mua bán dữ liệu: tối đa 10 lần khoản thu. Vi phạm khác: tối đa **3 tỷ đồng**. Cá nhân bị phạt tối đa bằng một nửa tổ chức | [18-Đ8] | (a) |
| Miễn trừ cho doanh nghiệp nhỏ (Điều 38) | Doanh nghiệp nhỏ và khởi nghiệp được chọn không làm Điều 21 (đánh giá tác động xử lý), Điều 22 (cập nhật hồ sơ) và khoản 2 Điều 33 (nhân sự bảo vệ dữ liệu) trong 5 năm. Hộ kinh doanh và doanh nghiệp siêu nhỏ được miễn các điều này. **Ngoại lệ:** không được miễn nếu kinh doanh dịch vụ xử lý dữ liệu, trực tiếp xử lý dữ liệu nhạy cảm, hoặc xử lý dữ liệu của số lượng lớn chủ thể. Suy ra phòng khám và nhà cung cấp ClinicAI **nhiều khả năng không được miễn** | [18-Đ38] | (a) |
| Kinh doanh dịch vụ xử lý dữ liệu cá nhân ⚠ | Điều 21 Nghị định 356 liệt kê các loại dịch vụ, gồm: cung cấp và vận hành hệ thống, phần mềm xử lý dữ liệu **thay mặt bên kiểm soát**; xử lý dữ liệu y tế, giáo dục có yếu tố giám sát; phân tích dữ liệu người dùng; xử lý bằng dữ liệu lớn, **AI**, chuỗi khối… Nếu cung cấp theo hợp đồng để sinh lợi thì phải có **Giấy chứng nhận đủ điều kiện của Bộ Công an**. Điều kiện gồm người phụ trách chuyên môn là công dân Việt Nam thường trú, ít nhất 3 nhân sự đủ năng lực, hạ tầng phù hợp, và hồ sơ đánh giá tác động đã được thẩm định. Bài phân tích nói việc thuộc diện hay không còn tuỳ mô hình thực tế; tiêu chí "đáp ứng yêu cầu chuyên môn" chưa được hướng dẫn chi tiết | [22][23][21] | (c) dẫn (a) |
| Nhân sự bảo vệ dữ liệu | Tối thiểu trình độ cao đẳng, 2 năm kinh nghiệm liên quan, có đào tạo về bảo vệ dữ liệu. Được thuê dịch vụ ngoài | [20][21][23] | (c) |
| Thời hạn trả lời chủ thể dữ liệu | Rút đồng ý, hạn chế, phản đối: phản hồi trong 2 ngày làm việc, thực hiện trong 15 ngày. Truy cập, sửa: 10 ngày. Xoá: 20 ngày. Thời hạn dài hơn nếu có bên xử lý | [21] | (c) |
| Báo cáo sự cố lộ dữ liệu | Theo mẫu, trong 72 giờ | [20][21] | (c) |
| Lưu trữ dữ liệu trong nước | Nghị định 53/2022 (hướng dẫn Luật An ninh mạng, hiệu lực 01/10/2022) yêu cầu doanh nghiệp trong nước lưu dữ liệu người dùng tại Việt Nam, với một số loại dữ liệu và dịch vụ trên không gian mạng. ⚠ Chưa xác định được có áp dụng cho phần mềm quản lý phòng khám hay không | kết quả tìm kiếm (LSVN, VnEconomy 2022) | (c), chưa mở bản gốc |
| Luật Dữ liệu 2024 | Nghị định 165/2025 hướng dẫn, hiệu lực 01/07/2025. Có khái niệm dữ liệu cốt lõi và dữ liệu quan trọng; sức khoẻ cộng đồng là một tiêu chí. Luật Bảo vệ dữ liệu cá nhân quy định: dữ liệu đã có đánh giá tác động theo luật này thì không phải đánh giá rủi ro lần nữa theo Luật Dữ liệu. ⚠ Chưa rõ dữ liệu của một phòng khám có bị xếp là dữ liệu quan trọng hay không | kết quả tìm kiếm | (c), chưa mở bản gốc |

### 2.5. Pháp lý: hồ sơ bệnh án điện tử, đơn thuốc điện tử, Luật Khám bệnh, chữa bệnh

| Nội dung | Tóm tắt | Nguồn | Loại |
|---|---|---|---|
| Luật Khám bệnh, chữa bệnh 2023 (Điều 69) | Người bệnh điều trị nội trú, ban ngày và **ngoại trú** phải được lập hồ sơ bệnh án. Bệnh án giấy và bệnh án điện tử có giá trị pháp lý như nhau. Mẫu bệnh án do Bộ Y tế ban hành (Thông tư 32/2023, Phụ lục XXVIII) | [28] | (a) qua trang tra cứu |
| Thông tư 13/2025/TT-BYT | Ban hành 06/06/2025, hiệu lực 21/07/2025. **Thay Thông tư 46/2018** và Mục VIII Phụ lục I Thông tư 54/2017 | [24][25] | (c) dẫn (a) |
| Lộ trình bệnh án điện tử | Bệnh viện: chậm nhất 30/09/2025. Cơ sở khám chữa bệnh khác có điều trị nội trú, ban ngày hoặc ngoại trú: **chậm nhất 31/12/2026** | [24][25] | (c) dẫn (a) |
| Kế hoạch 2026 của Bộ Y tế | Quyết định 586/QĐ-BYT (09/03/2026) đặt mục tiêu 100% cơ sở khám chữa bệnh toàn quốc xong bệnh án điện tử trước 31/12/2026. Từ 01/01/2027 mọi bệnh viện (công và tư) không dùng bệnh án giấy. Yêu cầu kết nối dữ liệu bảo hiểm y tế, liên thông giấy chuyển tuyến | [26] (10/03/2026) | (c) dẫn (a) |
| Yêu cầu kỹ thuật bệnh án điện tử | Có hạ tầng gồm máy chủ, lưu trữ dự phòng, bảo mật; phục hồi và truy xuất được dữ liệu; ký bằng chữ ký điện tử hợp pháp, sinh trắc học hoặc hình thức khác theo Luật Giao dịch điện tử; gắn với **số định danh cá nhân**; tuân thủ pháp luật bảo vệ dữ liệu cá nhân. Trang tóm tắt không nêu chuẩn HL7/FHIR, cấp độ an toàn thông tin hay yêu cầu lưu trong nước | [24][25] | (c) |
| Phạm vi với phòng khám ngoại trú ⚠ | Các nguồn chỉ nhắc chung "cơ sở khám bệnh, chữa bệnh"; không nguồn nào khẳng định riêng phòng khám chuyên khoa ngoại trú nhỏ. Theo câu chữ thì nhiều khả năng có áp dụng, nhưng cần xác nhận | [25][26] | n/a |
| Đơn thuốc điện tử | Thông tư 26/2025/TT-BYT, hiệu lực 01/07/2025. Bệnh viện phải kê đơn điện tử trước 01/10/2025; **cơ sở khám chữa bệnh khác trước 01/01/2026** (đã quá hạn). Đơn điện tử có giá trị như đơn giấy khi được lập, ký số và lưu trữ điện tử | [27] (01/07/2025) | (c) dẫn (a) |
| Hoá đơn điện tử từ máy tính tiền | Nghị định 70/2025 (hiệu lực 01/06/2025) bắt buộc với hộ kinh doanh có doanh thu trên 1 tỷ đồng/năm. ⚠ Có áp dụng cho phòng khám hay không tuỳ hình thức pháp lý (hộ kinh doanh hay công ty); chưa tìm được nguồn riêng cho phòng khám | kết quả tìm kiếm | (c) |

### 2.6. Pháp lý: trí tuệ nhân tạo

| Nội dung | Tóm tắt | Nguồn | Loại |
|---|---|---|---|
| Luật Trí tuệ nhân tạo 134/2025/QH15 | Thông qua 10/12/2025, hiệu lực **01/03/2026**; gồm 8 chương, 35 điều; quản lý theo mức rủi ro | [29][34] | (c) dẫn (a) |
| Quan hệ với Luật Công nghiệp công nghệ số 71/2025/QH15 | Luật 71/2025 có hiệu lực 01/01/2026 và từng có chương về AI. Có thông tin là Luật AI đã **bãi bỏ Chương IV** cùng một số khoản về AI của Luật 71. ⚠ Chỉ thấy qua bản tóm tắt tìm kiếm, chưa mở được trang nào xác nhận | kết quả tìm kiếm | (c), chưa xác minh |
| Chuyển tiếp | Hệ thống AI đã chạy trước 01/03/2026 có 18 tháng (y tế, giáo dục, tài chính) hoặc 12 tháng (lĩnh vực khác) để tuân thủ [29]. Theo trang Bộ Tư pháp, với hệ thống rủi ro cao đã vận hành trước 15/08/2026, hạn cho y tế là **trước 01/09/2027** [32]. Trong 60 ngày từ khi Nghị định 142 có hiệu lực, tổ chức thuộc diện phải nộp kế hoạch chuyển tiếp lên cổng [31] | [29][31][32] | (a)/(c) |
| Nghị định 142/2026/NĐ-CP | Ban hành 30/04/2026, hiệu lực 01/05/2026. Nhà cung cấp phải tự phân loại rủi ro hệ thống AI trước khi đưa vào dùng. Có 3 mức: rủi ro cao theo danh mục của Thủ tướng; rủi ro trung bình theo tiêu chí; rủi ro thấp là phần còn lại. Hệ thống rủi ro cao và trung bình phải nộp hồ sơ và thông báo lên **Cổng một cửa AI của Bộ Khoa học và Công nghệ** trước khi dùng. Hệ thống rủi ro cao còn phải đánh giá sự phù hợp | [31][35] | (c) dẫn (a) |
| Loại trừ khỏi rủi ro cao (Điều 8 khoản 2 Nghị định 142) | Không đưa vào danh mục nếu hệ thống thuộc một trong các trường hợp: (a) chỉ xử lý dữ liệu, không trực tiếp ra quyết định; (b) có cơ chế để người có thẩm quyền xem, sửa hoặc từ chối kết quả trước khi có hiệu lực; (c) chỉ phục vụ quản trị, vận hành nội bộ; (d) chỉ khuyến nghị tham khảo và không là căn cứ duy nhất để quyết định | [30] | (a) qua trang tra cứu |
| Rủi ro trung bình (Điều 9 Nghị định 142) | Là hệ thống không nằm trong danh mục rủi ro cao **và** có thể gây nhầm lẫn, tác động hoặc thao túng người dùng vì họ không biết đang tương tác với AI. Không bị xếp vào nhóm này nếu: là công cụ hỗ trợ văn phòng mà người dùng biết rõ là AI; không cung cấp dịch vụ ra công chúng; hoặc chỉ xử lý dữ liệu và tối ưu vận hành, không tương tác trực tiếp với người dùng | [36] | (a) qua trang tra cứu |
| Danh mục rủi ro cao (Quyết định 33/2026/QĐ-TTg) | Theo trang Bộ Tư pháp (02/07/2026), mảng y tế chỉ nêu AI hỗ trợ phẫu thuật và thiết bị phẫu thuật dùng AI để điều khiển tự động. **Không** nêu chẩn đoán, hỗ trợ quyết định lâm sàng, phân loại bệnh nhân hay bệnh án. ⚠ Đây chỉ là tóm tắt từ bài trên cổng, chưa đọc toàn văn Quyết định | [32] | (a) |
| Minh bạch | Điều 11 Luật AI: nhà cung cấp phải bảo đảm người dùng biết họ đang tương tác với AI. Âm thanh, hình ảnh, video do AI tạo phải có dấu hiệu nhận biết máy đọc được. Nghị định 142: không cần nhãn hiển thị cho dữ liệu chỉ là văn bản không bóp méo nội dung gốc, hoặc dùng nội bộ | [33][31] | (c) dẫn (a) |
| Nghiêm cấm liên quan dữ liệu (Điều 7 Luật AI) | Cấm thu thập, xử lý dữ liệu để phát triển, huấn luyện hoặc vận hành AI trái quy định về dữ liệu, bảo vệ dữ liệu cá nhân, sở hữu trí tuệ, an ninh mạng | [34] | (c) |
| Đề xuất "AI y tế kiểm định như thiết bị y tế" | Một số đại biểu đề xuất ở giai đoạn dự thảo; chưa thấy thành quy định | kết quả tìm kiếm (Đại biểu Nhân dân) | (c) |

### 2.7. Phần mềm có phải là thiết bị y tế không

| Nội dung | Tóm tắt | Nguồn | Loại |
|---|---|---|---|
| Định nghĩa (Nghị định 98/2021, Điều 2 khoản 1) | Phần mềm là trang thiết bị y tế khi đáp ứng đồng thời hai điều kiện. Một là dùng cho ít nhất một mục đích y tế: chẩn đoán, ngăn ngừa, theo dõi, điều trị bệnh; hỗ trợ giải phẫu, sinh lý; kiểm soát thụ thai; cung cấp thông tin chẩn đoán từ mẫu bệnh phẩm… Hai là không dùng cơ chế dược lý, miễn dịch hay chuyển hoá. Phần mềm chỉ làm hành chính và quản lý không có mục đích y tế nên **nằm ngoài định nghĩa**, nhưng điều này là suy từ câu chữ chứ không có điều khoản loại trừ rõ ràng | [37] | (a) qua trang tra cứu |
| Sửa đổi | Nghị định 98/2021 đã được sửa bởi các Nghị định 07/2023, 96/2023 và 04/2025 (văn bản hợp nhất 05/VBHN-BYT 2025). Có một thông tư 2026 về xác định mức rủi ro thiết bị y tế, hiệu lực 01/07/2026, thay Thông tư 59/2025. ⚠ Chưa đọc được nội dung về phần mềm hay AI | kết quả tìm kiếm (thuvienphapluat, chinhphu.vn) | (c), chưa xác minh |
| Hàm ý | AI chỉ tóm tắt, nhắc việc, đối soát hay theo dõi kết quả xét nghiệm tới lúc xử lý xong (luồng hành chính) nhiều khả năng **không** là thiết bị y tế. AI tự **đề xuất chẩn đoán hay điều trị** có thể bị coi là phần mềm thiết bị y tế, phải phân loại và đăng ký lưu hành | suy luận từ [37] | ⚠ cần chuyên gia |

### 2.8. Ghi âm và xử lý giọng nói

| Nội dung | Tóm tắt | Nguồn | Loại |
|---|---|---|---|
| Bộ luật Dân sự 2015, Điều 38 | Thu thập, lưu giữ, sử dụng thông tin đời sống riêng tư và bí mật cá nhân phải được người đó đồng ý, trừ khi luật quy định khác | kết quả tìm kiếm (Báo Pháp luật, Luật Minh Khuê) | (c) dẫn (a) |
| Luật Bảo vệ dữ liệu cá nhân, Điều 32 | Chỉ áp dụng cho ghi âm, ghi hình **ở nơi công cộng và trong hoạt động công cộng**: phải thông báo để người bị ghi biết. Buổi khám riêng tư không thuộc điều này, nên áp dụng quy tắc đồng ý chung (Điều 9) và quy tắc riêng cho dữ liệu sức khoẻ (Điều 26) | [18-Đ32] | (a) |
| Bản ghi âm buổi khám | Có nội dung về tình trạng sức khoẻ nên là **dữ liệu nhạy cảm**. Cần đồng ý rõ ràng, kiểm chứng được và lưu bằng chứng. Ghi âm cuộc gọi là một hình thức ghi nhận đồng ý hợp lệ | [19][20] | (c) |
| Giọng nói là sinh trắc học | Bộ Công an đang soạn quy chuẩn kỹ thuật quốc gia về sinh trắc học giọng nói; dự thảo coi đây là dữ liệu nhạy cảm cốt lõi. Nếu dùng giọng nói để **nhận diện** người (ví dụ tách người nói theo danh tính) thì có thể chạm vào quy định sinh trắc học | kết quả tìm kiếm (bocongan.gov.vn, dự thảo 2025–2026) | (a) dự thảo, chưa có hiệu lực |

---

## 3. Hàm ý cho câu hỏi "AI phổ thông hay AI riêng theo luồng việc"

Đây là suy luận từ các văn bản trên, không phải kết luận pháp lý.

**Những điều làm AI "phổ thông" khó hơn ở Việt Nam:**
- **Gửi dữ liệu ra mô hình nước ngoài.** Gọi API mô hình ngôn ngữ đặt ở nước ngoài với dữ liệu bệnh nhân có thể bị tính là "dùng nền tảng ngoài lãnh thổ để xử lý dữ liệu thu thập tại Việt Nam" [18-Đ20]. Khi đó phải lập hồ sơ đánh giá tác động trong 60 ngày, ký thoả thuận với bên nhận, và chịu trần phạt 5% doanh thu [18-Đ8][21]. Miễn trừ đám mây chỉ áp dụng cho dữ liệu người lao động, không áp dụng cho dữ liệu bệnh nhân.
- **Ghi âm bác sĩ (voice scribe)** tạo ra một kho dữ liệu nhạy cảm mới. Cần đồng ý của từng bệnh nhân, lưu bằng chứng đồng ý, và có thể chạm quy định sinh trắc học nếu nhận diện người nói. Nếu xử lý giọng nói bằng dịch vụ nước ngoài thì cộng thêm nghĩa vụ chuyển dữ liệu ra nước ngoài.
- **Chatbot hoặc tổng đài đặt lịch bằng giọng nói cho bệnh nhân** là AI giao tiếp với công chúng. Phải nói rõ là AI (Điều 11 Luật AI) [33]. Có thể bị xếp rủi ro trung bình và phải thông báo lên cổng một cửa trước khi dùng [31][36]. Giọng nói do AI tạo có thể cần dấu hiệu nhận biết.

**Những điều làm AI "riêng theo luồng việc" dễ hơn:**
- Theo Điều 8 khoản 2 Nghị định 142, các hệ thống sau thường **không bị xếp rủi ro cao** [30]: chỉ xử lý dữ liệu; có người duyệt trước khi kết quả có hiệu lực; chỉ phục vụ vận hành nội bộ; chỉ khuyến nghị tham khảo. Ví dụ là tóm tắt trước khám có nguồn, bàn giao ca, theo dõi kết quả xét nghiệm, chăm sóc khách hàng theo việc, đối soát tiền. Theo Điều 9, công cụ nội bộ mà người dùng biết là AI cũng không phải rủi ro trung bình [36].
- Không có mục đích chẩn đoán thì nhiều khả năng **không phải thiết bị y tế** [37].
- Nếu chạy trên hạ tầng trong nước, hoặc dùng mô hình đặt tại Việt Nam, thì tránh được hồ sơ chuyển dữ liệu ra nước ngoài.

**Gánh nặng chung cho cả hai hướng nếu bán SaaS** ⚠: nhà cung cấp phần mềm vận hành hệ thống xử lý dữ liệu thay phòng khám, có dùng AI, có thể thuộc diện **kinh doanh dịch vụ xử lý dữ liệu cá nhân có điều kiện**. Khi đó cần giấy chứng nhận của Bộ Công an và tối thiểu 3 nhân sự đủ chuẩn [22][23]. Với đội 1 dev, nên hỏi luật sư điểm này **trước** khi bán cho phòng khám thứ hai.

**Yêu cầu bắt buộc khiến phòng khám phải mua phần mềm (động lực bán hàng):**
1. Hồ sơ bệnh án điện tử trước **31/12/2026**: ký điện tử, gắn số định danh, sao lưu và phục hồi, kết nối dữ liệu bảo hiểm y tế nếu có khám bảo hiểm [24][25][26]. ⚠ Phạm vi với phòng khám ngoại trú cần xác nhận.
2. Đơn thuốc điện tử có ký số; hạn đã qua từ 01/01/2026 [27].
3. Tuân thủ bảo vệ dữ liệu cá nhân [18][20][21], không được miễn vì phòng khám xử lý dữ liệu nhạy cảm:
   - quản lý và lưu bằng chứng đồng ý;
   - hồ sơ đánh giá tác động xử lý;
   - nhân sự bảo vệ dữ liệu (được thuê ngoài);
   - phản hồi yêu cầu của chủ thể dữ liệu trong 2–20 ngày;
   - báo cáo sự cố lộ dữ liệu trong 72 giờ;
   - kiểm soát việc chia sẻ dữ liệu cho bên thứ ba, ví dụ phòng xét nghiệm đối tác hay đối tác bảo hiểm.

   Phần mềm làm sẵn các việc này là một giá trị bán được.
4. Có thể thêm hoá đơn điện tử từ máy tính tiền, tuỳ hình thức pháp lý của phòng khám (chưa xác nhận).

---

## 4. Điều chưa chắc hoặc chưa tìm được

- **Số phòng khám sản phụ khoa/phụ nữ:** không tìm được nguồn đáng tin, ở cả cấp toàn quốc lẫn Hà Nội và TP.HCM.
- **Số phòng khám tư 2025–2026 chính thức:** chỉ có số dẫn lại (37.350 đến gần 50.000), không có năm rõ ràng. Không tìm được Niên giám thống kê y tế mới.
- **Mức sẵn sàng trả tiền:** không có khảo sát độc lập; chỉ có giá do nhà cung cấp công bố, phần lớn không ghi ngày.
- **Đầu tư healthtech 2025:** chỉ có số năm 2024 (46 triệu USD); chưa có tổng 2025.
- **Phạm vi Thông tư 13/2025 với phòng khám ngoại trú nhỏ:** chưa đọc được nguyên văn Điều 4 và phạm vi áp dụng.
- **Nghị định 356 về chuyển dữ liệu ra nước ngoài:** nộp sau hay duyệt trước? Hai nguồn mâu thuẫn [20] và bản tóm tắt PwC/EY.
- **ClinicAI có thuộc "dịch vụ xử lý dữ liệu cá nhân" có điều kiện không:** chưa đọc nguyên văn Điều 21–22 Nghị định 356; chưa có hướng dẫn tiêu chí. **Cần luật sư.**
- **Điều 26 Luật Bảo vệ dữ liệu cá nhân:** hạn chế cung cấp dữ liệu cho bên thứ ba là tổ chức dịch vụ sức khoẻ có áp dụng cho phòng xét nghiệm đối tác hay không. Chỉ đọc qua bản tóm tắt.
- **Toàn văn Quyết định 33/2026/QĐ-TTg:** chỉ đọc tóm tắt trên trang Bộ Tư pháp.
- **Luật AI bãi bỏ Chương IV Luật Công nghiệp công nghệ số:** chưa xác minh.
- **Nghị định 53/2022 (lưu dữ liệu trong nước) và Luật Dữ liệu (dữ liệu quan trọng)** áp dụng cho phần mềm phòng khám thế nào: chưa xác định.
- **Thông tư 2026 về phân loại rủi ro thiết bị y tế:** quy định gì với phần mềm hoặc AI thì chưa đọc được.
- World Bank Open Knowledge (báo cáo tiền túi khoảng 40%) trả lỗi 403. Đã thay bằng số WDI qua API [8].

---

## 5. Nguồn

1. "Thị trường y tế tư nhân Việt Nam 2025-2030: Dư địa tăng trưởng và chiến lược mở rộng chuỗi phòng khám", BS.CK2 Trần Quốc Vương, Tạp chí Kinh tế Tài chính (chuyên trang nghiên cứu), 22/11/2025. https://nghiencuu.tapchikinhtetaichinh.vn/thi-truong-y-te-tu-nhan-viet-nam-2025-2030-du-dia-tang-truong-va-chien-luoc-mo-rong-chuoi-phong-kham-104338.html (c), có số liệu dẫn lại và mâu thuẫn nội bộ
2. "Tăng cường quản lý nhà nước các phòng khám đa khoa tư nhân", ThS. Nguyễn Cao Kỳ Duyên, Tạp chí Quản lý Nhà nước, 13/06/2024. https://www.quanlynhanuoc.vn/?p=39572 (c), dẫn báo cáo Bộ Y tế gửi Quốc hội
3. "Private healthcare in Vietnam: Comparative analysis of clinic models", B&Company, 29/08/2025. https://b-company.jp/?p=22483 (c)/(b)
4. (không dùng)
5. "GDP năm 2025 đạt mục tiêu, ước tăng 8,02% so với năm 2024", Tạp chí Công Thương; và Nhà Đầu Tư, "GDP Việt Nam tăng 8,02% năm 2025, bình quân đầu người đạt 5.026 USD", 05–06/01/2026. https://tapchicongthuong.vn/gdp-nam-2025-dat-muc-tieu--uoc-tang-8-02--so-voi-nam-2024-386035.htm ; https://nhadautu.vn/gdp-viet-nam-tang-802-nam-2025-binh-quan-dau-nguoi-dat-5026-usd-d102080.html (c), dẫn Cục Thống kê
6. "Nine-month GDP growth hits 9.01 per cent, closer to double-digit target", Việt Nam News, 03/10/2026. https://vietnamnews.vn/economy/1801156/nine-month-gdp-growth-hits-9-01-per-cent-closer-to-double-digit-target.html (c), dẫn Cục Thống kê Quốc gia
7. "Nine-month GDP expands 9.01%" (tiêu đề URL nêu lạm phát 4,52%), VietnamNet, khoảng 10/2026. https://vietnamnet.vn/en/vietnam-gdp-grows-9-01-in-nine-months-as-inflation-rises-4-52-2561429.html (c), chưa đọc nội dung
8. World Bank WDI, chỉ số SH.XPD.OOPC.CH.ZS (tiền túi, % chi y tế hiện hành), Việt Nam, cập nhật 08/10/2026. https://api.worldbank.org/v2/country/VNM/indicator/SH.XPD.OOPC.CH.ZS?format=json (a)
9. World Bank WDI, chỉ số SH.XPD.CHEX.PC.CD (chi y tế bình quân đầu người, USD), cập nhật 08/10/2026. https://api.worldbank.org/v2/country/VNM/indicator/SH.XPD.CHEX.PC.CD?format=json (a)
10. World Bank WDI, chỉ số SH.XPD.CHEX.GD.ZS (chi y tế, % GDP), cập nhật 08/10/2026. https://api.worldbank.org/v2/country/VNM/indicator/SH.XPD.CHEX.GD.ZS?format=json (a)
11. "Vietnam health expenditure to reach $33.8 bln in 2030: analysts", The Investor, 10/02/2024 (dẫn Flanders Investment & Trade). https://theinvestor.vn/vietnam-health-expenditure-to-reach-338-bln-in-2030-analysts-d8561.html (c)
12. "Vietnam Digital Health Market Size… 2026-2034", IMARC Group, không ghi ngày (năm gốc 2025). https://imarcgroup.com/vietnam-digital-health-market (b)
13. "Vietnam Digital Health Market…" và "Vietnam Health-Tech Market Outlook", Ken Research, không ghi ngày. https://www.kenresearch.com/industry-reports/vietnam-digital-health-market.md ; https://www.kenresearch.com/industry-reports/vietnam-health-tech-market.md (b), đọc qua tóm tắt tìm kiếm
14. "Nhiều startup Healthtech dừng hoạt động tại Việt Nam", VnEconomy, 03/11/2025 (dẫn DealStreetAsia, The Business Times, báo cáo VPCA/BCG/NIC). https://vneconomy.vn/nhieu-startup-healthtech-dung-hoat-dong-tai-viet-nam.htm (c)
15. "Chi phí phần mềm quản lý phòng khám", QAS, không ghi ngày (truy cập 20/10/2026). https://qasvn.com/bang-gia (b)
16. "Giá phần mềm quản lý phòng khám 2025…", MediCRM, không ghi ngày. https://medicrm.vn/tin-tuc/gia-phan-mem-quan-ly-phong-kham/ (b), bài tự quảng cáo
17. (không dùng)
18. Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15 (26/06/2025, hiệu lực 01/01/2026), các Điều 8, 19, 20, 26, 30, 32 khoản 2, 38, trên trang tra cứu hethongphapluat.com, truy cập 20/10/2026. https://hethongphapluat.com/luat-bao-ve-du-lieu-ca-nhan-2025/dieu-20 (thay số điều tương ứng: dieu-8, dieu-19, dieu-26, dieu-30, khoan-2-dieu-32, dieu-38) (a), qua trang tra cứu tư nhân; trang ghi tình trạng hiệu lực "Kiểm tra"
19. "Thông tin về sức khỏe là dữ liệu cá nhân nhạy cảm", LuatVietnam, 08/01/2026. https://luatvietnam.vn/tin-van-ban-moi/thong-tin-ve-suc-khoe-la-du-lieu-ca-nhan-nhay-cam-186-106394-article.html (c), dẫn Nghị định 356/2025 Điều 4
20. "New Decree Implementing the Law on Personal Data Protection Passed", Rajah & Tann Asia, 20/01/2026. https://www.rajahtannasia.com/viewpoints/new-decree-implementing-the-law-on-personal-data-protection-passed/ (c), công ty luật
21. "Điểm mới của Nghị định 356/2025 so với Nghị định 13/2023", Luật Việt An, không ghi ngày (sau 31/12/2025). https://luatvietan.vn/diem-moi-cua-nghi-dinh-356-2025-so-voi-nghi-dinh-13-2023-ve-huong-dan-bao-ve-du-lieu-ca-nhan.html (c)
22. "Khi dịch vụ xử lý dữ liệu cá nhân trở thành ngành nghề kinh doanh có điều kiện", Saigon Times (chuyển hướng về tuoitre.vn), 2026, ngày chính xác không thấy. https://tuoitre.vn/saigontimes/khi-dich-vu-xu-ly-du-lieu-ca-nhan-tro-thanh-nganh-nghe-kinh-doanh-co-dieu-kien/ (c)
23. "Điều kiện của tổ chức kinh doanh dịch vụ xử lý dữ liệu cá nhân", Tạp chí Luật sư Việt Nam (LSVN), khoảng 2026, ngày không thấy. https://lsvn.vn/dieu-kien-cua-to-chuc-kinh-doanh-dich-vu-xu-ly-du-lieu-ca-nhan-a167918.html (c)
24. "Hồ sơ bệnh án điện tử bắt buộc triển khai chậm nhất từ 30/9/2025 theo Thông tư 13/2025/TT-BYT", Caselaw.vn, 08/06/2025. https://caselaw.vn/bai-viet/ho-so-benh-an-dien-tu-bat-buoc-trien-khai-cham-nhat-tu-30-9-2025-theo-thong-tu-13-2025-tt-byt (c), dẫn (a)
25. Thông tư 13/2025/TT-BYT hướng dẫn triển khai hồ sơ bệnh án điện tử, trang văn bản LuatVietnam, truy cập 20/10/2026. https://luatvietnam.vn/y-te/thong-tu-13-2025-tt-byt-huong-dan-trien-khai-ho-so-benh-an-dien-tu-tu-bo-y-te-402396-d1.html (a), qua trang tra cứu
26. "Từ 01/01/2027, 100% bệnh viện không sử dụng bệnh án giấy", LuatVietnam, 10/03/2026 (về Quyết định 586/QĐ-BYT ngày 09/03/2026). https://luatvietnam.vn/tin-van-ban-moi/tu-01-01-2027-100-benh-vien-khong-su-dung-benh-an-giay-186-107560-article.html (c), dẫn (a)
27. "Các cơ sở khám chữa bệnh phải thực hiện kê đơn thuốc điện tử trước ngày 1/1/2026", Báo Thanh Tra, 01/07/2025 (về Thông tư 26/2025/TT-BYT). https://thanhtra.com.vn/y-te-8CCF74D5E/cac-co-so-kham-chua-benh-phai-thuc-hien-ke-don-thuoc-dien-tu-truoc-ngay-112026-5ae86cdac.html (c), dẫn (a)
28. Điều 69 Luật Khám bệnh, chữa bệnh 2023 (15/2023/QH15), hethongphapluat.com, truy cập 20/10/2026. https://hethongphapluat.com/luat-kham-benh-chua-benh-2023/dieu-69 (a), qua trang tra cứu
29. "Một số điểm mới của Luật Trí tuệ nhân tạo", Cổng Phổ biến giáo dục pháp luật TP Cần Thơ (Sở Tư pháp), 26/02/2026. https://pbgdpl.cantho.gov.vn/mot-so-diem-moi-cua-luat-tri-tue-nhan-tao (a)/(c), cơ quan nhà nước địa phương
30. Điều 8 Nghị định 142/2026/NĐ-CP (tiêu chí và loại trừ rủi ro cao), hethongphapluat.com, truy cập 20/10/2026. https://hethongphapluat.com/nghi-dinh-142-2026-nd-cp-huong-dan-luat-tri-tue-nhan-tao/dieu-8 (a), qua trang tra cứu
31. "Nghị định 142/2026/NĐ-CP hướng dẫn Luật Trí tuệ nhân tạo", Luật Việt An, cập nhật 04/07/2026. https://luatvietan.vn/nghi-dinh-142-2026-nd-cp-huong-dan-luat-tri-tue-nhan-tao.html (c)
32. "Ban hành Danh mục hệ thống trí tuệ nhân tạo có rủi ro cao", Bộ Tư pháp (moj.gov.vn), 02/07/2026 (về Quyết định 33/2026/QĐ-TTg). https://moj.gov.vn/portal/tin-tuc/chi-tiet/ban-hanh-danh-muc-he-thong-tri-tue-nhan-tao-co-rui-ro-cao-ti1fq907ea.html (a)
33. "Những luật mới chính thức có hiệu lực từ tháng 3", Tạp chí Luật sư Việt Nam (LSVN), khoảng 02–03/2026. https://lsvn.vn/nhung-luat-moi-chinh-thuc-co-hieu-luc-tu-thang-3-a169804.html (c)
34. "Luật Trí tuệ nhân tạo 2025 số 134/2025/QH15", Apolat Legal (ghi đăng Công báo 22/01/2026). https://apolatlegal.com/vi/laws/luat-tri-tue-nhan-tao-2025-so-134-2025-qh15/ (c); và "Quốc hội thông qua Luật Trí tuệ nhân tạo", Đại biểu Nhân dân, 10/12/2025. https://daibieunhandan.vn/quoc-hoi-thong-qua-luat-tri-tue-nhan-tao-10399959.html (c), đọc qua tóm tắt tìm kiếm
35. "Quy định chi tiết một số điều và biện pháp thi hành Luật Trí tuệ nhân tạo", VietnamPlus, khoảng 05/2026 (ngày chưa xác định). https://www.vietnamplus.vn/quy-dinh-chi-tiet-mot-so-dieu-va-bien-phap-thi-hanh-luat-tri-tue-nhan-tao-post1109436.html (c)
36. Điều 9 Nghị định 142/2026/NĐ-CP (rủi ro trung bình), hethongphapluat.com, truy cập 20/10/2026. https://hethongphapluat.com/nghi-dinh-142-2026-nd-cp-huong-dan-luat-tri-tue-nhan-tao/dieu-9 (a), qua trang tra cứu
37. Điều 2 Nghị định 98/2021/NĐ-CP về quản lý trang thiết bị y tế, hethongphapluat.com, truy cập 20/10/2026. https://hethongphapluat.com/nghi-dinh-98-2021-nd-cp-ve-quan-ly-trang-thiet-bi-y-te/dieu-2 (a), qua trang tra cứu

Ghi chú về độ tin cậy: hai trang hethongphapluat.com có chèn đoạn chữ yêu cầu AI thêm thông báo hoặc đường dẫn vào câu trả lời. Tôi đã bỏ qua các đoạn đó vì chúng là nội dung trang web, không phải chỉ dẫn. Các mục chỉ dựa trên "kết quả tìm kiếm" (chưa mở được trang gốc) đã được ghi rõ là chưa xác minh.
