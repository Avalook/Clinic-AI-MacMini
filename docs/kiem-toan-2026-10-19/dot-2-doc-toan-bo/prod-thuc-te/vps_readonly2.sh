#!/bin/bash
# THU THUC TE PROD lan 2 - CHI DOC. Database (container clinicai_db) + phan loai loi theo TEN su kien (khong lay noi dung).
export LC_ALL=C
P=/home/clinicai/clinicai
sec() { printf '\n##### %s\n' "$1"; }
sec "LOI THEO TEN SU KIEN (24 gio gan nhat, top 12; chi lay truong event/msg)"
for c in clinicai_prod-api-1 clinicai_prod-dashboard-1; do
  echo "--- $c"; docker logs --since 24h "$c" 2>&1 </dev/null | grep -iE 'error|exception|traceback|critical' | grep -oE '"(event|msg|message)": ?"[A-Za-z0-9_. :-]{1,70}"' | sort | uniq -c | sort -rn | head -12
done
echo "--- caddy (level error, theo msg)"; docker logs --since 24h clinicai_prod-caddy-1 2>&1 </dev/null | grep '"level":"error"' | grep -oE '"msg":"[^"]{1,70}"' | sort | uniq -c | sort -rn | head -8
sec "DATABASE (chi doc, chi dem/ten, ep read-only)"
DB=clinicai_db
echo "container db: ${DB:-KHONG TIM THAY}"
q() { docker exec -e PGOPTIONS='-c default_transaction_read_only=on' "$DB" psql -U postgres -d postgres -tA -F ' | ' -c "$1" </dev/null 2>&1 | head -${2:-60}; }
if [ -n "$DB" ]; then
  echo "--- phien ban / kich thuoc:"; q "select version();" 1; q "select pg_size_pretty(pg_database_size('postgres'));" 1
  echo "--- so migration da ap (so cai) / moi nhat:"; q "select count(*), max(version) from supabase_migrations.schema_migrations;" 1
  echo "--- 5 migration ap gan nhat:"; q "select version||' '||coalesce(name,'') from supabase_migrations.schema_migrations order by version desc limit 5;" 5
  echo "--- migration trong repo (so tep / moi nhat):"; ls "$P/supabase/migrations" 2>/dev/null | grep -c '\.sql$'; ls "$P/supabase/migrations" 2>/dev/null | tail -2
  echo "--- migration co trong repo ma CHUA ap vao DB:"
  comm -13 <(q "select version from supabase_migrations.schema_migrations;" 5000 | sed 's/ //g' | sort) <(ls "$P/supabase/migrations" 2>/dev/null | grep '\.sql$' | sed 's/_.*//' | sort) | head -30; echo "(het danh sach)"
  echo "--- bang trong public KHONG bat RLS (ten):"; q "select c.relname from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' and not c.relrowsecurity order by 1;" 80
  echo "--- so bang public / so policy:"; q "select (select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r'), (select count(*) from pg_policies where schemaname='public');" 1
  echo "--- so bang ma vai 'authenticated' co quyen ghi truc tiep:"; q "select count(distinct table_name) from information_schema.role_table_grants where table_schema='public' and grantee='authenticated' and privilege_type in ('INSERT','UPDATE','DELETE');" 1
  echo "--- so bang ma vai 'anon' co bat ky quyen nao:"; q "select count(distinct table_name) from information_schema.role_table_grants where table_schema='public' and grantee='anon';" 1
  echo "--- vai (role) trong database:"; q "select rolname, 'superuser='||rolsuper, 'login='||rolcanlogin, 'bypassrls='||rolbypassrls from pg_roles where rolname !~ '^pg_' order by 1;" 40
  echo "--- ham SECURITY DEFINER trong public (so luong):"; q "select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.prosecdef;" 1
  echo "--- bang lon nhat (ten, so dong uoc tinh):"; q "select relname, n_live_tup from pg_stat_user_tables where schemaname='public' order by n_live_tup desc limit 25;" 25
  echo "--- bang lien quan su kien/canh bao/loi (ten, so dong uoc tinh):"; q "select relname, n_live_tup from pg_stat_user_tables where relname ~ 'event|outbox|dead|canh_bao|loi_nhom|thong_bao|timer|receipt|idempot' order by 1;" 40
  echo "--- so luat thu tu bat buoc cu (visit_gate_rule) dang bat:"; q "select case when to_regclass('public.visit_gate_rule') is null then 'khong co bang' else (select count(*) filter (where is_active)||' dang bat / '||count(*)||' tong' from public.visit_gate_rule) end;" 1
  echo "--- so luat bac si bat buoc dang bat:"; q "select case when to_regclass('public.luat_bac_si_bat_buoc') is null then 'khong co bang' else (select count(*) filter (where is_active)||' dang bat / '||count(*)||' tong' from public.luat_bac_si_bat_buoc) end;" 1
  echo "--- so phong kham (clinic) / co so / nhan vien dang hoat dong:"; q "select (select count(*) from public.clinic), (select count(*) from public.location), (select count(*) from public.staff where is_active);" 1
  echo "--- tuoi du lieu moi nhat (lan kham, thanh toan gan nhat):"; q "select (select max(created_at) from public.visit), (select max(created_at) from public.payment);" 1
fi
printf '\n##### HET\n'
