f = "src/tests/services/test_sinh_hieu_khong_chan_db.py"
with open(f) as file:
    c = file.read()
c = c.replace(
    '"SELECT id::text FROM service_type WHERE is_active AND NOT coalesce(qua_tu_van, false) ORDER BY code LIMIT 1"',
    '"SELECT id::text FROM service_type WHERE is_active"\n            " AND NOT coalesce(qua_tu_van, false) ORDER BY code LIMIT 1"'
)
with open(f, "w") as file:
    file.write(c)
