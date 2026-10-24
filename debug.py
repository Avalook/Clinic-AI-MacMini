import asyncio, asyncpg
async def main():
    conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:55600/postgres")
    try:
        st = await conn.fetchrow("SELECT id, code, tu_van FROM service_type WHERE is_active ORDER BY code LIMIT 1")
        print("First service_type:", dict(st) if st else None)
        all_st = await conn.fetch("SELECT code, tu_van FROM service_type WHERE is_active ORDER BY code")
        print("All active service_types:")
        for x in all_st: print(dict(x))
    finally:
        await conn.close()
asyncio.run(main())
