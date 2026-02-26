"""Seed database with initial data"""
import asyncio
import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from core.database import Base
from core.config import settings
from models import Asset


async def seed_assets():
    """Seed assets - now assets are obtained dynamically via payout"""
    # Assets are now populated dynamically by the data collector service
    # This script is kept for compatibility but no longer populates assets
    print("Assets are now obtained dynamically via payout from monitoring accounts")
    print("Start the data collector service to populate assets automatically")


async def seed_monitoring_accounts():
    """Seed monitoring accounts from files"""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from pathlib import Path
    from models import MonitoringAccount, MonitoringAccountType
    from sqlalchemy import select

    async with async_session() as session:
        # Check if accounts already exist
        existing_payout = await session.execute(
            select(MonitoringAccount).where(
                MonitoringAccount.account_type == MonitoringAccountType.PAYOUT
            )
        )
        existing_ativos = await session.execute(
            select(MonitoringAccount).where(
                MonitoringAccount.account_type == MonitoringAccountType.ATIVOS
            )
        )
        
        has_payout = existing_payout.first() is not None
        has_ativos = existing_ativos.first() is not None
        
        if has_payout and has_ativos:
            print("Monitoring accounts already exist, skipping creation")
            return
        
        # Load payout SSID (path is relative to backend folder, so go up one level)
        payout_path = Path("../accountsformonitorinig/payout/accountforpayout.txt.txt")
        if payout_path.exists():
            with open(payout_path, 'r') as f:
                payout_ssid = f.read().strip()

            if payout_ssid and not has_payout:
                payout_account = MonitoringAccount(
                    ssid=payout_ssid,
                    account_type=MonitoringAccountType.PAYOUT,
                    name="Payout Monitor",
                    is_active=True
                )
                session.add(payout_account)
                print("Payout monitoring account seeded")
            elif has_payout:
                print("Payout account already exists, skipping")
        else:
            print(f"Payout SSID file not found: {payout_path.absolute()}")

        # Load ativos SSID (path is relative to backend folder, so go up one level)
        ativos_path = Path("../accountsformonitorinig/actives/accountsforactives.txt.txt")
        if ativos_path.exists():
            with open(ativos_path, 'r') as f:
                ativos_ssid = f.read().strip()

            if ativos_ssid and not has_ativos:
                ativos_account = MonitoringAccount(
                    ssid=ativos_ssid,
                    account_type=MonitoringAccountType.ATIVOS,
                    name="Ativos Monitor",
                    is_active=True
                )
                session.add(ativos_account)
                print("Ativos monitoring account seeded")
            elif has_ativos:
                print("Ativos account already exists, skipping")
        else:
            print(f"Ativos SSID file not found: {ativos_path.absolute()}")

        await session.commit()
        print("Monitoring accounts seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_monitoring_accounts())
