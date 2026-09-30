# ClinicAI Product Prototype
Folder độc lập. Không sửa app đang chạy, Supabase hoặc deployment.

## Chạy
`npm run dev` → http://127.0.0.1:8770/
`npm run build`
`node --test src/model.test.mjs`

Hiện dùng node_modules liên kết từ src/truong-ca-prototype để tận dụng runtime có sẵn. Khi chuyển máy, bỏ symlink và npm install với package.json.

12 workspace theo vai trò; data giả dùng chung trong localStorage clinicai-product-v1. Chuyển role thanh trái; khôi phục mẫu ở cuối sidebar. Mở coverage.html để thấy phạm vi đã mô phỏng và phần chưa đầy đủ.

Model frontend chỉ phục vụ prototype. Production tuân thủ frontend UI / FastAPI+SQL business logic. Không có payment,AI,IoT,Notion API thật; không dùng dữ liệu bệnh nhân thật. D11 vẫn là căn cứ nguồn chủ quản giai đoạn chuyển tiếp.
