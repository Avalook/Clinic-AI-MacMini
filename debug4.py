import asyncio, asyncpg

async def main():
    pool = await asyncpg.create_pool("postgresql://postgres:postgres@127.0.0.1:55600/postgres")
    async with pool.acquire() as conn:
        cid = await conn.fetchval("SELECT id FROM clinic LIMIT 1")
        print("Clinic:", cid)
        await conn.execute("INSERT INTO service_price (clinic_id, service_code, name, \"group\", ma_kiotviet, unit_price, active) VALUES ($1, 'PRP_TEST', 'Bơm PRP niêm mạc tử cung (TPC)', 'dich_vu', 'SP000140', 8000000, true) ON CONFLICT DO NOTHING", cid)
        
        ghep = await conn.fetch("SELECT sp.name, g.* FROM ghep_danh_muc_dich_vu('kiot_0110') g JOIN service_price sp ON sp.id = g.service_price_id WHERE g.thu_tu IN (3, 80)")
        for r in ghep:
            print("GHEP:", dict(r))
            
        await conn.fetchrow("SELECT * FROM dong_bo_danh_muc_dich_vu('kiot_0110')")
        
        sp = await conn.fetchval("SELECT name FROM service_price WHERE ma_kiotviet = 'SP000140'")
        print("Updated PRP name:", sp)
        
        lcb = await conn.fetch("SELECT name, service_code FROM service_price WHERE name = 'Liên cầu B'")
        print("Lien cau B rows:", [dict(x) for x in lcb])

    await pool.close()
asyncio.run(main())
