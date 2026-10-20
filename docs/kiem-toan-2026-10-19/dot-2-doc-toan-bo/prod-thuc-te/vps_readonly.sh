#!/bin/bash
# THU THUC TE PROD - CHI DOC. Khong ghi, khong sua, khong restart.
# Khong in gia tri bi mat, khong doc noi dung benh nhan. Chi dem, ten, trang thai.
# Database: PGOPTIONS ep read-only o phia server. Chay: ssh clinic-vps-moi 'bash -s' < vps_readonly.sh
export LC_ALL=C
P=/home/clinicai/clinicai
sec() { printf '\n##### %s\n' "$1"; }

sec "THOI DIEM"; date -Is; hostname

sec "GIT PROD"
cd "$P" 2>/dev/null && { git rev-parse HEAD; git log -1 --format='%ad %s' --date=iso; echo "nhanh: $(git rev-parse --abbrev-ref HEAD)"; echo "tep thay doi chua commit: $(git status --short | wc -l)"; }

sec "HE DIEU HANH"
grep PRETTY_NAME /etc/os-release; uname -r; echo "khoi dong luc: $(uptime -s)"; uptime
[ -f /var/run/reboot-required ] && echo "CAN KHOI DONG LAI (reboot-required)" || echo "khong co reboot-required"
docker --version; echo "docker daemon bat tu: $(systemctl show docker -p ActiveEnterTimestamp --value 2>/dev/null)"

sec "DIA VA BO NHO"; df -h / /mnt/viettel-cfs /home 2>/dev/null; free -m

sec "CONTAINER (ten | restart policy | so lan restart | suc khoe | trang thai)"
for c in $(docker ps -a --format '{{.Names}}' </dev/null); do
  docker inspect -f '{{.Name}} | {{.HostConfig.RestartPolicy.Name}} | restarts={{.RestartCount}} | health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} | {{.State.Status}} | start={{.State.StartedAt}}' "$c" </dev/null
done

sec "HEN GIO (systemd timers clinicai)"
systemctl list-timers --all --no-pager 2>/dev/null | grep -iE 'clinicai|backup|NEXT' | head -30
echo "--- dich vu clinicai that bai:"; systemctl --failed --no-pager --no-legend 2>/dev/null | head

sec "SAO LUU (ten, thoi gian, kich thuoc; khong doc noi dung)"
for d in /home/clinicai /var/backups /mnt/viettel-cfs; do
  find "$d" -maxdepth 4 -type f \( -name '*.dump' -o -name '*.sql' -o -name '*.sql.gz' -o -name '*.tar.gz' -o -name '*.dump.gz' -o -name '*.age' -o -name '*.zst' \) -mtime -30 2>/dev/null \
   | head -400 | while read -r f; do stat -c '%y %s %n' "$f"; done | sort -r | head -8
done
echo "--- thu muc co chu backup:"; ls -d /home/clinicai/*backup* /var/backups/clinicai* /mnt/viettel-cfs/*backup* 2>/dev/null

sec "CONG MANG DANG LANG NGHE"; ss -tlnH 2>/dev/null | awk '{print $4}' | sort -u
echo "--- tuong lua:"; (ufw status 2>&1 | head -4) || true

sec "TRUY CAP CONG KHAI (ma HTTP)"
for u in https://dr4women.io.vn/ https://dr4women.io.vn/health https://staging.dr4women.io.vn/ ; do
  printf '%s -> ' "$u"; curl -sS -o /dev/null -m 10 -w '%{http_code}\n' "$u" 2>&1
done

sec "FILE MOI TRUONG (chi ten bien, quyen file, SO SANH PROD vs STAGING bang bam; khong in gia tri)"
PE="$P/.env.prod"; ls -l "$PE" 2>/dev/null | awk '{print "quyen/chu: "$1" "$3}'
[ -f "$PE" ] && echo "so bien prod: $(grep -cE '^[A-Za-z_][A-Za-z0-9_]*=' "$PE")"
SE=$(ls /home/clinicai/clinicai-staging/.env.staging /home/clinicai/clinicai-staging/.env.prod /home/clinicai/clinicai-staging/.env 2>/dev/null | head -1)
echo "file staging: ${SE:-khong tim thay}"
if [ -f "$PE" ] && [ -n "$SE" ]; then
  for k in $(grep -oE '^[A-Za-z_][A-Za-z0-9_]*' "$PE" | grep -iE 'SECRET|PASSWORD|KEY|TOKEN|SALT'); do
    pv=$(grep -m1 "^$k=" "$PE" | cut -d= -f2- | sha256sum | cut -c1-12)
    sv=$(grep -m1 "^$k=" "$SE" | cut -d= -f2- | sha256sum | cut -c1-12)
    if grep -q "^$k=" "$SE"; then [ "$pv" = "$sv" ] && echo "$k: GIONG NHAU giua prod va staging" || echo "$k: khac nhau"; else echo "$k: chi co o prod"; fi
  done
fi

sec "LOI TRONG LOG 7 NGAY (chi dem, khong in noi dung)"
for c in $(docker ps --format '{{.Names}}' </dev/null | grep '^clinicai_prod'); do
  n=$(docker logs --since 168h "$c" 2>&1 </dev/null | grep -ciE 'error|traceback|exception|critical')
  m=$(docker logs --since 24h "$c" 2>&1 </dev/null | grep -ciE 'error|traceback|exception|critical')
  echo "$c: 7 ngay=$n ; 24 gio=$m"
done

sec "DATABASE (chi doc, chi dem/ten, ep read-only)"
DB=$(docker ps --format '{{.Names}}' </dev/null | grep -iE 'prod.*(db|postgres)|supabase.*db|postgres' | grep -viE 'staging|stg|test' | head -1)
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
