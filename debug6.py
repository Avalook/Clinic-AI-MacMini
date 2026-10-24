import asyncio, asyncpg
import sys
sys.path.append("/Users/quangdang/Projects/wt-danh-muc/src")

async def main():
    pool = await asyncpg.create_pool("postgresql://postgres:postgres@127.0.0.1:55600/postgres")
    
    # We will just write the test logic here without pytest
    from tests.services.test_thu_tien_xep_phong_mang_sang_db import _dung, _benh_nhan, _dong_luot
    from tests.services.test_sinh_hieu_cung_buoi_db import _check_in, _do, _flow
    
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    l1 = await _check_in(pool, ca, pid, ca.loai_kham)
    await _do(pool, ca, l1.visit, weight_kg=60, height_cm=160)
    await _dong_luot(pool, l1.visit)
    l2 = await _check_in(pool, ca, pid, ca.loai_thu_thuat)
    f = await _flow(pool, l2.visit)
    print("Visit 1 vitals:", (await _flow(pool, l1.visit))["vitals_status"])
    print("Visit 2 vitals:", f["vitals_status"])
    
    # Check what sinh_hieu_cua_buoi returns
    do = await pool.fetchrow("SELECT * FROM vital_measurement WHERE visit_id = $1::uuid", l1.visit)
    print("Measurement 1:", dict(do) if do else None)

    await pool.close()
asyncio.run(main())
