import asyncio
from sqlalchemy import text
from app.infrastructure.database import engine


async def main():
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        print("SQLAlchemy connection succeeded:", result.scalar())

    await engine.dispose()


asyncio.run(main())