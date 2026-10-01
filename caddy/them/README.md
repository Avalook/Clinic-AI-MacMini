# caddy/them — site PHỤ cho Caddy của prod

Caddy prod đọc mọi `*.caddy` trong thư mục này (`import /etc/caddy/them/*.caddy`
ở cuối `caddy/Caddyfile`). Không có tệp nào thì không có gì thêm — prod như cũ.

Tệp `*.caddy` ở đây KHÔNG vào git (`.gitignore`): chúng do script trên máy chủ
viết ra, ví dụ `staging.caddy` do `scripts/staging-dung-lan-dau.sh` viết từ mẫu
`caddy/staging-tren-prod.caddy.mau`. Không vào git nên cây prod vẫn sạch và
`deploy-backend.sh` không từ chối deploy.

Sửa tay một tệp ở đây xong phải: kiểm (`caddy validate`) rồi khởi động lại Caddy
prod — `admin off` nên không `caddy reload` được. Script staging làm đủ hai bước.

Lưu ý: deploy prod mà phải ROLLBACK thì compose chạy từ thư mục bản cũ (bản sao
`git archive`, không có tệp ở đây) → site phụ mất tới lần deploy prod sau, hoặc
chạy lại `scripts/staging-dung-lan-dau.sh`.
