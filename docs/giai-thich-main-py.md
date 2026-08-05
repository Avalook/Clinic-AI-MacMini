# Giải thích `src/clinicai/main.py` — từng dòng, và API đi đến đâu

File này là **cửa duy nhất** vào backend. Mọi request của phòng khám đều đi qua đúng
397 dòng này trước khi chạm tới bất kỳ logic nghiệp vụ nào. Đọc hiểu file này = hiểu
được 80% cách hệ thống vận hành.

Tài liệu đọc kèm file thật: mỗi mục ghi rõ số dòng để anh mở song song.

---

## Phần 0 — Bản đồ: một request đi từ đâu tới đâu

Trước khi vào từng dòng, phải thấy được toàn cảnh. Khi lễ tân bấm nút "Đặt lịch":

```
[1] Trình duyệt lễ tân
      │  POST /api/appointments        ← đường dẫn của Next.js, KHÔNG phải backend
      ▼
[2] Caddy (TLS, cổng 443)              docker: caddy
      │
      ▼
[3] Next.js dashboard                  docker: dashboard  (port 3000)
      │  app/api/appointments/route.ts
      │  gọi proxyJsonToBackend("POST", "/api/v1/appointments/bookings", body)
      │  → lib/backend-proxy.ts gắn 2 thứ vào header:
      │       Authorization: Bearer <access_token Supabase của chính lễ tân>
      │       X-API-Key: <BACKEND_API_KEY dùng chung>
      ▼
[4] FastAPI  =  file main.py này       docker: api  (port 8000, CLINIC_API_URL trỏ vào)
      │  RequestIdMiddleware → TimingMiddleware → api_key_middleware
      │  → DbErrorMiddleware → _GUARDED (runaway_guard → get_current_identity)
      │  → router booking → service → SQL
      ▼
[5] Supabase Postgres (cloud)
```

Hai điều rút ra ngay:

- **`/api/...` của Next.js và `/api/v1/...` của FastAPI là hai không gian tên khác
  nhau.** Trình duyệt không bao giờ gọi thẳng `/api/v1/...`. Nó gọi Next, Next gọi
  FastAPI (server→server, trong mạng nội bộ Docker). Vì thế `BACKEND_API_KEY` không
  bao giờ lộ ra trình duyệt.
- **Danh tính đi kèm suốt chặng.** Next không tự xưng "tôi là quản lý"; nó chuyển
  nguyên token của người đang đăng nhập xuống, để FastAPI tự giải mã → tra bảng
  `staff` → tự kết luận vai trò. Frontend nói dối được, backend thì không tin.

---

## Phần 1 — Dòng 53–59: import thư viện chuẩn Python

```python
import os
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator
from uuid import UUID
```

| Dòng | Cái gì | Dùng ở đâu trong file này |
|---|---|---|
| 53 | `os` | dòng 165: đọc biến môi trường `DEFAULT_LOCATION_ID` |
| 55 | `AsyncExitStack` | dòng 151: gom nhiều tài nguyên async vào **một** chỗ dọn dẹp |
| 55 | `asynccontextmanager` | dòng 144: biến hàm `lifespan` thành context manager |
| 57 | `AsyncIterator` | dòng 145: kiểu trả về của `lifespan` — bắt buộc để mypy pass |
| 59 | `UUID` | dòng 167: ép chuỗi env thành UUID, sai định dạng là nổ ngay lúc khởi động |

Chỗ đáng nói nhất là `AsyncExitStack`. Nếu không có nó, muốn mở 3 tài nguyên phải
lồng 3 tầng `async with`, và bậc thang cứ thế sâu thêm mỗi lần thêm tài nguyên mới.
`AsyncExitStack` cho phép **đăng ký dần** và nó tự đóng **theo thứ tự ngược lại**
(mở A→B→C thì đóng C→B→A) — đúng thứ tự an toàn, vì C có thể đang dùng B.

---

## Phần 2 — Dòng 62–67: import thư viện ngoài

```python
import asyncpg.exceptions      # 62 — để bắt lỗi PostgreSQL ở dòng 301, 341
import structlog               # 64 — log dạng JSON, không phải print()
from fastapi import Depends, FastAPI, Request     # 66
from fastapi.responses import JSONResponse        # 67
```

- `asyncpg.exceptions` được import **cả module** (không `from ... import X`) vì phía
  dưới cần tên đầy đủ `asyncpg.exceptions.ExclusionViolationError` làm khóa cho
  decorator — viết vậy đọc rõ đây là lỗi tầng database, không phải lỗi tầng app.
- `Depends` chỉ dùng đúng **một lần**, ở dòng 206 — nhưng đó là dòng quan trọng nhất
  file về mặt bảo mật.
- `Request` chỉ dùng làm **kiểu tham số** cho 4 exception handler ở cuối file.

---

## Phần 3 — Dòng 70–132: import 35 router + hạ tầng

```python
from clinicai.api.v1.routers.cskh import router as cskh_router
```

Đọc dòng này: *"trong file `src/clinicai/api/v1/routers/cskh.py` có một biến tên
`router`; mang nó về đây và gọi nó là `cskh_router`."*

Vì sao phải đổi tên (`as`)? Vì **cả 35 file router đều đặt tên biến là `router`**.
Không đổi tên thì cái sau ghi đè cái trước, và anh sẽ mất 34 nhóm API mà không có
một dòng lỗi nào báo.

**Hệ quả không nhìn thấy được:** `import` trong Python **chạy toàn bộ file được
import**. Nên ngay khi dòng 96 chạy, mọi `@router.get(...)` trong `cskh.py` đã thực
thi và các endpoint đã được ghi vào đối tượng `router` đó. `include_router` phía dưới
chỉ là bước **chép** danh sách đã có sẵn sang `app`.

Nhóm import còn lại (dòng 117–132) là hạ tầng:

| Dòng | Import | Vai trò |
|---|---|---|
| 118 | `close_pool, create_pool` | vòng đời connection pool tới Supabase |
| 120 | `ClinicAIBaseException` | lớp cha của mọi lỗi nghiệp vụ tự định nghĩa |
| 122 | `setup_logging` | cấu hình structlog xuất JSON |
| 124 | `init_sentry` | gửi lỗi lên Sentry |
| 126 | `AnthropicClient` | client gọi Claude |
| 128 | `make_checkpointer` | bộ nhớ hội thoại của LangGraph |
| 130 | `OrchestratorService` | tầng điều phối AI |
| 132 | `PhoWhisperTranscriber` | mô hình nhận dạng giọng nói tiếng Việt |

---

## Phần 4 — Dòng 135–140: ba lệnh chạy **ngay lúc import**

```python
setup_logging()      # 135
init_sentry()        # 137
logger = structlog.get_logger()   # 140
```

Ba dòng này **không nằm trong hàm nào** → chúng chạy ngay khi Python nạp file, tức là
**trước cả khi đối tượng `app` tồn tại** (dòng 192).

Thứ tự này là cố ý, không phải ngẫu nhiên:

1. `setup_logging()` phải chạy **đầu tiên**, nếu không những dòng log sinh ra trong
   lúc khởi động sẽ ra định dạng mặc định (text lộn xộn), lệch khỏi phần còn lại và
   Dozzle sẽ không parse được.
2. `init_sentry()` chạy **trước khi tạo app** vì Sentry cần vá (patch) các thư viện
   asyncio/FastAPI *trước khi* chúng được dùng. Init sau thì nó chỉ bắt được một phần.
3. `logger` là biến cấp module → cả 4 exception handler ở cuối file dùng chung, không
   phải tạo logger mới mỗi lần có lỗi.

---

## Phần 5 — Dòng 144–188: `lifespan` — mở và đóng tài nguyên

Đây là phần khó nhất file. Đọc chậm.

```python
@asynccontextmanager                                      # 144
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # 145
```

**Dòng 144** biến hàm bên dưới thành context manager bất đồng bộ. Quy ước: mọi thứ
**trước `yield`** = lúc bật; **sau `yield`** = lúc tắt.

**Dòng 145** — FastAPI sẽ tự truyền chính đối tượng `app` vào đây. Kiểu trả về là
`AsyncIterator[None]`: "một luồng bất đồng bộ, có `yield`, và `yield` ra `None`" —
đúng vậy, dòng 183 là `yield` trần, không kèm giá trị.

```python
app.state.db_pool = await create_pool()    # 148
```

**Dòng 148 — dòng quan trọng nhất của cả vòng đời.** `create_pool()` (xem
`core/database.py:40`) mở sẵn một **bể kết nối** tới Postgres: tối thiểu
`POOL_MIN_SIZE`, tối đa `POOL_MAX_SIZE` kết nối, và **thử lại có backoff** nếu
Supabase chưa sẵn sàng lúc container vừa bật (nếu không, container chết → Docker
restart → chết lại → vòng lặp crash).

`app.state` là **cái túi dùng chung toàn ứng dụng**. Mọi endpoint sau này lấy pool ra
bằng `Depends(get_db_pool)` — và hàm đó chỉ làm đúng một việc:
`yield request.app.state.db_pool`. Nghĩa là **35 router, hàng trăm truy vấn, dùng
chung một bể kết nối duy nhất**. Đây là lý do hệ thống chịu được nhiều người dùng
cùng lúc trên một Mac mini: không có chuyện mỗi request mở một kết nối mới tới
Supabase (kết nối tới Postgres là tài nguyên đắt, và Supabase có hạn mức).

```python
try:                                                  # 149
    async with AsyncExitStack() as stack:             # 151
        checkpointer = await stack.enter_async_context(make_checkpointer())  # 153
```

**Dòng 149** mở `try` bao trọn phần còn lại — cặp `finally` của nó ở dòng 186 đảm bảo
**dù khởi động hỏng giữa chừng, pool vẫn được đóng**.

**Dòng 153** — `enter_async_context` = "mở tài nguyên này, và **nhớ giùm** rằng lát
nữa phải đóng nó". `make_checkpointer()` là nơi LangGraph lưu trạng thái hội thoại AI,
để cuộc trò chuyện không mất khi request kết thúc.

```python
llm_client = AnthropicClient()                # 156
stack.push_async_callback(llm_client.close)   # 158
app.state.llm_client = llm_client             # 159
```

**Dòng 158** — `AnthropicClient` không phải context manager, nên không dùng
`enter_async_context` được. `push_async_callback` là cách nói: "đây không phải context
manager, nhưng khi dọn dẹp thì gọi giùm hàm `close` này". Kết quả: cùng một cơ chế
dọn dẹp cho hai loại tài nguyên khác nhau.

```python
app.state.voice_transcriber = PhoWhisperTranscriber()   # 162
```

**Dòng 162** — khởi tạo **một lần** lúc bật app. Đây là mô hình nhận dạng giọng nói;
nạp nó tốn vài giây và khá nhiều RAM. Nếu tạo mới ở mỗi request, mỗi lần bác sĩ đọc
y lệnh sẽ phải chờ nạp lại mô hình.

```python
default_location_id_env = os.environ.get("DEFAULT_LOCATION_ID")   # 165
scheduling_location_id: UUID | None = (                            # 166–168
    UUID(default_location_id_env) if default_location_id_env else None
)
```

**Dòng 165–168** — `os.environ.get` (không phải `os.environ[...]`) → thiếu biến thì
được `None` chứ không nổ. Nhưng **nếu có mà sai định dạng UUID thì `UUID(...)` nổ ngay
lúc khởi động**, chứ không im lặng để rồi 3 tuần sau mới lòi ra ở một truy vấn nào đó.
Đây là nguyên tắc *fail fast*: sai cấu hình thì phải chết lúc bật, không phải lúc chạy.

```python
app.state.orchestrator_service = OrchestratorService(   # 171–178
    checkpointer=checkpointer,
    llm_client=llm_client,
    scheduling_pool=app.state.db_pool,
    scheduling_location_id=scheduling_location_id,
    lab_triage_pool=app.state.db_pool,
    task_manager_pool=app.state.db_pool,
)
```

**Dòng 171–178** — ba tham số `*_pool` đều nhận **cùng một** `app.state.db_pool`. Đây
là *dependency injection*: OrchestratorService không tự đi tạo kết nối, mà nhận từ bên
ngoài. Nhờ vậy khi viết test có thể truyền pool giả vào. Việc chúng là cùng một pool
hôm nay là chi tiết triển khai — ngày nào tách DB tra cứu xét nghiệm ra riêng, chỉ
sửa đúng dòng này.

```python
logger.info("app_startup_complete")   # 181
yield                                  # 183
logger.info("app_shutdown_starting")   # 185
```

**Dòng 183 — `yield` là ranh giới.** Trước nó là khởi động. Tại đúng khoảnh khắc này
FastAPI mới bắt đầu nhận request, và hàm `lifespan` **đứng yên ở đây suốt nhiều ngày,
nhiều tuần** — bao lâu app còn chạy. Khi anh `docker compose down`, Python mới chạy
tiếp dòng 185.

Hai dòng log 181/185 không phải trang trí: chúng là mốc anh grep trong Dozzle để biết
container bật/tắt lúc nào, và bật lên có sạch không.

```python
finally:                                    # 186
    await close_pool(app.state.db_pool)     # 188
```

**Dòng 186–188** — `finally` chạy **trong mọi trường hợp**: tắt bình thường, hay
`make_checkpointer()` ném lỗi ở dòng 153. Không có nó, một lỗi khởi động sẽ để lại
đám kết nối treo phía Supabase.

Thứ tự dọn dẹp thực tế khi tắt: `AsyncExitStack` đóng ngược (llm_client.close →
checkpointer), **rồi mới** tới `close_pool`. Đúng thứ tự — vì llm_client và
checkpointer có thể còn cần database trong lúc đóng.

---

## Phần 6 — Dòng 192–197: tạo ứng dụng

```python
app = FastAPI(
    title="ClinicAI",                                       # 193
    description="AI-powered clinic management for Dr4women",# 194
    version="0.1.0",                                        # 195
    lifespan=lifespan,                                      # 196
)
```

- `title`, `description`, `version` **không ảnh hưởng gì tới lúc chạy**. Chúng chỉ đi
  vào file `/openapi.json` và hiện lên đầu trang `/docs` (Swagger UI).
- `lifespan=lifespan` — truyền **hàm**, không gọi hàm (không có dấu ngoặc). FastAPI
  giữ tham chiếu và sẽ tự gọi vào đúng lúc.

Biến `app` này chính là thứ Uvicorn tìm khi container chạy `uvicorn clinicai.main:app`
— chuỗi đó nghĩa là "trong module `clinicai.main`, lấy biến tên `app`".

---

## Phần 7 — Dòng 200–203: bốn lớp middleware, và bẫy thứ tự

```python
app.add_middleware(DbErrorMiddleware)        # 200
app.middleware("http")(api_key_middleware)   # 201
app.add_middleware(TimingMiddleware)         # 202
app.add_middleware(RequestIdMiddleware)      # 203
```

**Đây là chỗ 90% người đọc hiểu ngược.** Starlette (nền của FastAPI) **chèn mỗi
middleware mới vào đầu danh sách**. Nên **cái thêm sau cùng lại nằm ngoài cùng**.

Dòng 201 nhìn khác ba dòng kia nhưng bản chất y hệt: `app.middleware("http")` là
đường tắt cú pháp cho `add_middleware(BaseHTTPMiddleware, dispatch=api_key_middleware)`
— dùng khi middleware là **hàm** thay vì **class**.

Thứ tự thực tế một request đi qua:

```
        request vào
             │
 ┌───────────▼──────────────────────────────────────┐
 │ ServerErrorMiddleware   (Starlette tự thêm)      │ ← handler Exception (dòng 382)
 │ ┌────────────────────────────────────────────┐   │
 │ │ RequestIdMiddleware      (dòng 203)        │   │  gắn X-Request-ID
 │ │ ┌────────────────────────────────────────┐ │   │
 │ │ │ TimingMiddleware       (dòng 202)      │ │   │  đo thời gian
 │ │ │ ┌────────────────────────────────────┐ │ │   │
 │ │ │ │ api_key_middleware   (dòng 201)    │ │ │   │  chặn nếu sai X-API-Key
 │ │ │ │ ┌────────────────────────────────┐ │ │ │   │
 │ │ │ │ │ DbErrorMiddleware  (dòng 200)  │ │ │ │   │  lỗi kết nối DB → 503
 │ │ │ │ │ ┌────────────────────────────┐ │ │ │ │   │
 │ │ │ │ │ │ ExceptionMiddleware        │ │ │ │ │   │ ← handler 409 (dòng 301/341)
 │ │ │ │ │ │   → _GUARDED → endpoint    │ │ │ │ │   │   và ClinicAIBase (dòng 362)
```

Vì sao thứ tự này đúng:

- **`RequestIdMiddleware` ngoài cùng** (dòng 203) — nó phải gán `request_id` *trước*
  mọi thứ khác, để dù lỗi xảy ra ở lớp nào thì log của lớp đó cũng đã có mã truy vết.
  Nó tái dùng `X-Request-ID` nếu Caddy/Cloudflare đã gắn sẵn — nhờ vậy anh lần được
  một request xuyên suốt từ ingress xuống DB bằng đúng một mã.
- **`TimingMiddleware` ngay bên trong** — nó đo cả thời gian của `api_key_middleware`
  và của DB. Nếu đặt trong cùng, nó sẽ báo số đẹp hơn thực tế người dùng cảm nhận.
- **`api_key_middleware`** (`api/auth.py:84`) — chặn ở đây, trước khi chạm DB. Nó
  **miễn trừ** `/health`, `/health/db`, `/docs`, `/openapi.json`, `/redoc`
  (`auth.py:50`). Và nếu `BACKEND_API_KEY` chưa đặt: ở dev/local/test thì cho qua kèm
  log cảnh báo; ở **staging/prod thì trả 503 SERVER_MISCONFIGURED** — thà chết rõ ràng
  còn hơn chạy không có khóa mà không ai biết.
- **`DbErrorMiddleware` trong cùng** — chỉ bắt lỗi **tầng kết nối** (mạng đứt, pool
  cạn), đổi thành **503 + `Retry-After: 5`**. Lý do sống còn: nếu để nó thành 500,
  healthcheck của Docker thấy 500 → restart container → vòng lặp crash mỗi lần
  Supabase chớp mạng. Trả 503 thì container sống, và tự lành khi mạng trở lại.

**Một cái bẫy thật, ghi lại để sau này khỏi mất buổi chiều đi tìm:** `ServerErrorMiddleware`
nằm **ngoài** `RequestIdMiddleware`. Mà `RequestIdMiddleware` chỉ gắn header ở dòng
`middleware.py:111`, tức là **chỉ khi `call_next` trả về bình thường**. Nên với lỗi 500
chưa bắt được (do handler dòng 382 xử lý), **response trả về sẽ KHÔNG có header
`X-Request-ID`** — đúng lúc anh cần mã đó nhất. Mã vẫn nằm trong log server, chỉ là
client không nhận được.

---

## Phần 8 — Dòng 206: `_GUARDED` — dòng ngắn nhất, quan trọng nhất

```python
_GUARDED = [Depends(runaway_guard)]
```

Mổ xẻ:

- `Depends(runaway_guard)` — nói với FastAPI: "trước khi chạy endpoint, hãy gọi hàm
  `runaway_guard`". Kết quả trả về **bị bỏ đi** (hàm này trả `None`). Người ta dùng
  kiểu này khi chỉ cần **tác dụng phụ**: kiểm tra và chặn.
- Là một **list** vì tham số `dependencies=` của `include_router` nhận list — có thể
  xếp nhiều cửa gác.
- Gạch dưới đầu tên `_GUARDED` = quy ước "nội bộ file này, đừng import từ nơi khác".
- Viết một lần rồi dùng lại 30 lần: sửa chính sách gác cửa chỉ sửa **một** dòng, không
  phải sửa 30 dòng và bỏ sót 3 cái.

**Và đây là điều tên biến không nói ra:** `runaway_guard` (`api/runaway_guard.py:211`)
được khai báo là

```python
async def runaway_guard(
    request: Request,
    identity: StaffIdentity = Depends(get_current_identity),
) -> None:
```

Nó **phụ thuộc vào `get_current_identity`**. Mà `get_current_identity` bắt buộc phải
có `Authorization: Bearer ...` hợp lệ — không có thì ném **401** ngay
(`identity.py:183`), rồi giải mã JWT Supabase, tra ra nhân viên và phòng khám.

Nghĩa là: **`_GUARDED` không chỉ là bộ đếm chống lặp — nó chính là cửa xác thực.**
Route nào có `_GUARDED` thì bắt buộc phải đăng nhập; route nào không có thì chỉ cần
`X-API-Key` là gọi được. Danh sách route **không** có `_GUARDED` ở phần 9 vì thế cần
được đọc kỹ.

Về phần "chống lặp": ngưỡng là **120 request/phút cho mỗi nhân viên**
(`runaway_guard.py:74`). Cố tình đặt **cao hơn nhiều** so với thao tác tay của con
người. Triết lý ghi rõ trong docstring đầu file đó: một người thật không thể bấm 120
lần/phút, nên chạm ngưỡng nghĩa là **có bug** — thường là `useEffect` tự kích lại
chính nó, hoặc vòng retry không backoff. Đặt ngưỡng chặt sẽ **giấu** bug đi (server
lặng lẽ từ chối, màn hình chạy nửa vời, không ai điều tra, phòng khám chỉ thấy "hơi
chậm"). Nên: lần chạm đầu tiên **ghi log WARNING kèm route và mã nhân viên**, quá
ngưỡng mới trả 429 — cảnh báo là việc thứ nhất, từ chối là việc thứ hai.

Lưu ý thứ tự: dependency của router được giải **trước** khi FastAPI kiểm tra body.
Nên khi thiếu token *và* body sai, anh nhận **401**, không phải 422.

---

## Phần 9 — Dòng 209–297: `include_router` và toàn bộ bản đồ API

### 9.1 Mổ xẻ đúng dòng anh hỏi

```python
app.include_router(cskh_router, prefix="/api/v1", tags=["cskh"], dependencies=_GUARDED)
```

| Thành phần | Nghĩa | Ảnh hưởng lúc chạy? |
|---|---|---|
| `app.include_router(...)` | **Chép** mọi route đã khai trong router đó vào bảng định tuyến của `app` | Có |
| `cskh_router` | đối tượng `APIRouter` import ở dòng 96, gốc là biến `router` trong `routers/cskh.py` | Có |
| `prefix="/api/v1"` | ghép vào **đầu** mọi đường dẫn con. Phải bắt đầu bằng `/`, **không** được kết thúc bằng `/` (FastAPI assert ngay lúc bật) | Có |
| `tags=["cskh"]` | **chỉ để gom nhóm trong trang `/docs`**. Không kiểm tra gì, không chặn gì | **Không** |
| `dependencies=_GUARDED` | gắn cửa gác vào **từng** route của router này | Có |

Đây là **chép**, không phải liên kết sống: route nào thêm vào `cskh_router` *sau* dòng
274 sẽ không xuất hiện. Trong dự án này không xảy ra, vì `import` ở đầu file đã chạy
xong toàn bộ file router rồi.

Cụ thể `cskh.py` có `router = APIRouter()` (không prefix riêng) và 3 endpoint. Ghép lại:

| Method | URL cuối cùng | Ai gọi hôm nay |
|---|---|---|
| GET | `/api/v1/cskh/recalls` | *(chưa màn hình nào gọi)* |
| POST | `/api/v1/cskh/actions` | `app/api/cskh-action/route.ts` |
| POST | `/api/v1/cskh/followup-calls` | `app/api/cskh-followup/route.ts` |

### 9.2 Quy tắc ghép đường dẫn

```
URL cuối = prefix lúc include  +  prefix riêng của APIRouter (nếu có)  +  path của decorator
```

Đa số router khai `APIRouter()` trần → chỉ có 2 mảnh. Nhưng **6 router có prefix
riêng**, nên bị ghép 3 mảnh — chỗ này hay đọc nhầm:

| Router | Khai báo trong file | Path decorator | URL thật |
|---|---|---|---|
| `brief` | `APIRouter(prefix="/brief")` | `/{clinic_patient_id}` | `/api/v1/brief/{clinic_patient_id}` |
| `lab` | `APIRouter(prefix="/lab")` | `/orders` | `/api/v1/lab/orders` |
| `tools` | `APIRouter(prefix="/tools")` | `/task/create` | `/api/v1/tools/task/create` |
| `orchestrator` | `APIRouter(prefix="/orchestrator")` | `/chat` | `/api/v1/orchestrator/chat` |
| `voice` | `APIRouter(prefix="/voice")` | `/transcribe` | `/api/v1/voice/transcribe` |
| `catalog` | `APIRouter(tags=["catalog"])` | `/catalog/wards` | `/api/v1/catalog/wards` |

### 9.3 Bảng đầy đủ — 35 router, ~110 endpoint

Cột **Gác** : ✅ = có `_GUARDED` (bắt buộc đăng nhập + đếm ngưỡng) · ⬜ = không.

#### Không có prefix `/api/v1` — dòng 209

| Method | URL | Gác | Ghi chú |
|---|---|---|---|
| GET | `/health` | ⬜ | Docker healthcheck + Uptime Kuma. **Miễn cả X-API-Key** |
| GET | `/health/db` | ⬜ | ping thật xuống Postgres |

Đây là router **duy nhất** không có prefix và không có gác — cố ý: healthcheck phải
gọi được khi mọi thứ khác đang hỏng.

#### Danh tính & hàng đợi — dòng 210–221

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| GET | `/api/v1/me` | ✅ | *(chưa dùng)* |
| GET | `/api/v1/queue` | ✅ | `queue/page.tsx`, `QueueBoard.tsx` |
| GET | `/api/v1/console/overview` | ✅ | `app/console/page.tsx` |
| POST | `/api/v1/console/feedback` | ✅ | `app/api/console/feedback/route.ts` |
| GET | `/api/v1/patients/{patient_id}/links` | ✅ | consent router |
| GET | `/api/v1/patients/{patient_id}/shared-form` | ✅ | consent router |
| POST | `/api/v1/patients/links` | ✅ | |
| POST | `/api/v1/patients/consents` | ✅ | |
| POST | `/api/v1/patients/consents/{consent_id}/revoke` | ✅ | |

#### Bệnh nhân & nhân sự — dòng 222–228

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| POST | `/api/v1/patients` | ✅ | `app/api/patients/route.ts` |
| GET | `/api/v1/patients` | ✅ | |
| GET | `/api/v1/patients/check-phone` | ✅ | |
| GET | `/api/v1/patients/check-duplicate` | ✅ | `app/api/patients/check-duplicate/route.ts` (MPI dedup) |
| GET | `/api/v1/patients/{id:uuid}` | ✅ | |
| PATCH | `/api/v1/patients/{id:uuid}` | ✅ | |
| POST GET PATCH DELETE | `/api/v1/staff`, `/api/v1/staff/{id}` | ✅ | *(chưa dùng)* |
| POST | `/api/v1/work-sessions` | ✅ | *(chưa dùng)* |
| GET | `/api/v1/work-sessions/{id}` | ✅ | |
| POST | `/api/v1/work-sessions/{id}/staff` | ✅ | |
| GET | `/api/v1/appointments/{id:uuid}` | ✅ | |

`{id:uuid}` là **path converter**: sai định dạng UUID thì Starlette **không khớp
route** → 404, endpoint không hề chạy. Rẻ hơn nhiều so với để nó xuống tận DB.

#### Thu ngân, báo cáo, nhật ký — dòng 229–246

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| POST | `/api/v1/payments` | ✅ | `app/api/payment/route.ts` |
| DELETE | `/api/v1/payments` | ✅ | (huỷ thanh toán) |
| GET | `/api/v1/cashier/board` | ✅ | `tasks/page.tsx` |
| GET | `/api/v1/reports/booking-channels` | ✅ | `reports/page.tsx` |
| GET | `/api/v1/audit/events` | ✅ | `audit-log/page.tsx` |
| GET | `/api/v1/clinic-config/overview` | ✅ | `settings/clinic-config/page.tsx` |
| GET | `/api/v1/clinic-config/staff` | ✅ | |
| GET | `/api/v1/clinic-config/services` | ✅ | |
| PUT | `/api/v1/clinic-config/service-form` | ✅ | gán biểu mẫu cho dịch vụ |
| PUT | `/api/v1/clinic-config/room-floor` | ✅ | |
| PUT | `/api/v1/clinic-config/room-nodes` | ✅ | |
| PUT | `/api/v1/clinic-config/staff-nodes` | ✅ | |

#### Luồng khám: episode & work-item — dòng 247–252

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| PATCH | `/api/v1/episodes/{episode_id}` | ✅ | `app/api/episodes/route.ts` |
| GET | `/api/v1/work-items` | ✅ | `lib/worklist-server.ts` |
| POST | `/api/v1/work-items/{id}/commands/start` | ✅ | `app/api/work-items/[id]/commands/[command]/route.ts` |
| POST | `/api/v1/work-items/{id}/commands/complete` | ✅ | ↑ cùng route |
| POST | `/api/v1/work-items/{id}/commands/skip` | ✅ | ↑ |
| POST | `/api/v1/work-items/{id}/commands/cancel` | ✅ | ↑ |
| GET | `/api/v1/work-items/{id}/blockers` | ✅ | `app/api/work-items/[id]/blockers/route.ts` |
| GET | `/api/v1/visits/{visit_id}/work-items` | ✅ | |
| GET | `/api/v1/service-catalogue` | ✅ | |
| POST | `/api/v1/visits/{visit_id}/service-orders` | ✅ | `app/api/visits/[id]/service-orders/route.ts` |
| POST | `/api/v1/visits/{visit_id}/service-orders/duplicates` | ✅ | |
| GET | `/api/v1/visits/{visit_id}/charges` | ✅ | `app/api/visits/[id]/charges/route.ts` |

#### AI: tools / orchestrator / brief — dòng 253–255

| Method | URL | Gác | Ghi chú |
|---|---|---|---|
| POST | `/api/v1/tools/patient/get-summary` | ✅ | 10 endpoint này là **tool** cho Claude gọi, |
| POST | `/api/v1/tools/scheduling/find-oncall` | ✅ | không phải cho màn hình. |
| POST | `/api/v1/tools/event-log/append` | ✅ | |
| POST | `/api/v1/tools/kb/read-policy` | ✅ | |
| POST | `/api/v1/tools/communication/send-zalo` | ✅ | |
| POST | `/api/v1/tools/lab/classify` | ✅ | |
| POST | `/api/v1/tools/task/create` · `/task/query` · `/task/update-status` | ✅ | |
| GET | `/api/v1/tools/task/check-sla/{task_id}` | ✅ | |
| POST | `/api/v1/orchestrator/chat` | ✅ | cửa vào LangGraph |
| POST | `/api/v1/brief/{clinic_patient_id}` | ✅ | `app/api/brief/[id]/route.ts` → `PreVisitBrief.tsx` |

Ba dòng 253–255 **không truyền `tags=`** — vì `tools`/`orchestrator`/`brief` đã tự khai
`tags` trong `APIRouter(...)` của chúng.

#### ⚠️ Catalog — dòng 256, **không có gác**

```python
app.include_router(catalog_router, prefix="/api/v1")
```

| Method | URL | Gác | Thực tế |
|---|---|---|---|
| GET | `/api/v1/catalog/wards` | ⬜ | **hoàn toàn không cần đăng nhập** — chỉ cần X-API-Key |
| GET | `/api/v1/catalog/service-types` | ⬜ | nhưng tự khai `Depends(get_current_identity)` trong hàm |
| GET | `/api/v1/catalog/booking-channels` | ⬜ | ↑ như trên |

Đây là dòng **duy nhất** vừa thiếu `tags` vừa thiếu `dependencies`. Hai endpoint sau
tự lo phần danh tính ở cấp hàm, nên vẫn an toàn; riêng `/catalog/wards` (danh mục
phường/xã hành chính) là dữ liệu công khai nên không cần. Cái **mất** là: ba endpoint
này không được đếm vào ngưỡng chống lặp — một vòng lặp hỏng gọi `/catalog/wards` sẽ
không kích cảnh báo nào.

#### Ops, xét nghiệm, siêu âm — dòng 257–261

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| GET | `/api/v1/ops/status` | ✅ | `app/api/ops/summary/route.ts` |
| GET | `/api/v1/ops/telemetry` | ✅ | ↑ (nơi cảnh báo runaway hiện lên) |
| POST | `/api/v1/lab/orders` | ✅ | `app/api/lab-result/route.ts` |
| PATCH | `/api/v1/lab/results/{lab_result_id}` | ✅ | |
| POST | `/api/v1/lab/results/{id}/review` | ✅ | `app/api/lab-result/[id]/review/route.ts` |
| GET | `/api/v1/lab/results/{id}/release` | ✅ | |
| POST | `/api/v1/lab/triage/{lab_result_id}` | ✅ | `app/api/lab-result/[id]/triage/route.ts` (AI phân loại) |
| POST | `/api/v1/ultrasound/measurements` | ✅ | `app/api/ultrasound/route.ts` |
| GET | `/api/v1/ultrasound/queue` · `/rooms` · `/records` · `/image` | ✅ | `sieu-am/page.tsx` |
| POST | `/api/v1/ultrasound/draft` | ✅ | |
| POST | `/api/v1/ultrasound/{ultrasound_id}/image` | ✅ | |

#### Hồ sơ lâm sàng & ký — dòng 262–273, 284–289

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| GET PUT | `/api/v1/clinical-forms` | ✅ | `app/api/clinical-form/route.ts` |
| POST | `/api/v1/clinical-forms/andrology-review` | ✅ | `app/api/clinical-form/andrology-review/route.ts` |
| POST | `/api/v1/clinical-records` | ✅ | `app/api/clinical-record/route.ts` |
| GET | `/api/v1/clinical/{visit_id:uuid}/status` | ✅ | `app/api/clinical/[visit_id]/[action]/route.ts` |
| POST | `/api/v1/clinical/{visit_id:uuid}/sign` | ✅ | ký bệnh án |
| POST | `/api/v1/clinical/{visit_id:uuid}/release` | ✅ | trả kết quả |
| POST | `/api/v1/clinical/{visit_id:uuid}/amend` | ✅ | sửa sau khi ký |
| POST | `/api/v1/clinical/ultrasound/{ultrasound_id:uuid}/sign` | ✅ | |
| POST PATCH | `/api/v1/service-log`, `/service-log/{row_id}` | ✅ | `app/api/service-log/route.ts` |
| POST PATCH DELETE | `/api/v1/sono/queue`, `/sono/queue/{row_id}` | ✅ | `app/api/sono/route.ts` |

#### Đặt lịch — dòng 275–277

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| POST | `/api/v1/appointments/bookings` | ✅ | `app/api/appointments/route.ts` |
| GET | `/api/v1/appointments/quote` | ✅ | `app/api/appointments/quote/route.ts` (báo giá + slot) |
| GET | `/api/v1/appointments/week` | ✅ | `home/page.tsx` |
| GET | `/api/v1/appointments/doctor-board` | ✅ | `tasks/page.tsx` |
| GET | `/api/v1/appointments/policy` | ✅ | `lib/booking-policy.ts` (6 nơi gọi) |
| PATCH | `/api/v1/appointments/{appointment_id}` | ✅ | |
| POST GET DELETE | `/api/v1/appointments/slot-hold` | ✅ | `BookingHub.tsx` giữ chỗ tạm |

#### Cấu hình vận hành — dòng 278–280

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| POST PATCH DELETE | `/api/v1/roster/shifts`, `/roster/shifts/{id}` | ✅ | `app/api/roster/route.ts` |
| POST PATCH DELETE | `/api/v1/service-prices`, `/service-prices/{id}` | ✅ | `app/api/service-price/route.ts` |
| PATCH | `/api/v1/booking-policy` | ✅ | `app/api/booking-policy/route.ts` |
| POST GET | `/api/v1/booking-rules` | ✅ | `app/api/booking-rules/route.ts` |
| DELETE | `/api/v1/booking-overrides/doctor/{override_id}` | ✅ | `app/api/booking-overrides/doctor/[id]/route.ts` |
| DELETE | `/api/v1/booking-overrides/slot/{override_id}` | ✅ | `app/api/booking-overrides/slot/[id]/route.ts` |
| GET PUT | `/api/v1/feature-mode` | ✅ | ⚠️ **xem mục 11.1 — frontend đang gọi sai đường dẫn** |

#### Điều phối & lễ tân — dòng 281–283

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| GET | `/api/v1/dispatch/overview` · `/alerts` · `/routes` · `/history` · `/tv` | ✅ | `app/api/dispatch-read/route.ts` |
| POST | `/api/v1/dispatch/move` · `/transfer-room` · `/route` | ✅ | `app/api/dispatch/[action]/route.ts` |
| PUT | `/api/v1/dispatch/threshold` | ✅ | |
| GET | `/api/v1/reception/checkout` | ✅ | `reception/checkout/page.tsx` |
| GET | `/api/v1/reception/checkout/{visit_id:uuid}` | ✅ | |
| POST | `/api/v1/reception/checkout` | ✅ | `app/api/reception/checkout/route.ts` |

#### Tiến độ & giọng nói — dòng 290–296

| Method | URL | Gác | Ai gọi |
|---|---|---|---|
| GET | `/api/v1/visits/progress` | ✅ | `truong-ca/load.ts` |
| GET | `/api/v1/visits/{visit_id}/workflow` | ✅ | |
| GET | `/api/v1/visits/active` | ✅ | |
| POST | `/api/v1/voice/transcribe` | ✅ | *(chưa màn hình nào gọi)* |

#### ⚠️ Display — dòng 297, **không có gác**

```python
app.include_router(display_router, prefix="/api/v1", tags=["display"])
```

| Method | URL | Gác | Vì sao |
|---|---|---|---|
| GET | `/api/v1/display/config?clinic_id=...` | ⬜ | Màn hình TV ở sảnh **không có ai đăng nhập**. Nếu bắt buộc token thì TV không chạy được. Nó nhận `clinic_id` qua query param thay vì suy từ danh tính |

Đây là ngoại lệ có chủ đích, nhưng phải ghi nhớ: **bất cứ ai có `X-API-Key` đều đọc
được cấu hình hiển thị của bất kỳ `clinic_id` nào**. Chấp nhận được vì đó là dữ liệu
sẽ chiếu lên tường; không được phép thêm gì nhạy cảm vào endpoint này.

### 9.4 Thứ tự đăng ký có quan trọng không?

Có, nhưng chỉ khi hai route **trùng khuôn**. Starlette duyệt danh sách **từ trên
xuống, lấy cái khớp đầu tiên**. Trong file này có 3 router cùng khai dưới `/visits/...`
(`work_items` dòng 250, `visit_progress` dòng 290) và 2 router cùng khai
`/patients/...` (`consent` dòng 219, `patients` dòng 222) — hôm nay không xung đột vì
các path con khác nhau. Nhưng nếu ngày nào đó thêm `/visits/{id}` chung chung vào
`work_items`, nó sẽ **nuốt** `/visits/progress` của router đăng ký sau. Quy tắc an
toàn: **route cụ thể phải đứng trước route có tham số.**

---

## Phần 10 — Dòng 301–397: bốn lưới bắt lỗi

FastAPI cho phép đăng ký handler theo **loại exception**. Khi lỗi bay lên, nó tìm
handler khớp nhất. Bốn cái ở đây xếp từ **hẹp → rộng**.

### 10.1 Dòng 301–337 — Xung đột khung giờ → 409

```python
@app.exception_handler(asyncpg.exceptions.ExclusionViolationError)   # 301
```

`ExclusionViolationError` là lỗi Postgres ném ra khi vi phạm **EXCLUSION constraint** —
loại ràng buộc chống **chồng lấn khoảng**. Ví dụ: bác sĩ Thành đã có lịch 9:00–9:30,
ai đó cố đặt tiếp 9:15–9:45.

Điểm hay của thiết kế này: **luật chống trùng lịch nằm trong DB, không nằm trong
Python.** Hai lễ tân bấm cùng lúc, Python có kiểm tra trước cũng vô nghĩa (race
condition) — chỉ Postgres mới phân xử được ai thắng. Python chỉ lo **dịch lỗi**.

```python
constraint = getattr(exc, "constraint_name", None) or ""    # 307
```

**Dòng 307** — `getattr(..., None)` thay vì `exc.constraint_name` vì tuỳ phiên bản
asyncpg thuộc tính này có thể vắng. `or ""` biến `None` thành chuỗi rỗng để dòng dưới
`.get()` không nổ.

**Dòng 309–319** — từ điển dịch tên constraint kỹ thuật sang câu tiếng Việt lễ tân
đọc hiểu:

| Tên constraint trong DB | Câu hiện lên màn hình |
|---|---|
| `appointment_no_doctor_overlap` | "Lịch hẹn xung đột khung giờ với appointment khác" |
| `slot_override_no_overlap` | "Đã có một điều chỉnh khác phủ khung giờ này — sửa hoặc xoá nó trước." |
| `doctor_override_no_overlap` | "Đã có một luật khác phủ khung giờ này — sửa hoặc xoá nó trước." |

**Dòng 321–326** — constraint lạ (mới thêm mà quên khai ở đây) thì rơi vào câu mặc
định, **có kèm tên constraint trong ngoặc**. Không đẹp, nhưng người dùng đọc xong gọi
điện cho anh và anh biết ngay phải sửa ở đâu. Im lặng mới là tệ.

**Dòng 334–337** — trả **409 CONFLICT_ERROR**. 409 là đúng nghĩa: "yêu cầu hợp lệ,
nhưng đụng trạng thái hiện tại". Không phải 400 (sai cú pháp), không phải 500 (lỗi
server).

### 10.2 Dòng 341–358 — Trùng khoá duy nhất → 409

Bắt `UniqueViolationError` (vi phạm UNIQUE constraint). Khác cái trên ở chỗ **không**
đọc tên constraint và **không** map câu:

```python
"message": "Resource already exists"    # 356
```

Cố ý. Tên UNIQUE constraint thường lộ cấu trúc bảng và đôi khi cả dữ liệu (ví dụ
`staff_phone_key` → tiết lộ hệ thống định danh nhân viên bằng số điện thoại). Với lỗi
chồng lấn khung giờ thì thông tin chi tiết giúp người dùng xử lý được; với trùng khoá
thì không giúp gì thêm, nên giữ mơ hồ.

### 10.3 Dòng 362–378 — Lỗi nghiệp vụ của chính mình

```python
@app.exception_handler(ClinicAIBaseException)   # 362
```

Bắt **cả họ** exception tự định nghĩa. Trong `core/exceptions.py` có 4 lớp con:
`ResourceNotFoundError`, `ValidationError`, `SafetyGateError`, `ExternalServiceError`.
Nhờ đăng ký lớp **cha**, thêm bao nhiêu lớp con nữa cũng tự động được xử lý — không
phải sửa `main.py`.

```python
status_code=exc.status_code,                                  # 376
content={"error": exc.error_code, "message": exc.message},    # 377
```

Mỗi exception **tự mang mã HTTP và mã lỗi của mình** (404/400/403/502...). Handler này
chỉ đóng gói lại. Đây là lý do service viết được `raise ResourceNotFoundError("Không
tìm thấy bệnh nhân")` mà không cần biết gì về HTTP — đúng nguyên tắc "logic nghiệp vụ
là Python thuần, testable" trong `CLAUDE.md`.

Chú ý `logger.warning` (dòng 368) chứ không phải `error`: đây là lỗi **đã lường
trước**, không phải sự cố. Bệnh nhân không tồn tại là chuyện thường ngày, không đáng
đánh thức ai.

### 10.4 Dòng 382–397 — Lưới cuối cùng

```python
@app.exception_handler(Exception)   # 382
```

Bắt **mọi thứ còn lại**. Ba khác biệt quan trọng so với ba handler trên:

1. **`logger.exception`** (dòng 386) chứ không phải `warning` — hàm này ghi kèm **toàn
   bộ stack trace**. Lỗi không lường trước thì cần biết chính xác dòng nào.
2. **Không trả chi tiết cho client** (dòng 391–397): chỉ `"An internal server error
   occurred."`. Chi tiết kỹ thuật ở lại trong log và Sentry. Trả stack trace ra ngoài
   là lỗ hổng bảo mật kinh điển.
3. Như đã nói ở Phần 6, handler này chạy tại `ServerErrorMiddleware` — **ngoài cùng**,
   nên response 500 của nó không có header `X-Request-ID`.

### 10.5 Ai thắng khi nhiều lưới cùng khớp?

Thứ tự phân xử thực tế:

```
Lỗi trong endpoint
   │
   ├─ Là ExclusionViolation / UniqueViolation / ClinicAIBaseException?
   │     → ExceptionMiddleware (trong cùng) xử lý → 409 / mã riêng
   │
   ├─ Là lỗi KẾT NỐI DB (PostgresConnectionError, InterfaceError, OSError)?
   │     → bay tiếp ra ngoài → DbErrorMiddleware bắt → 503 + Retry-After
   │
   └─ Còn lại
         → bay ra tận ServerErrorMiddleware → handler dòng 382 → 500
```

Chi tiết đáng giá: **503 thắng 500**, vì `DbErrorMiddleware` nằm **trong** hơn
`ServerErrorMiddleware`, nên nó chạm lỗi trước. Đó chính xác là điều mình muốn —
Supabase chớp mạng thì trả 503 (khách gọi lại được), chứ không phải 500 (làm Docker
restart container thành vòng lặp).

---

## Phần 11 — Những gì đọc kỹ mới thấy

### 11.1 ⚠️ Một API gọi hụt: `feature-mode`

Backend đăng ký (`routers/config.py:375`, `router = APIRouter()` không prefix riêng,
include với `prefix="/api/v1"`):

```
GET  /api/v1/feature-mode
PUT  /api/v1/feature-mode
```

Frontend lại gọi (`app/api/config/feature-mode/route.ts:6,16`):

```
GET  /api/v1/config/feature-mode      ← thừa chữ "config"
PUT  /api/v1/config/feature-mode
```

Hai đường dẫn không khớp → backend trả **404**. Chữ `config` trong `tags=["config"]`
ở dòng 279 **không tạo ra đoạn đường dẫn nào** (tags chỉ để gom nhóm trong `/docs`) —
nhiều khả năng đây chính là chỗ hiểu nhầm khi viết frontend.

Lỗi này **đã có từ trước** (kiểm tra `git show HEAD` — không phải do đợt thêm chú thích
vừa rồi tạo ra). Sửa được bằng **một dòng**, chọn một trong hai:

- đổi decorator thành `@router.get("/config/feature-mode")` + `@router.put(...)`, hoặc
- đổi 2 chỗ trong `app/api/config/feature-mode/route.ts` thành `/api/v1/feature-mode`.

Không có test nào cho đường dẫn này, nên nó lọt qua CI.

### 11.2 Những API đã xây nhưng chưa màn hình nào gọi

Rà toàn bộ `app/`, `lib/`, `components/` của dashboard, các endpoint sau **không có
người gọi**:

| Endpoint | Nhiều khả năng vì |
|---|---|
| `GET /api/v1/me` | frontend đang tự suy vai trò từ `lib/roles.ts` |
| `GET /api/v1/cskh/recalls` | màn CSKH mới chỉ ghi, chưa đọc |
| `/api/v1/staff/*` (5 endpoint CRUD) | quản lý nhân sự vẫn làm tay |
| `/api/v1/work-sessions/*` | (lưu ý: `/work-sessions` trong dashboard là **trang Next**, không phải API này) |
| `/api/v1/catalog/*` | frontend còn đọc thẳng Supabase |
| `/api/v1/voice/transcribe` | tính năng giọng nói chưa lên UI |
| `/api/v1/orchestrator/chat`, `/api/v1/tools/*` | dành cho AI gọi, không phải màn hình |
| `/api/v1/display/config` | màn TV có thể đang đọc đường khác |

Đây không phải bug — đa số là phần backend của Phase 4 đã xong trước, frontend chưa
chuyển sang. Nhưng đáng ghi lại để khỏi tưởng nhầm là code chết mà xoá.

### 11.3 Ba mức bảo vệ, phân biệt cho rõ

| Mức | Cơ chế | Route nào không có |
|---|---|---|
| 1. Máy gọi máy | `X-API-Key` (middleware dòng 201) | `/health`, `/health/db`, `/docs`, `/openapi.json`, `/redoc` |
| 2. Người là ai | `_GUARDED` → `get_current_identity` (JWT Supabase) | `/health/*`, `/api/v1/catalog/*`, `/api/v1/display/config` |
| 3. Người được làm gì | `require_role(...)` khai **trong từng router**, không có trong `main.py` | tuỳ endpoint |

`main.py` chỉ dựng mức 1 và 2. Mức 3 (chỉ MANAGEMENT được đổi `feature-mode`, chỉ bác
sĩ được ký bệnh án) nằm rải trong từng router bằng `Depends(require_role(...))` —
xem `api/identity.py:342` (`RoleGuard`).

### 11.4 Cách sờ tận tay

Danh sách sinh ra từ chính `main.py`, luôn đúng với code hiện tại:

```bash
curl -s localhost:8000/openapi.json | python3 -c "import json,sys; [print(f'{m.upper():7} {p}') for p,v in sorted(json.load(sys.stdin)['paths'].items()) for m in v]"
```

Hoặc mở trình duyệt vào `http://localhost:8000/docs` — đó là trang Swagger, và các
nhóm anh thấy trên đó chính là `tags=[...]` ở dòng 209–297.

---

## Phụ lục — bốn khái niệm nền

*(Phần này trước đây nằm ở đầu `main.py` dưới dạng chú thích. Đưa ra đây vì nó là
kiến thức nền, không phải tài liệu của file đó — để trong source thì mỗi lần mở
`main.py` phải cuộn qua 50 dòng mới thấy dòng code đầu tiên.)*

### `async` — lập trình bất đồng bộ

Từ khóa khai báo hàm bất đồng bộ (`async def`). Tác dụng: ứng dụng **không bị nghẽn**
khi chờ các thao tác I/O tốn thời gian — truy vấn database, gọi API ngoài, gửi tin nhắn.

Trong dự án này: khi một bác sĩ chờ kết quả từ Supabase, nhờ `async` mà tiến trình
trên Mac mini không đứng yên — nó vẫn phục vụ được request của lễ tân và thu ngân
khác cùng lúc. Không có `async`, 35 người dùng sẽ phải xếp hàng chờ nhau.

### `asynccontextmanager` — quản lý tài nguyên

Decorator (từ thư viện `contextlib`) tạo ra cú pháp `async with ...` bằng một từ khóa
`yield` duy nhất:

- code **trước** `yield` → chạy để **mở / khởi tạo** tài nguyên
- lệnh `yield` → tạm dừng, bàn giao tài nguyên cho ứng dụng dùng
- code **sau** `yield` (hoặc khối `finally`) → chạy để **đóng / dọn dẹp**

### `lifespan` — vòng đời ứng dụng FastAPI

Cơ chế chuẩn của FastAPI (thay cho `on_event("startup")` / `on_event("shutdown")` cũ)
để làm những việc cần thiết khi web app vừa bật và khi bị tắt. Bản thân `lifespan`
chính là một hàm được bọc bởi `@asynccontextmanager`. Xem Phần 5 để đọc từng dòng.

### `UUID` — mã định danh duy nhất toàn cầu

*Universally Unique Identifier*: chuỗi 36 ký tự (32 ký tự chữ/số + 4 dấu gạch ngang),
chia 5 nhóm theo dạng `8-4-4-4-12`. Ví dụ: `3f2b1234-5678-4abc-8def-90123456789a`.

Import `UUID` trong file Python dùng để:

- **Xác thực**: ép chuỗi từ trình duyệt thành đối tượng `UUID`. Chuỗi rác sai định
  dạng sẽ báo lỗi **ngay trước khi** đụng tới database.
- **Tạo mới**: `uuid.uuid4()` sinh mã định danh ngẫu nhiên.
