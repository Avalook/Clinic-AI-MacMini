# Chạy test và CI — quy chuẩn

> Viết ngày 23/09/2026, sau một buổi mất **hơn hai giờ** chỉ để chờ test.
> Nguyên nhân không phải test chậm. Nguyên nhân là **cách chạy** sai.

## Chuyện đã xảy ra

Trong một phiên làm việc, mỗi lần cần kiểm lại là dựng **một database mới**:
`clinicai_ev_db10`, `db11`, … tới `db26`. Không dọn cái cũ. Kết quả:

| | Lúc nghẹt | Sau khi dọn |
|---|---|---|
| `docker ps` | **> 3 phút** | **0,09 giây** |
| 24 bài kiểm một lát | 14 phút 45 | 3 phút → **40 giây** |
| **Cả bộ 2.822 bài** | **14 phút** | **64 giây** |

Cùng một bộ test, cùng một máy. **Chậm gấp 13 lần chỉ vì 26 Postgres cùng chạy.**

Bài học không phải "test chậm thì chịu". Bài học là: **đo trước khi chịu đựng.**

---

## Quy chuẩn: MỘT database thử

```bash
# Dựng (chỉ khi THÊM MIGRATION hoặc chưa có)
DB_CONTAINER=clinicai_test DB_PORT=55500 scripts/tests/dung-db-kiem.sh

# Chạy
DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \
  poetry run pytest src/tests/ -q -m "not integration" --ignore=src/tests/integration
```

**Một cái tên, một cổng, dùng lại mãi.** Sửa Python thuần thì KHÔNG dựng lại —
database cũ dùng tiếp được, tiết kiệm ~4 phút mỗi lượt.

Dựng lại khi: thêm migration · đổi seed · nghi dữ liệu bẩn làm đỏ giả.

```bash
# Dọn mọi database thử lạc lại (KHÔNG đụng clinicai_thu_* hay supabase_*)
docker rm -f $(docker ps -aq --filter "name=^clinicai_ev_db")
```

---

## Bốn lớp, chạy theo lớp — đừng chạy cả bộ mỗi lần

| Lớp | Lệnh | Thời gian |
|---|---|---|
| **Bài vừa đỏ** | `pytest --lf -q` | ~10 giây |
| **Một vùng** | `pytest src/tests/services/test_<vùng>_db.py -q` | 20–60 giây |
| **Cả bộ backend** | như trên, `src/tests/` | **~64 giây** |
| **Giao diện** | `npx tsc --noEmit` · `npx eslint .` · `npm run test:boundary` | ~60 giây |

Cả bộ chỉ chạy **trước khi commit**, không chạy sau mỗi lần sửa một dòng.

### Lược đồ chạy KHÁC hẳn

`supabase/tests/*.sql` đếm bảng, policy, nút. Chúng **đỏ trên database có dữ
liệu test** — không phải vì code sai, mà vì pytest vừa tạo thêm hàng trăm dòng.

Phải dựng một database RIÊNG, **không seed, không pytest**, y như CI:

```
bootstrap → áp mọi migration → áp LẠI lần hai → chạy 34 bài .sql
```

---

## CI: 5 job, chạy song song, ~4 phút

| Job | Thời gian | Làm gì |
|---|---|---|
| `backend` | ~3,8 phút | ruff · mypy · pytest + coverage ≥ 80% |
| `portability` | ~3 phút | dựng ảnh linux/amd64, chứng minh chạy được ngoài Mac |
| `frontend` | ~2,1 phút | tsc · eslint · test giao diện |
| `database` | ~0,9 phút | migration áp hai lần + 34 bài lược đồ |
| `infra-safety` | ~0,1 phút | script phá huỷ + chốt pre-commit |

Tổng ~4 phút vì chạy song song. **Đây là mức bình thường của một dự án cỡ này**
— không cần tối ưu thêm; thứ cần tối ưu là vòng lặp ở MÁY, không phải CI.

`src/tests/integration/` bị loại khỏi CI (nợ `CI-DEBT-1`): fixture của nó chạy
`DELETE FROM appointment`, mà bảng ấy có trigger chỉ-thêm. Chạy cả bộ ở máy sẽ
thấy 23 lỗi từ đây — **không phải lỗi mới**.

---

## Ba cái bẫy đã cắn thật

**1. Sửa file trong lúc test đang chạy.** Bài kiểm ranh giới đọc mã nguồn từ
đĩa; sửa giữa chừng là đỏ giả. Đã cắn ba lần trong một ngày. Chờ xong, hoặc sửa
vùng khác hẳn (giao diện trong lúc backend chạy).

**2. Giết tiến trình đang dựng database.** DB dựng dở cho ra 40 lỗi vô nghĩa.
Kết quả ấy phải **bỏ hoàn toàn**, không phải bằng chứng gì.

**3. Đọc một lượt chạy bẩn thành lỗi code.** Trước khi sửa, hỏi:
*"đỏ vì code, hay vì database còn dữ liệu của lượt trước?"* Dựng sạch, chạy lại,
**rồi mới** kết luận. Tuyệt đối không vá code để chiều một bài kiểm đỏ giả.

---

## Thứ tự trước khi commit

```
1. vùng vừa sửa          ~40 giây
2. cả bộ backend         ~64 giây   (database thử dùng lại)
3. lược đồ               ~60 giây   (database RIÊNG, sạch, không seed)
4. giao diện             ~60 giây
5. commit → push → CI    ~4 phút
```

Tổng ở máy: **khoảng 4 phút**. Nếu lâu hơn nhiều, **dừng lại và đo** —
gần như chắc chắn là Docker đang nghẹt, không phải test chậm đi.
