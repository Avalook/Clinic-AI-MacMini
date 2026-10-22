# Đối chiếu chạy thật với bản đồ

Ngày kiểm: 22/10/2026. Môi trường: `scripts/dev-up.sh`, database local cách ly `clinicai_thu_db` (cổng DB 54422, API 8100, Supabase 54421); chỉ dữ liệu giả `DEMO-*` / `@dr4women.local`. Không dùng DB staging/prod.

## Stack local

- `scripts/dev-up.sh` hoàn tất: 183 bảng, 40 hồ sơ `DEMO-*`, 4 lịch `LK-DEMO` trong ngày, 11/11 tài khoản thử đăng nhập được; API `/health` và `/luot-kham/bang` trả 200, dashboard `/login` lên được.
- Lần chạy đầu gặp mật khẩu trong volume thử cũ không trùng file `.env.thu-local` mới sinh. Đã đổi mật khẩu các role DB của chính container thử để khớp file local; không xoá volume. Lần chạy kế tiếp stack lên đầy đủ.
- Khi chạy script qua lệnh công cụ riêng, các tiến trình nền bị dọn sau khi lệnh kết thúc. Vì vậy lượt mô phỏng được ghép cùng phiên shell với `dev-up.sh`.

## Luồng đã đi qua

`ngay_kham.py` đã dựng một phần cấu hình và chạy pha đặt lịch đồng thời: ba CSKH tranh chỗ cuối, giữ chỗ, tạo trùng khách cùng SĐT, đặt lịch trùng khách/giờ, đặt lịch khi chưa có lịch trực, công bố lịch nghỉ và thử các khung ngoài giờ. Nhiều bước được kịch bản xác nhận đúng. Bản ghi kết thúc ở PHA E khi lịch của BS A ngày 23/10 chưa được xếp, nên script thoát trước phần khám từng bước và phần kiểm cuối.

Trong pha cấu hình, hai giả định của kịch bản không khớp seed local: gán thêm node `LUOTKHAM-03`/`LUOTKHAM-14` cho phòng lễ tân bị API từ chối vì đó là nhóm quản trị; cơ sở Hào Nam trong dữ liệu local không ở trạng thái hoạt động. Đây là dữ liệu/kịch bản mô phỏng, chưa đủ bằng chứng kết luận lỗi code hay ghi chú bản đồ.

Trong A5, phép kiểm ba lịch tự do đã đặt trước lúc công bố roster phải xuất hiện trong hàng `MAT_BAC_SI` bị thất bại. Ghi nhận ở `phat-hien.json` trạng thái `can_soat`: API còn lọc theo cơ sở của phiên; lần chạy không lưu ID cụ thể và cơ sở đang chọn để đối chiếu nên chưa quy được nguyên nhân cho API hay setup mô phỏng.

Lượt thử thêm `mo_phong.py K01` không qua được bước đặt lịch: helper thử lần lượt các slot cho đến 23:15 rồi API từ chối ngoài ca. Trước đó `ngay_kham.py` đã tạo nhiều lịch thử trong DB local, nên lượt này không phải lượt sạch. Không tính bước khám, dịch vụ, kết quả, thu, cấp thuốc hay check-out của K01 là đã kiểm.

## Đối chiếu với bản đồ

- Các bước đặt lịch và phản hồi API quan sát được phần lớn nhất quán với luồng CSKH đặt lịch, giữ chỗ, kiểm trùng/giới hạn khung đã ghi trong bản đồ. Riêng A5 có một phép kiểm chưa đạt, cần tái hiện cô lập; chưa đủ bằng chứng sửa bản đồ hoặc quy lỗi code.
- Chưa chạy tới tiếp đón/check-in → khám → chỉ định → thu dịch vụ → phòng dịch vụ → kết quả → Hoàn tất → check-out trong lần này.
- Chưa chạy bán thuốc/hoàn tiền/đóng ca bằng kịch bản hoàn chỉnh. Những bước này chưa được coi là đối chiếu thực tế.

## Kết quả chạy SQL lượt 4 trên DB thử

`kiem-du-lieu-prod-4.sql` chạy thành công trên `clinicai_thu_db`:

| Mục | Kết quả local |
| --- | ---: |
| Ngày thực thu lệch / tổng chênh có dấu / tổng chênh tuyệt đối | 0 / 0 / 0 |
| Lô tồn lệch / tổng lô | 0 / 4 |
| Phiếu VOIDED khác ngày thu và huỷ | 0 |

Đây chỉ là số trên DB thử local, không phải số prod.
