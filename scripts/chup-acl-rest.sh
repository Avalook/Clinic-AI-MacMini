#!/bin/bash
# Chụp quyền của anon / authenticated / PUBLIC trên schema public (thứ /rest/v1
# để lộ ra Internet) và SINH SẴN rollback.sql đưa quyền về y hệt lúc chụp.
#
# CHỈ ĐỌC: script không ghi gì vào database. rollback.sql chỉ là tệp; muốn áp
# thì người chạy tự áp (xem docs/ke-hoach/khoa-rest-v1-2210.md, mục 5).
#
# Vì sao cần: bản sao lưu dùng `pg_dump --no-acl`, nên quyền trên prod KHÔNG nằm
# trong bản sao nào. Chụp ngay trước khi áp 20261022900000_khoa_rest_v1.sql là
# cách duy nhất có đường lui chính xác.
#
# Dùng:
#   CLINIC_DB_CONTAINER=clinicai_db ./scripts/chup-acl-rest.sh ~/acl-rest/truoc
#   CLINIC_DB_DSN='postgresql://…' ./scripts/chup-acl-rest.sh /tmp/acl
#
# Ra ba tệp trong thư mục đích (tạo nếu chưa có, KHÔNG ghi đè tệp có sẵn):
#   acl.txt       bản chụp đọc được, sắp xếp cố định — `diff` hai lần chụp
#                 là thấy đúng chỗ khác
#   dp.txt        `\dp public.*` để người đọc (không dùng để so)
#   rollback.sql  một giao dịch: dọn quyền hiện có của anon/authenticated/PUBLIC
#                 rồi GRANT lại y như chụp, dựng lại policy của staff +
#                 clinic_membership, trả quyền mặc định (bảng/hàm sinh sau)
#
# Không đặt rollback.sql vào supabase/migrations/. Luật repo: DB chỉ đổi bằng
# migration — cần hoàn tác hẳn thì chép nó thành migration MỚI.

set -euo pipefail

DICH_DIR="${1:-}"
if [[ -z "$DICH_DIR" ]]; then
  echo "Dùng: $0 <thư mục đích>   (đặt CLINIC_DB_CONTAINER hoặc CLINIC_DB_DSN)" >&2
  exit 2
fi

if [[ -n "${CLINIC_DB_DSN:-}" ]]; then
  run_sql() { psql "$CLINIC_DB_DSN" -X -v ON_ERROR_STOP=1 -q "$@"; }
elif [[ -n "${CLINIC_DB_CONTAINER:-}" ]]; then
  run_sql() {
    docker exec -i "$CLINIC_DB_CONTAINER" \
      psql -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" \
           -X -v ON_ERROR_STOP=1 -q "$@"
  }
else
  echo "Chưa chọn đích: đặt CLINIC_DB_CONTAINER=clinicai_db (VPS) hoặc CLINIC_DB_DSN." >&2
  exit 2
fi

mkdir -p "$DICH_DIR"
for t in acl.txt dp.txt rollback.sql; do
  if [[ -e "$DICH_DIR/$t" ]]; then
    echo "Đã có $DICH_DIR/$t — chọn thư mục khác, không ghi đè bản chụp cũ." >&2
    exit 1
  fi
done

# Mọi câu dưới đây chạy trong giao dịch CHỈ ĐỌC: lỡ có câu ghi thì Postgres từ chối.
# search_path = pg_catalog để tên hàm và biểu thức policy in kèm `public.` —
# rollback.sql không phụ thuộc search_path của phiên áp nó.
doc() {
  { echo "BEGIN READ ONLY; SET LOCAL search_path TO pg_catalog;"; cat; echo "ROLLBACK;"; } |
    run_sql -At
}

# ── 1. Bản chụp đọc được ─────────────────────────────────────────────────────
{
  echo "# ACL /rest/v1 — anon, authenticated, PUBLIC trên schema public"
  echo "# database: $(doc <<<"SELECT current_database() || ' · ' || version();")"
  echo
  echo "## Quyền mức bảng/view/sequence (pg_class.relacl)"
  doc <<'SQL'
SELECT format('%s|%s|%s|%s', c.relkind, c.relname,
              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END,
              a.privilege_type)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(c.relacl) a
 WHERE n.nspname = 'public'
   AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
 ORDER BY 1;
SQL
  echo
  echo "## Quyền theo cột (pg_attribute.attacl)"
  doc <<'SQL'
SELECT format('%s.%s|%s|%s', c.relname, at.attname,
              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END,
              a.privilege_type)
  FROM pg_attribute at
  JOIN pg_class c ON c.oid = at.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(at.attacl) a
 WHERE n.nspname = 'public' AND at.attnum > 0 AND NOT at.attisdropped
   AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
 ORDER BY 1;
SQL
  echo
  echo "## EXECUTE hàm (pg_proc.proacl; NULL = mặc định Postgres = PUBLIC gọi được)"
  doc <<'SQL'
SELECT format('%s|%s|%s', p.oid::regprocedure,
              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END,
              a.privilege_type)
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  CROSS JOIN LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
 WHERE n.nspname = 'public'
   AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
 ORDER BY 1;
SQL
  echo
  echo "## Quyền mặc định cho đối tượng sinh sau (pg_default_acl, gồm mặc định ngầm)"
  doc <<'SQL'
WITH vai AS (
    SELECT oid FROM pg_roles WHERE rolname = 'postgres'
    UNION SELECT defaclrole FROM pg_default_acl
), muc AS (
    SELECT d.defaclrole AS vai, d.defaclnamespace AS ns, d.defaclobjtype AS loai,
           d.defaclacl AS acl
      FROM pg_default_acl d
     WHERE d.defaclnamespace IN (0, 'public'::regnamespace)
    UNION ALL
    -- Không có dòng toàn cục = Postgres dùng acldefault (hàm: PUBLIC gọi được).
    SELECT v.oid, 0, l.loai::"char", acldefault(lower(l.loai)::"char", v.oid)
      FROM vai v CROSS JOIN (VALUES ('r'), ('S'), ('f'), ('T'), ('n')) l(loai)
     WHERE NOT EXISTS (SELECT 1 FROM pg_default_acl d
                        WHERE d.defaclrole = v.oid AND d.defaclnamespace = 0
                          AND d.defaclobjtype = l.loai::"char")
)
SELECT format('%s|%s|%s|%s|%s', m.vai::regrole,
              CASE m.ns WHEN 0 THEN '(toàn cục)' ELSE m.ns::regnamespace::text END,
              m.loai,
              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END,
              a.privilege_type)
  FROM muc m CROSS JOIN LATERAL aclexplode(m.acl) a
 WHERE a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
 ORDER BY 1;
SQL
  echo
  echo "## Policy của staff, clinic_membership"
  doc <<'SQL'
SELECT format('%s|%s|%s|%s|%s|USING %s|CHECK %s', tablename, policyname, permissive,
              cmd, roles, coalesce(qual, '-'), coalesce(with_check, '-'))
  FROM pg_policies
 WHERE schemaname = 'public' AND tablename IN ('staff', 'clinic_membership')
 ORDER BY tablename, policyname;
SQL
} >"$DICH_DIR/acl.txt"

# Bảng `\dp` để người đọc; không dùng để so: sau REVOKE + GRANT lại, Postgres
# đổi thứ tự mục trong ACL và viết rõ quyền chủ bảng thay cho NULL — cùng nghĩa
# nhưng `diff` báo khác.
printf 'BEGIN READ ONLY;\n\\dp public.*\nROLLBACK;\n' | run_sql >"$DICH_DIR/dp.txt"

# ── 2. rollback.sql ──────────────────────────────────────────────────────────
{
  cat <<'HEAD'
-- SINH TỰ ĐỘNG bởi scripts/chup-acl-rest.sh — đưa quyền anon/authenticated/PUBLIC
-- trên schema public về y hệt lúc chụp (acl.txt cùng thư mục). Không đổi dữ liệu.
-- Áp xong: chụp lại bằng chính script đó và `diff` acl.txt — phải trùng khít.
BEGIN;

-- Dọn sạch quyền hiện có của ba vai, rồi cấp lại đúng bản chụp.
REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL ROUTINES  IN SCHEMA public FROM PUBLIC, anon, authenticated;
DO $don_mac_dinh$
DECLARE r record;
BEGIN
    FOR r IN SELECT DISTINCT ro.rolname FROM pg_roles ro
              WHERE ro.rolname = 'postgres'
                 OR ro.oid IN (SELECT defaclrole FROM pg_default_acl)
    LOOP
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated', r.rolname);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated', r.rolname);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon, authenticated', r.rolname);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL ON TYPES FROM PUBLIC, anon, authenticated', r.rolname);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated', r.rolname);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated', r.rolname);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon, authenticated', r.rolname);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I REVOKE ALL ON TYPES FROM PUBLIC, anon, authenticated', r.rolname);
    END LOOP;
END
$don_mac_dinh$;

HEAD
  echo "-- Bảng / view / sequence"
  doc <<'SQL'
SELECT format('GRANT %s ON %s public.%I TO %s;', a.privilege_type,
              CASE c.relkind WHEN 'S' THEN 'SEQUENCE' ELSE 'TABLE' END, c.relname,
              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE quote_ident(a.grantee::regrole::text) END)
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(c.relacl) a
 WHERE n.nspname = 'public'
   AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
 ORDER BY 1;
SQL
  echo
  echo "-- Theo cột"
  doc <<'SQL'
SELECT format('GRANT %s (%I) ON TABLE public.%I TO %s;', a.privilege_type, at.attname,
              c.relname,
              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE quote_ident(a.grantee::regrole::text) END)
  FROM pg_attribute at
  JOIN pg_class c ON c.oid = at.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  CROSS JOIN LATERAL aclexplode(at.attacl) a
 WHERE n.nspname = 'public' AND at.attnum > 0 AND NOT at.attisdropped
   AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
 ORDER BY 1;
SQL
  echo
  echo "-- Hàm"
  doc <<'SQL'
SELECT format('GRANT EXECUTE ON ROUTINE %s TO %s;', p.oid::regprocedure,
              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE quote_ident(a.grantee::regrole::text) END)
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  CROSS JOIN LATERAL aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
 WHERE n.nspname = 'public'
   AND a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
 ORDER BY 1;
SQL
  echo
  echo "-- Quyền mặc định"
  doc <<'SQL'
WITH vai AS (
    SELECT oid FROM pg_roles WHERE rolname = 'postgres'
    UNION SELECT defaclrole FROM pg_default_acl
), muc AS (
    SELECT d.defaclrole AS vai, d.defaclnamespace AS ns, d.defaclobjtype AS loai,
           d.defaclacl AS acl
      FROM pg_default_acl d
     WHERE d.defaclnamespace IN (0, 'public'::regnamespace)
    UNION ALL
    SELECT v.oid, 0, l.loai::"char", acldefault(lower(l.loai)::"char", v.oid)
      FROM vai v CROSS JOIN (VALUES ('r'), ('S'), ('f'), ('T'), ('n')) l(loai)
     WHERE NOT EXISTS (SELECT 1 FROM pg_default_acl d
                        WHERE d.defaclrole = v.oid AND d.defaclnamespace = 0
                          AND d.defaclobjtype = l.loai::"char")
)
SELECT format('ALTER DEFAULT PRIVILEGES FOR ROLE %I%s GRANT %s ON %s TO %s;',
              m.vai::regrole::text,
              CASE m.ns WHEN 0 THEN '' ELSE ' IN SCHEMA ' || quote_ident(m.ns::regnamespace::text) END,
              a.privilege_type,
              CASE m.loai WHEN 'r' THEN 'TABLES' WHEN 'S' THEN 'SEQUENCES'
                          WHEN 'f' THEN 'FUNCTIONS' WHEN 'T' THEN 'TYPES' ELSE 'SCHEMAS' END,
              CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE quote_ident(a.grantee::regrole::text) END)
  FROM muc m CROSS JOIN LATERAL aclexplode(m.acl) a
 WHERE a.grantee IN (0, 'anon'::regrole, 'authenticated'::regrole)
   -- SCHEMAS chỉ có dạng toàn cục; dạng IN SCHEMA không tồn tại.
   AND NOT (m.loai = 'n' AND m.ns <> 0)
 ORDER BY 1;
SQL
  echo
  echo "-- Policy staff + clinic_membership: bỏ hết cái đang có, dựng lại bản chụp."
  cat <<'DROP'
DO $bo_policy$
DECLARE p record;
BEGIN
    FOR p IN SELECT pol.polname, c.relname FROM pg_policy pol
               JOIN pg_class c ON c.oid = pol.polrelid
               JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'public' AND c.relname IN ('staff', 'clinic_membership')
    LOOP
        EXECUTE format('DROP POLICY %I ON public.%I', p.polname, p.relname);
    END LOOP;
END
$bo_policy$;
DROP
  doc <<'SQL'
SELECT format('CREATE POLICY %I ON public.%I AS %s FOR %s TO %s%s%s;',
              p.polname, c.relname,
              CASE WHEN p.polpermissive THEN 'PERMISSIVE' ELSE 'RESTRICTIVE' END,
              CASE p.polcmd WHEN 'r' THEN 'SELECT' WHEN 'a' THEN 'INSERT'
                            WHEN 'w' THEN 'UPDATE' WHEN 'd' THEN 'DELETE' ELSE 'ALL' END,
              (SELECT string_agg(CASE r WHEN 0 THEN 'PUBLIC'
                                        ELSE quote_ident(r::regrole::text) END, ', ')
                 FROM unnest(p.polroles) r),
              coalesce(' USING (' || pg_get_expr(p.polqual, p.polrelid) || ')', ''),
              coalesce(' WITH CHECK (' || pg_get_expr(p.polwithcheck, p.polrelid) || ')', ''))
  FROM pg_policy p
  JOIN pg_class c ON c.oid = p.polrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relname IN ('staff', 'clinic_membership')
 ORDER BY c.relname, p.polname;
SQL
  echo
  echo "NOTIFY pgrst, 'reload schema';"
  echo "COMMIT;"
} >"$DICH_DIR/rollback.sql"

echo "Đã chụp vào $DICH_DIR:"
echo "  acl.txt      $(grep -c '|' "$DICH_DIR/acl.txt") dòng quyền/policy"
echo "  rollback.sql $(grep -c '^GRANT\|^ALTER DEFAULT\|^CREATE POLICY' "$DICH_DIR/rollback.sql") lệnh GRANT/policy"
