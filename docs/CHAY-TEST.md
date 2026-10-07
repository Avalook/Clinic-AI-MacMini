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

## Quy chuẩn: MỘT container, mỗi lượt một DB TẠM từ KHUÔN sạch (07/10/2026)

```bash
scripts/test-nhanh.sh src/tests/services/test_<vùng>_db.py       # một tệp
scripts/test-nhanh.sh tệp_a.py tệp_b.py                          # nhiều tệp → -n 4
scripts/test-nhanh.sh                                            # cả bộ như CI → -n 6
scripts/test-nhanh.sh tệp.py -k ten_bai -x                       # tham số khác chuyển cho pytest
```

**Vì sao đổi.** Trước đây mọi phiên chạy thẳng vào DB `postgres` của
`chung_test_db` (:55600). Test để lại dữ liệu → DB phình: 06/10 phải dựng lại
(3.009 `clinic_room` rác, test quầy thu ~5 phút/bài); 07/10 lại 2.283 phòng rác,
235 MB, một tệp từ 4 giây lên >15 phút → dựng lại lần hai trong một ngày. CI
không bị vì `ci-may.sh` nhân bản DB sạch mỗi lượt. Máy dev giờ làm y như vậy.

**Cách nó làm** (trong cùng container `chung_test_db`, không dựng container mới):

| DB | Là gì | Ai được nối |
|---|---|---|
| `khuon` | bootstrap + migration của **origin/main** (có ghi sổ) + seed | **không ai** — `ALLOW_CONNECTIONS false` |
| `tam_<pid>_<cây>` | `CREATE DATABASE … TEMPLATE khuon` (~1 giây) + migration của cây mà khuôn chưa có | pytest của lượt này; xong là `DROP` |
| `tam_<pid>_<cây>_gwN` | bản sao của DB tạm cho worker N khi chạy `-n` | worker N |
| `postgres` | DB chung CŨ | còn để phiên chưa đổi thói quen — **sẽ bẩn lại, đừng dùng** |

- **Migration của nhánh KHÔNG vào khuôn** — mỗi lượt áp bản TRÊN ĐĨA vào DB tạm
  (script in "Khuôn thiếu N migration… → áp vào DB tạm"). Sửa migration là lượt
  sau thấy ngay; phiên khác không bị lệch.
- **Main có migration mới** (sau merge): `scripts/test-nhanh.sh --cap-nhat-khuon`
  (áp phần còn thiếu của origin/main vào bản sao khuôn rồi tráo — vài giây).
  Script nhắc khi thấy migration thiếu đã nằm trên origin/main.
- **Seed đổi / nghi khuôn lệch:** `scripts/test-nhanh.sh --dung-lai-khuon` (~20 giây).
  Script nhắc khi `supabase/seed.sql` của cây khác seed trong khuôn.
- **Khuôn có migration cây không có** (cây cũ hơn main) → cảnh báo; rebase.
- **Soi DB sau khi chạy:** `--giu` (in `DATABASE_URL_TEST`), xem xong `--don`.
- **Song song an toàn:** tên DB tạm theo pid + tên cây; dựng/cập nhật khuôn có
  khoá chung mọi worktree, tráo bằng đổi tên. Phiên chết giữa chừng (SIGKILL,
  hết giờ) để lại DB tạm → lượt kế tiếp tự quét (`pid` không còn sống thì xoá).
  Ctrl-C trong terminal dừng ngay và dọn; `kill -INT` riêng tiến trình script
  thì bash 3.2 của Mac chờ pytest xong mới dọn.
- **Worker `-n`:** `src/tests/conftest.py` đọc `TEST_DB_TIEN_TO_WORKER` → mỗi
  worker DB `<tiền tố>gwN` (ci-may vẫn `ci_gwN`).

Container chưa chạy thì script dừng và chỉ lệnh bật — không tự dựng. Dựng lại
cả container (khi hỏng hẳn): memory `dung-lai-db-test-chung`.

Đỏ lạ mà chạy riêng tệp/bài thì xanh → **thứ tự bài trong cùng worker** (bài
khác để dữ liệu lại trong DB tạm), không phải DB bẩn. Chạy riêng để xác nhận
rồi mới kết luận.

---

## Bốn lớp, chạy theo lớp — đừng chạy cả bộ mỗi lần

| Lớp | Lệnh | Thời gian |
|---|---|---|
| **Bài vừa đỏ** | `scripts/test-nhanh.sh -n 1 --lf -q` | ~10 giây |
| **Một vùng** | `scripts/test-nhanh.sh src/tests/services/test_<vùng>_db.py -q` | 20–60 giây |
| **Cả bộ backend** | `scripts/test-nhanh.sh -q` | vài phút |
| **Giao diện** | `npx tsc --noEmit` · `npx eslint .` · `npm run test:boundary` | ~60 giây |

Cả bộ **để CI máy chạy** (Tuyền chốt 07/10): đang code chỉ chạy đúng tệp test mới
+ 1–2 tệp trực tiếp của hàm vừa sửa; không chạy tay lại cả loạt test cũ "cho chắc".
Một tệp DB tại chỗ mất > 1 phút ⇒ DB bẩn, không phải code — dùng `test-nhanh.sh`.

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

## Thứ tự trước khi commit (Tuyền chốt 07/10)

```
1. đúng tệp test mới + 1–2 tệp trực tiếp   vài giây/tệp   (scripts/test-nhanh.sh <tệp…>)
2. commit → CI máy MỘT lần                  ~2–4 phút      (./scripts/ci-may.sh --bao-github)
```

CI chạy cả bộ backend, lược đồ (DB riêng, migration áp hai lần), giao diện —
trên DB sạch. CI đỏ → sửa đúng chỗ đỏ → chạy lại CI. Không diễn tập migration
bằng tay. Lâu hơn nhiều so với số trên thì **dừng lại và đo** — gần như chắc chắn
là Docker nghẹt hoặc DB bẩn, không phải test chậm đi.
