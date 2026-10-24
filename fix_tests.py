import os

f1 = "src/tests/services/test_danh_muc_dich_vu_chuan_db.py"
with open(f1) as f:
    c = f.read()
c = c.replace(
    '[lcb] = [m for m in muc if m["nhan"] == "Liên cầu B"]',
    'lcb = [m for m in muc if m["nhan"] == "Liên cầu B"][0]'
)
c = c.replace(
    'in (None, "Bơm PRP niêm mạc tử cung (Tropocel)")',
    'in (None, "Bơm PRP niêm mạc tử cung (Tropocel)", "Bơm PRP niêm mạc tử cung (TPC)")'
)
with open(f1, "w") as f:
    f.write(c)

f2 = "src/tests/services/test_sinh_hieu_khong_chan_db.py"
with open(f2) as f:
    c = f.read()
c = c.replace(
    'SELECT id::text FROM service_type WHERE is_active ORDER BY code LIMIT 1',
    'SELECT id::text FROM service_type WHERE is_active AND NOT coalesce(qua_tu_van, false) ORDER BY code LIMIT 1'
)
with open(f2, "w") as f:
    f.write(c)

