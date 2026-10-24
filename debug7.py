import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:55600/postgres")
    st = await conn.fetchrow("SELECT code, qua_tu_van FROM service_type WHERE code = 'KHAM_TONG_QUAT'")
    print("KHAM_TONG_QUAT:", dict(st) if st else None)
    await conn.close()
asyncio.run(main())
