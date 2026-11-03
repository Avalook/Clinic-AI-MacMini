# Postgres 17 + pgBackRest — ảnh DB của prod/staging khi bật sao lưu nối tiếp
# (docs/KE-HOACH-SAO-LUU-NOI-TIEP.md).
#
# VÌ SAO CÓ ẢNH RIÊNG. `archive_command` chạy BÊN TRONG container DB, nên
# pgBackRest phải nằm trong chính ảnh đó; `postgres:17` không có sẵn. Ảnh gốc là
# Debian có sẵn kho apt PGDG, nên gói `pgbackrest` đúng bản cho PG17.
#
# Local và CI vẫn dùng `postgres:17` trần (SUPABASE_DB_IMAGE không đặt) — ảnh
# này chỉ dựng trên máy chủ:
#   docker build -f docker/db/Dockerfile -t clinicai-db:17-pgbackrest docker/db
FROM postgres:17

RUN apt-get update \
 && apt-get install -y --no-install-recommends pgbackrest \
 && rm -rf /var/lib/apt/lists/* \
 && install -d -o postgres -g postgres -m 750 /var/lib/pgbackrest

COPY pgbackrest.conf /etc/pgbackrest/pgbackrest.conf
