import asyncio, asyncpg

async def main():
    pool = await asyncpg.create_pool("postgresql://postgres:postgres@127.0.0.1:55600/postgres")
    async with pool.acquire() as conn:
        cid = await conn.fetchval("SELECT id FROM clinic LIMIT 1")
        # Ensure we have the same state as tests by wiping and running seed? No, tests rollback.
        # But let's check what test_danh_muc_kiotviet_db does.
        await conn.execute("INSERT INTO service_price (clinic_id, service_code, name, \"group\", active) VALUES ($1, 'TEST_DUP', 'Liên cầu B', 'dich_vu', true) ON CONFLICT DO NOTHING", cid)
        
        await conn.fetchrow("SELECT * FROM dong_bo_danh_muc_dich_vu('kiot_0110')")
        
        lcb = await conn.fetch("SELECT name, service_code FROM service_price WHERE name = 'Liên cầu B'")
        print("Lien cau B rows:", [dict(x) for x in lcb])

    await pool.close()
asyncio.run(main())
