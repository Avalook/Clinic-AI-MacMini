import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:55600/postgres")
    try:
        st = await conn.fetchrow("SELECT id, code, qua_tu_van FROM service_type WHERE is_active ORDER BY code LIMIT 1")
        print("First service_type:", dict(st) if st else None)
    finally:
        await conn.close()
asyncio.run(main())
