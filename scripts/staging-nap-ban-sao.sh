#!/usr/bin/env bash
# NẠP BẢN SAO LƯU PROD MỚI NHẤT VÀO STAGING + CHE DỮ LIỆU KHÁCH (01/10/2026).
#
# Chạy TRÊN MÁY CỦA STAGING (mặc định: chung VPS prod), từ thư mục staging:
#
#   ./scripts/staging-nap-ban-sao.sh
#
# Hẹn giờ mỗi đêm 03:30 (sau sao lưu 02:15): scripts/systemd/clinicai-staging-nap.*
#
# LÀM GÌ, THEO ĐÚNG THỨ TỰ:
#   1. Chọn bản sao lưu mới nhất (cặp public + _auth), kiểm sha256 theo manifest.
#      Kiểu `rieng` (VPS riêng): kéo cặp mới nhất từ prod qua rsync CHỈ ĐỌC trước.
#   2. Lấy danh sách migration prod đã áp (SELECT trên database prod — chỉ đọc).
#   3. Dừng api / su-kien / dashboard + GoTrue / PostgREST của staging.
#   4. MỘT giao dịch: gỡ public → thay auth.users/identities → tạo lại extension
#      → nạp public → quyền → sổ migration → CHE DỮ LIỆU KHÁCH. Hỏng bất cứ đâu
#      thì huỷ cả khối: staging giữ nguyên dữ liệu hôm qua. Và dữ liệu khách
#      CHƯA CHE không bao giờ được commit vào database staging.
#   5. Áp migration mà code staging có nhưng prod chưa có (nhánh đang thử).
#   6. Bật lại dịch vụ, kiểm: 0 tên khách thật còn lại.
#
# KHÔNG đụng prod: chỉ đọc tệp sao lưu + một câu SELECT sổ migration.
#
# Biến (mặc định đúng cho VPS):
#   STAGING_DIR         thư mục code staging (mặc định: repo chứa script này)
#   STAGING_ENV_FILE    mặc định $STAGING_DIR/.env.staging
#   BAN_SAO_DIR         mặc định $HOME/backups/clinicai
#   BAN_SAO_SSH         kiểu rieng: user@may-prod để rsync bản sao về BAN_SAO_DIR
#   BAN_SAO_SSH_DIR     thư mục sao lưu trên máy prod (mặc định /home/clinicai/backups/clinicai)
#   STG_DB_CONTAINER    mặc định clinicai_stg_db
#   SO_MIGRATION        prod-db | theo-git | theo-code (mặc định: prod-db nếu
#                       thấy container database prod, không thì theo-git)

set -euo pipefail

STAGING_DIR="${STAGING_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STAGING_ENV_FILE="${STAGING_ENV_FILE:-$STAGING_DIR/.env.staging}"
# shellcheck source=lib/staging-chung.sh
. "$STAGING_DIR/scripts/lib/staging-chung.sh"

BAN_SAO_DIR="${BAN_SAO_DIR:-$HOME/backups/clinicai}"
BAN_SAO_SSH="${BAN_SAO_SSH:-}"
BAN_SAO_SSH_DIR="${BAN_SAO_SSH_DIR:-/home/clinicai/backups/clinicai}"
CHE_SQL="$STAGING_DIR/scripts/staging-che-du-lieu.sql"

# Bản MỚI NHẤT theo mốc giờ trong tên (…_YYYYMMDD_HHMMSS.sql.gz), KHÔNG theo
# thứ tự chữ cái: tên còn mang mã nguồn (clinicai-db, atfm… của thời cloud) nên
# sort cả tên sẽ chọn nhầm một bản tháng 8 (bắt được khi thử 01/10/2026).
moi_nhat() {
    grep -E '^(.*/)?clinicai_production_.*_[0-9]{8}_[0-9]{6}\.sql\.gz$' \
        | sed -E 's/^(.*_([0-9]{8}_[0-9]{6})\.sql\.gz)$/\2 \1/' | sort | tail -1 | cut -d' ' -f2-
}
psql_stg() { docker exec -i "$STG_DB" psql -v ON_ERROR_STOP=1 -q -U postgres -d postgres "$@"; }
sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }

kiem_ten_staging
kiem_env_staging
kiem_db_la_staging "$STG_DB"
[ -f "$CHE_SQL" ] || dung "thiếu $CHE_SQL"

# Không chạy chồng lên một lần deploy staging (cùng khoá).
if ! mkdir "$STAGING_DEPLOY_LOCK" 2>/dev/null; then
    dung "staging đang deploy/nạp ($STAGING_DEPLOY_LOCK)."
fi
DA_DUNG=""
don_dep() {
    # Lỗi giữa chừng mà dịch vụ đã dừng → bật lại (dữ liệu cũ vẫn nguyên vì giao
    # dịch đã huỷ). Đừng để staging tắt hẳn chỉ vì một đêm nạp hỏng.
    if [ -n "$DA_DUNG" ]; then
        # shellcheck disable=SC2086
        docker start $DA_DUNG >/dev/null 2>&1 || true
    fi
    rmdir "$STAGING_DEPLOY_LOCK" 2>/dev/null || true
}
trap don_dep EXIT INT TERM

# ── 1. Chọn bản sao lưu ──────────────────────────────────────────────────────
buoc "1/6  Chọn bản sao lưu"
if [ -n "$BAN_SAO_SSH" ]; then
    mkdir -p "$BAN_SAO_DIR"
    MOI="$(ssh -o BatchMode=yes "$BAN_SAO_SSH" "ls -1 '$BAN_SAO_SSH_DIR'" | moi_nhat || true)"
    [ -n "$MOI" ] || dung "không thấy bản sao lưu nào trên $BAN_SAO_SSH:$BAN_SAO_SSH_DIR"
    GOC="${MOI%.sql.gz}"
    rsync -t -e "ssh -o BatchMode=yes" \
        "$BAN_SAO_SSH:$BAN_SAO_SSH_DIR/$MOI" \
        "$BAN_SAO_SSH:$BAN_SAO_SSH_DIR/$MOI.manifest" \
        "$BAN_SAO_SSH:$BAN_SAO_SSH_DIR/${GOC}_auth.sql.gz" "$BAN_SAO_DIR/"
    chmod 600 "$BAN_SAO_DIR"/clinicai_production_* 2>/dev/null || true
    # Giữ 3 bản gần nhất trên máy staging.
    find "$BAN_SAO_DIR" -name 'clinicai_production_*' -mtime +3 -delete 2>/dev/null || true
    xong "đã kéo $MOI từ $BAN_SAO_SSH"
fi
BAN="$(find "$BAN_SAO_DIR" -maxdepth 1 -name 'clinicai_production_*.sql.gz' | moi_nhat || true)"
[ -n "$BAN" ] || dung "không thấy bản sao lưu nào trong $BAN_SAO_DIR"
AUTH="${BAN%.sql.gz}_auth.sql.gz"
MANIFEST="$BAN.manifest"
[ -f "$AUTH" ] || dung "thiếu tệp tài khoản $(basename "$AUTH")"
[ -f "$MANIFEST" ] || dung "thiếu manifest $(basename "$MANIFEST") — không kiểm được mã, không nạp."
MONG="$(sed -n 's/^archive_sha256=//p' "$MANIFEST")"
MONG_AUTH="$(sed -n 's/^auth_sha256=//p' "$MANIFEST")"
[ -n "$MONG" ] && [ "$MONG" = "$(sha "$BAN")" ] || dung "tệp $(basename "$BAN") sai sha256 so với manifest."
[ -n "$MONG_AUTH" ] && [ "$MONG_AUTH" = "$(sha "$AUTH")" ] || dung "tệp $(basename "$AUTH") sai sha256 so với manifest."
gzip -t "$BAN" && gzip -t "$AUTH" || dung "tệp sao lưu không giải nén được."
xong "$(basename "$BAN") (+ _auth) — sha256 khớp manifest"

# Mốc thời gian của bản sao, lấy từ tên: …_YYYYMMDD_HHMMSS.sql.gz
MOC="$(basename "$BAN" .sql.gz | grep -oE '[0-9]{8}_[0-9]{6}$' || true)"
MOC_GIT=""
[ -z "$MOC" ] || MOC_GIT="${MOC:0:4}-${MOC:4:2}-${MOC:6:2} ${MOC:9:2}:${MOC:11:2}:${MOC:13:2} +0700"

# ── 2. Sổ migration của prod lúc sao lưu ─────────────────────────────────────
# Bản dump chỉ có lược đồ public — KHÔNG có sổ supabase_migrations. Ghi sổ sai
# thì bước 5 áp lại một migration đã có (hỏng) hoặc bỏ sót một cái chưa có.
buoc "2/6  Sổ migration của prod"
SO_MIGRATION="${SO_MIGRATION:-}"
if [ -z "$SO_MIGRATION" ]; then
    if docker inspect "$PROD_DB_CONTAINER" >/dev/null 2>&1; then SO_MIGRATION=prod-db; else SO_MIGRATION=theo-git; fi
fi
DS_MIGRATION=""
case "$SO_MIGRATION" in
    prod-db)
        # CHỈ ĐỌC. Giới hạn đã biết: migration áp lên prod SAU giờ sao lưu
        # (02:15 → 03:30) có trong sổ nhưng chưa có trong bản dump → staging
        # thiếu đúng migration đó tới đêm sau. Hiếm (áp migration làm ban ngày).
        DS_MIGRATION="$(docker exec "$PROD_DB_CONTAINER" psql -U postgres -d postgres -tAc \
            "SELECT version FROM supabase_migrations.schema_migrations ORDER BY 1" | tr -d ' \r')"
        ;;
    theo-git)
        # Migration có trên origin/main lúc sao lưu — gần đúng (prod có thể chậm
        # hơn main). Dùng cho VPS riêng, nơi không đọc được database prod.
        git -C "$STAGING_DIR" fetch -q origin main 2>/dev/null || canh "không fetch được origin/main"
        MOC_COMMIT="$(git -C "$STAGING_DIR" rev-list -1 --before="${MOC_GIT:-now}" origin/main 2>/dev/null || true)"
        [ -n "$MOC_COMMIT" ] || dung "không tìm được commit main lúc $MOC_GIT"
        DS_MIGRATION="$(git -C "$STAGING_DIR" ls-tree --name-only "$MOC_COMMIT" supabase/migrations/ \
            | sed -n 's#^supabase/migrations/\([0-9]*\)_.*\.sql$#\1#p')"
        canh "sổ migration lấy theo git (main lúc ${MOC_GIT}) — gần đúng."
        ;;
    theo-code)
        DS_MIGRATION="$(find "$STAGING_DIR/supabase/migrations" -name '*.sql' -exec basename {} \; \
            | sed -n 's#^\([0-9]*\)_.*#\1#p' | sort)"
        canh "sổ migration = mọi migration trong code staging (chỉ đúng khi code staging = prod)."
        ;;
    *) dung "SO_MIGRATION không hợp lệ: $SO_MIGRATION" ;;
esac
SO_DONG="$(printf '%s\n' "$DS_MIGRATION" | grep -c . || true)"
[ "$SO_DONG" -gt 50 ] || dung "sổ migration chỉ có $SO_DONG dòng — nghi đọc hỏng, dừng."
xong "$SO_DONG migration (nguồn: $SO_MIGRATION)"

# ── 3. Dừng dịch vụ đọc database staging ─────────────────────────────────────
buoc "3/6  Dừng api / su-kien / dashboard / GoTrue / PostgREST của staging"
for cap in "$STG_APP_PROJECT:api" "$STG_APP_PROJECT:su-kien" "$STG_APP_PROJECT:dashboard" \
           "$STG_SB_PROJECT:auth" "$STG_SB_PROJECT:rest"; do
    c="$(docker ps -q --filter "label=com.docker.compose.project=${cap%%:*}" \
        --filter "label=com.docker.compose.service=${cap#*:}" | head -1)"
    [ -n "$c" ] || continue
    docker stop "$c" >/dev/null
    DA_DUNG="$DA_DUNG $c"
done
psql_stg -tAc "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity
               WHERE datname = 'postgres' AND pid <> pg_backend_pid()
                 AND backend_type = 'client backend'" >/dev/null
[ "$(psql_stg -tAc "SELECT to_regclass('auth.users') IS NOT NULL")" = "t" ] || \
    dung "database staging chưa có auth.users — GoTrue staging chưa chạy lần nào?"
xong "đã dừng:${DA_DUNG:- (không có gì đang chạy)}"

# ── 4. Một giao dịch: nạp + che ──────────────────────────────────────────────
buoc "4/6  Nạp + che dữ liệu khách — MỘT giao dịch (vài chục giây)"
{
    echo "SET client_min_messages = warning;"
    # GIỮ PHIÊN ĐĂNG NHẬP QUA ĐÊM (02/10/2026): TRUNCATE auth.users CASCADE xoá cả
    # auth.sessions / refresh_tokens / mfa_amr_claims → sáng ra trình duyệt cầm
    # refresh token đã chết ("Refresh Token Not Found"). Chép ra bảng TẠM trước
    # khi xoá, trả lại sau khi nạp tài khoản prod (chỉ phiên của người còn tồn
    # tại). Cùng giao dịch; hỏng thì chỉ cảnh báo — nạp lại vẫn chạy tiếp,
    # người dùng đăng nhập lại (app đã tự đưa về /login: lib/het-phien.ts).
    cat <<'SQL'
DO $giu$
BEGIN
    CREATE TEMP TABLE giu_sessions AS SELECT * FROM auth.sessions;
    CREATE TEMP TABLE giu_refresh  AS SELECT * FROM auth.refresh_tokens;
    IF to_regclass('auth.mfa_amr_claims') IS NOT NULL THEN
        CREATE TEMP TABLE giu_amr AS SELECT * FROM auth.mfa_amr_claims;
    END IF;
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'không giữ được phiên đăng nhập staging (%) — người dùng sẽ phải đăng nhập lại', SQLERRM;
END
$giu$;
SQL
    # Gỡ public TRƯỚC khi xoá auth: DB dựng bằng migration có khoá ngoại
    # public → auth.users; TRUNCATE … CASCADE sẽ lan sang bảng chỉ-thêm và đụng
    # chốt chặn. DROP SCHEMA không chạy trigger xoá hàng.
    echo "DROP SCHEMA IF EXISTS public CASCADE;"
    echo "TRUNCATE auth.users CASCADE;"
    gzip -cd "$AUTH"
    echo "SET client_min_messages = warning;"
    cat <<'SQL'
DO $giu$
BEGIN
    IF to_regclass('pg_temp.giu_sessions') IS NULL OR to_regclass('pg_temp.giu_refresh') IS NULL THEN
        RETURN;  -- bước giữ phiên đã hỏng/bỏ qua — cảnh báo đã in ở trên
    END IF;
    INSERT INTO auth.sessions SELECT s.* FROM giu_sessions s
        WHERE s.user_id IN (SELECT id FROM auth.users) ON CONFLICT DO NOTHING;
    INSERT INTO auth.refresh_tokens SELECT r.* FROM giu_refresh r
        WHERE r.session_id IN (SELECT id FROM auth.sessions) ON CONFLICT DO NOTHING;
    IF to_regclass('pg_temp.giu_amr') IS NOT NULL THEN
        INSERT INTO auth.mfa_amr_claims SELECT a.* FROM giu_amr a
            WHERE a.session_id IN (SELECT id FROM auth.sessions) ON CONFLICT DO NOTHING;
    END IF;
    -- refresh_tokens.id là serial: GoTrue cấp id mới phải lớn hơn mọi id đã trả lại.
    PERFORM setval('auth.refresh_tokens_id_seq', GREATEST(
        (SELECT coalesce(max(id), 1) FROM auth.refresh_tokens),
        (SELECT last_value FROM auth.refresh_tokens_id_seq)));
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'không trả lại được phiên đăng nhập staging (%) — người dùng sẽ phải đăng nhập lại', SQLERRM;
END
$giu$;
SQL
    # Bản dump không chở extension nằm trong public (btree_gist, pg_trgm,
    # unaccent) — thiếu là f_unaccent hỏng ngay dòng COPY patient đầu tiên.
    echo "CREATE SCHEMA public;"
    echo "CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;"
    echo "CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;"
    echo "CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;"
    gzip -cd "$BAN" | sed '/^CREATE SCHEMA public;$/d'
    cat <<'SQL'
SET client_min_messages = warning;
SELECT pg_catalog.set_config('search_path', 'public', false);
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO authenticated, service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO anon, authenticated, service_role;
CREATE SCHEMA IF NOT EXISTS supabase_migrations;
CREATE TABLE IF NOT EXISTS supabase_migrations.schema_migrations (version text PRIMARY KEY, name text, statements text[]);
TRUNCATE supabase_migrations.schema_migrations;
SQL
    printf '%s\n' "$DS_MIGRATION" | grep -E '^[0-9]+$' | \
        sed "s/.*/INSERT INTO supabase_migrations.schema_migrations (version, name) VALUES ('&', 'nap-tu-ban-sao-prod');/"
    echo "SET LOCAL clinicai.che_cho_phep = 'staging';"
    cat "$CHE_SQL"
} | psql_stg --single-transaction >/dev/null
xong "đã nạp + che (giao dịch đã commit)"
xong "giữ lại $(psql_stg -tAc 'SELECT count(*) FROM auth.sessions' | tr -d ' \r') phiên đăng nhập"

# ── 5. Migration của code staging mà prod chưa có ────────────────────────────
buoc "5/6  Bật GoTrue / PostgREST + áp migration code staging mới hơn prod"
for cap in "$STG_SB_PROJECT:auth" "$STG_SB_PROJECT:rest"; do
    c="$(cid_dich_vu "${cap%%:*}" "${cap#*:}")"
    [ -z "$c" ] || docker start "$c" >/dev/null
done
( cd "$STAGING_DIR" && CLINIC_DB_CONTAINER="$STG_DB" ./scripts/apply-pending-migrations.sh --apply )
psql_stg -c "NOTIFY pgrst, 'reload schema';" >/dev/null

# ── 6. Bật lại + kiểm ────────────────────────────────────────────────────────
buoc "6/6  Bật lại ứng dụng staging + kiểm"
for cap in "$STG_APP_PROJECT:api" "$STG_APP_PROJECT:su-kien" "$STG_APP_PROJECT:dashboard"; do
    c="$(cid_dich_vu "${cap%%:*}" "${cap#*:}")"
    [ -z "$c" ] || docker start "$c" >/dev/null
done
DA_DUNG=""
noi_caddy_prod_vao_cau

KIEM="$(psql_stg -tA -F' ' -c "SELECT
    (SELECT count(*) FROM patient),
    (SELECT count(*) FROM patient WHERE full_name !~ '^Khách [0-9]{4,}\$'),
    (SELECT count(*) FROM patient WHERE phone_primary IS NOT NULL AND phone_primary !~ '^09[0-9]{8}\$'),
    (SELECT count(*) FROM staff),
    (SELECT count(*) FROM clinic_room),
    (SELECT count(*) FROM service_type)")"
read -r SO_KHACH CON_TEN CON_SDT SO_NS SO_PHONG SO_DV <<<"$KIEM"
[ "$CON_TEN" = "0" ] && [ "$CON_SDT" = "0" ] || \
    dung "CHE CHƯA SẠCH: còn $CON_TEN tên / $CON_SDT SĐT không phải giá trị giả. Tắt staging: docs/STAGING.md."
xong "khách: $SO_KHACH (đã che hết) · nhân sự: $SO_NS · phòng: $SO_PHONG · dịch vụ: $SO_DV"
NHAT_KY="${STAGING_STATE_DIR:-$HOME/.local/state}/clinicai-staging-nap.log"
mkdir -p "$(dirname "$NHAT_KY")" 2>/dev/null || true
printf '%s\t%s\t%s\n' "$(date '+%F %T')" "$(basename "$BAN")" "$SO_KHACH khách" \
    >> "$NHAT_KY" 2>/dev/null || true
echo "XONG — staging = prod lúc ${MOC_GIT:-?}, dữ liệu khách đã che."
