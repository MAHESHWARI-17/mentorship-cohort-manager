"""Create or refresh the demo nominator account without resetting the database."""
import asyncio
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core.security import get_password_hash
from app.services.identity_service import claim_person_identity, update_person_identity


async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    try:
        db = client[settings.DATABASE_NAME]
        email = "demo.nominator@mphasis.com"
        employee_id = "9000001"
        existing = await db.users.find_one({"email": email})
        if not existing:
            existing = await db.users.find_one({"role": "nominator", "name": "Demo Nominator"})
        user_id = existing["_id"] if existing else ObjectId()
        if existing:
            await update_person_identity(
                db, owner_type="nominator", owner_id=str(user_id),
                email=email, employee_id=employee_id,
            )
        else:
            await claim_person_identity(
                db, owner_type="nominator", owner_id=str(user_id),
                email=email, employee_id=employee_id,
            )
        result = await db.users.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "name": "Demo Nominator",
                    "email": email,
                    "employeeId": employee_id,
                    "passwordHash": get_password_hash("Nominator@123"),
                    "role": "nominator",
                    "isActive": True,
                    "firstLoginPasswordReset": False,
                },
                "$setOnInsert": {"createdAt": datetime.now(timezone.utc)},
            },
            upsert=True,
        )
        action = "Created" if result.upserted_id else "Updated"
        print(f"{action} demo login: {email} / Nominator@123")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
