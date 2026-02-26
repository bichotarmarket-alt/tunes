"""Test script to verify SSID data is returned correctly"""
import asyncio
from sqlalchemy import select
from core.database import get_db
from models import User, Account


async def test_account_ssid_data():
    """Test that SSID data is returned correctly from database"""
    print("=== Test: Account SSID Data ===")

    async for db in get_db():
        # Get a test user
        result = await db.execute(select(User).limit(1))
        user = result.scalar_one_or_none()

        if not user:
            print("✗ No user found in database")
            return

        print(f"User ID: {user.id}")
        print(f"User Email: {user.email}")

        # Get user's accounts
        result = await db.execute(
            select(Account).where(Account.user_id == user.id)
        )
        accounts = result.scalars().all()

        print(f"\nFound {len(accounts)} account(s)")

        for account in accounts:
            print(f"\n--- Account {account.id} ---")
            print(f"Name: {account.name}")
            print(f"SSID Demo: {account.ssid_demo}")
            print(f"SSID Real: {account.ssid_real}")
            print(f"Autotrade Demo: {account.autotrade_demo}")
            print(f"Autotrade Real: {account.autotrade_real}")

            # Check if SSID is actually present
            has_ssid_demo = account.ssid_demo and len(account.ssid_demo.strip()) > 0
            has_ssid_real = account.ssid_real and len(account.ssid_real.strip()) > 0

            print(f"Has SSID Demo (checked): {has_ssid_demo}")
            print(f"Has SSID Real (checked): {has_ssid_real}")

        break


if __name__ == "__main__":
    asyncio.run(test_account_ssid_data())
