#!/usr/bin/env bash
# Đo CHỈ ĐỌC trên VPS: DB prod/staging, ổ đĩa, sao lưu, máy. In một JSON ra stdout.
# Chạy từ Mac qua scripts/do-so-do.py (gửi tệp này vào `ssh … bash -s`), không chạy tay.
set -u
q() {  # q <container> <sql> → một dòng kết quả, phân tách bằng |
  docker exec "$1" psql -U postgres -d postgres -AtF'|' -c "$2" 2>/dev/null
}
db() {  # db <container>
  local c=$1
  local kn max size
  kn=$(q "$c" "select count(*) from pg_stat_activity where datname is not null")
  max=$(q "$c" "show max_connections")
  size=$(q "$c" "select round(pg_database_size('postgres')/1024.0/1024/1024,2)")
  local theo_trang_thai
  theo_trang_thai=$(q "$c" "select coalesce(state,'?')||':'||count(*) from pg_stat_activity where datname is not null group by 1" | paste -sd, -)
  local bang_to
  bang_to=$(q "$c" "select relname||':'||round(pg_total_relation_size(relid)/1024.0/1024,1) from pg_statio_user_tables order by pg_total_relation_size(relid) desc limit 8" | paste -sd, -)
  local cham
  cham=$(q "$c" "select calls||'|'||round(mean_exec_time)||'|'||round(total_exec_time/1000)||'|'||regexp_replace(left(query,90),'\s+',' ','g') from pg_stat_statements order by total_exec_time desc limit 8" | python3 -c "
import sys,json
out=[]
for l in sys.stdin:
    p=l.rstrip('\n').split('|',3)
    if len(p)==4: out.append({'so_lan':int(p[0]),'tb_ms':int(p[1]),'tong_giay':int(p[2]),'cau':p[3]})
print(json.dumps(out,ensure_ascii=False))")
  local tu
  tu=$(q "$c" "select stats_reset from pg_stat_statements_info" )
  printf '{"ket_noi":%s,"max_ket_noi":%s,"dung_luong_gb":%s,"ket_noi_theo_trang_thai":"%s","bang_to_mb":"%s","cau_ton_thoi_gian_nhat":%s,"thong_ke_cau_tu":"%s"}' \
    "${kn:-null}" "${max:-null}" "${size:-null}" "$theo_trang_thai" "$bang_to" "${cham:-[]}" "$tu"
}
pct() { df -P "$1" 2>/dev/null | awk 'NR==2{gsub("%","",$5); printf "{\"dung_pct\":%s,\"tong_gb\":%.0f,\"con_gb\":%.0f}", $5, $2/1048576, $4/1048576}'; }
bk() {  # bk <thư mục> → bản dump chính mới nhất + tuổi giờ + số tệp
  local f
  # Thư mục sao lưu có cả _auth, lịch sử Notion và .manifest — "mới nhất theo giờ"
  # dễ chọn nhầm chúng (bẫy #523). Chỉ lấy bản dump chính *.sql.gz.
  f=$(ls -t "$1" 2>/dev/null | grep -E '\.sql\.gz$' | grep -v -e _auth -e notion | head -1)
  if [ -z "$f" ]; then printf '{"thu_muc":"%s","ban_moi_nhat":null}' "$1"; return; fi
  local t now
  t=$(stat -c %Y "$1/$f"); now=$(date +%s)
  # VPS không có bc — tính bằng awk.
  printf '{"thu_muc":"%s","ban_moi_nhat":"%s","tuoi_gio":%s,"co_mb":%s,"so_tep":%s}' "$1" "$f" \
    "$(awk -v a="$now" -v b="$t" 'BEGIN{printf "%.1f",(a-b)/3600}')" \
    "$(awk -v s="$(stat -c %s "$1/$f")" 'BEGIN{printf "%.0f",s/1048576}')" "$(ls "$1" | wc -l)"
}
printf '{"do_luc":"%s",' "$(date '+%F %T %z')"
printf '"db":{"prod":%s,"staging":%s},' "$(db clinicai_db)" "$(db clinicai_stg_db)"
printf '"o_dia":{"vps_goc":%s,"cfs":%s},' "$(pct /)" "$(pct /mnt/viettel-cfs)"
printf '"sao_luu":{"vps_hang_dem":%s,"vps_15_phut":%s,"cfs":%s},' "$(bk /home/clinicai/backups/clinicai)" "$(bk /home/clinicai/backups/clinicai-15p)" "$(bk /mnt/viettel-cfs/db-backups)"
printf '"may":{"nhan":%s,"tai_1_5_15":"%s","ram_mb":%s,"ram_con_mb":%s}}\n' "$(nproc)" "$(cut -d' ' -f1-3 /proc/loadavg)" "$(free -m | awk '/Mem:/{print $2}')" "$(free -m | awk '/Mem:/{print $7}')"
