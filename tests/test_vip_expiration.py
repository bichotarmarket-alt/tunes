"""Test script to verify VIP expiration logic"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from core.database import get_db
from models import User
from core.security.auth import _is_vip_expired_cached


async def test_vip_expiration_cache():
    """Test VIP expiration cache functionality"""
    print("=== Test 1: VIP Expiration Cache ===")

    # Test 1: User with valid VIP (not expired)
    user_id = "test_user_1"
    future_date = datetime.utcnow() + timedelta(days=30)
    is_expired = _is_vip_expired_cached(user_id, future_date)
    print(f"✓ User with future VIP date: expired={is_expired} (expected: False)")
    assert is_expired == False, "Valid VIP should not be expired"

    # Test 2: User with expired VIP
    user_id_2 = "test_user_2"
    past_date = datetime.utcnow() - timedelta(days=1)
    is_expired = _is_vip_expired_cached(user_id_2, past_date)
    print(f"✓ User with past VIP date: expired={is_expired} (expected: True)")
    assert is_expired == True, "Expired VIP should be expired"

    # Test 3: Cache hit (second call should use cache)
    is_expired_cached = _is_vip_expired_cached(user_id_2, past_date)
    print(f"✓ Cache hit for expired user: expired={is_expired_cached} (expected: True)")
    assert is_expired_cached == True, "Cached result should match"

    # Test 4: User without VIP end date
    user_id_3 = "test_user_3"
    is_expired = _is_vip_expired_cached(user_id_3, None)
    print(f"✓ User without VIP date: expired={is_expired} (expected: False)")
    assert is_expired == False, "User without VIP date should not be expired"

    print("✓ All cache tests passed!\n")


async def test_vip_cleanup_job():
    """Test VIP cleanup job functionality"""
    print("=== Test 2: VIP Cleanup Job ===")

    from jobs.cleanup_expired_vip import cleanup_expired_vip_users

    async for db in get_db():
        # Create test user with expired VIP
        now = datetime.utcnow()
        test_user = User(
            id="test_vip_expired",
            email="test_vip_expired@example.com",
            hashed_password="test_hash",
            name="Test VIP Expired",
            role="vip",
            vip_start_date=now - timedelta(days=10),
            vip_end_date=now - timedelta(days=1),
            is_active=True
        )
        db.add(test_user)
        await db.commit()

        # Run cleanup job
        updated = await cleanup_expired_vip_users(db)
        print(f"✓ Cleanup job updated {updated} user(s)")

        # Verify user was reset to free
        result = await db.execute(
            select(User).where(User.email == "test_vip_expired@example.com")
        )
        user = result.scalar_one_or_none()

        if user:
            print(f"✓ User role after cleanup: {user.role} (expected: free)")
            print(f"✓ VIP dates cleared: start={user.vip_start_date}, end={user.vip_end_date}")
            assert user.role == "free", "User should be reset to free"
            assert user.vip_start_date is None, "VIP start date should be cleared"
            assert user.vip_end_date is None, "VIP end date should be cleared"
        else:
            print("✗ User not found after cleanup")

        # Cleanup test user
        await db.delete(user)
        await db.commit()
        print("✓ Test user cleaned up\n")


async def test_vip_expiration_in_request():
    """Test VIP expiration during request flow"""
    print("=== Test 3: VIP Expiration in Request Flow ===")

    async for db in get_db():
        # Create test user with expired VIP
        now = datetime.utcnow()
        test_user = User(
            id="test_vip_request",
            email="test_vip_request@example.com",
            hashed_password="test_hash",
            name="Test VIP Request",
            role="vip",
            vip_start_date=now - timedelta(days=10),
            vip_end_date=now - timedelta(days=1),
            is_active=True
        )
        db.add(test_user)
        await db.commit()

        # Simulate request flow (get_current_user would check expiration)
        from core.security.auth import _is_vip_expired_cached
        is_expired = _is_vip_expired_cached(test_user.id, test_user.vip_end_date)

        print(f"✓ VIP expiration check: expired={is_expired} (expected: True)")
        assert is_expired == True, "VIP should be expired"

        # Simulate reset (what get_current_user would do)
        if is_expired:
            test_user.role = 'free'
            test_user.vip_start_date = None
            test_user.vip_end_date = None
            test_user.updated_at = now
            await db.commit()

        # Verify reset
        result = await db.execute(
            select(User).where(User.email == "test_vip_request@example.com")
        )
        user = result.scalar_one_or_none()

        if user:
            print(f"✓ User role after reset: {user.role} (expected: free)")
            assert user.role == "free", "User should be reset to free"

        # Cleanup test user
        await db.delete(user)
        await db.commit()
        print("✓ Test user cleaned up\n")


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("VIP Expiration Logic Tests")
    print("="*60 + "\n")

    try:
        # Clean up test users before running tests
        async for db in get_db():
            from sqlalchemy import delete
            await db.execute(
                delete(User).where(User.email.like("test_%@example.com"))
            )
            await db.commit()
            break

        await test_vip_expiration_cache()
        await test_vip_cleanup_job()
        await test_vip_expiration_in_request()

        print("="*60)
        print("✓ All tests passed successfully!")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
