"""Background job to clean up expired VIP users"""
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger


async def cleanup_expired_vip_users(db: AsyncSession) -> int:
    """
    Clean up expired VIP users in batch.
    
    This job should run periodically (e.g., every hour) to reset VIP status
    for users whose VIP has expired. This reduces the load on individual requests.

    Args:
        db: Database session

    Returns:
        int: Number of users updated
    """
    from models import User

    now = datetime.utcnow()

    # Find all expired VIP users
    result = await db.execute(
        select(User).where(
            User.role.in_(['vip', 'vip_plus']),
            User.vip_end_date < now
        )
    )
    expired_users = result.scalars().all()

    if not expired_users:
        return 0

    # Update all expired users
    updated_count = 0
    for user in expired_users:
        user.role = 'free'
        user.vip_start_date = None
        user.vip_end_date = None
        user.updated_at = now
        updated_count += 1

    await db.commit()

    logger.info(f"Cleanup: Reset {updated_count} expired VIP users to 'free'")

    return updated_count
