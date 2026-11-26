"""Global identity uniqueness and canonical identity validation."""
import re
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError


def _normalize_email(value: str) -> str:
    return value.strip().casefold()


def _normalize_employee_id(value: str) -> str:
    return value.strip().casefold()


def validate_employee_id(value: str) -> str:
    value = str(value or "").strip()
    if not re.fullmatch(r"\d{7}", value):
        raise HTTPException(status_code=422, detail="Employee ID must be exactly 7 digits")
    return value


def validate_mphasis_email(value: str) -> str:
    value = str(value or "").strip().lower()
    if not value.endswith("@mphasis.com"):
        raise HTTPException(status_code=422, detail='Email must end with "@mphasis.com"')
    return value


async def repair_existing_person_identity_data(db: AsyncIOMotorDatabase) -> None:
    """Repair legacy employee IDs and email domains before rebuilding identity claims.

    Valid, unique IDs and Mphasis email local parts are retained. Invalid or
    duplicated IDs receive the next available seven-digit number; addresses keep
    their local part and move to @mphasis.com, with a numeric suffix if needed
    to preserve global email uniqueness. Linked mentor login accounts mirror
    their profile's repaired identity.
    """
    linked_mentor_user_ids = set()
    async for mentor in db.mentors.find({"userId": {"$exists": True, "$ne": None}}, {"userId": 1}):
        linked_mentor_user_ids.add(str(mentor.get("userId")))

    people = []
    for collection_name, owner_type, query in (
        ("mentors", "mentor", {}),
        ("trainees", "trainee", {}),
        ("nominators", "nominator", {}),
        ("users", "nominator", {"role": "nominator"}),
        ("users", "user", {"role": {"$in": ["mentor", "trainee"]}}),
    ):
        async for record in db[collection_name].find(query).sort("_id", 1):
            if collection_name == "users" and str(record["_id"]) in linked_mentor_user_ids:
                continue
            people.append((collection_name, owner_type, record))

    first_valid_occurrence = set()
    preserved_ids = set()
    valid_for_record = {}
    for collection_name, _, record in people:
        raw = str(record.get("employeeId") or "").strip()
        key = (collection_name, str(record["_id"]))
        if re.fullmatch(r"\d{7}", raw) and raw not in first_valid_occurrence:
            first_valid_occurrence.add(raw)
            preserved_ids.add(raw)
            valid_for_record[key] = raw

    # Admins and any other non-person account addresses still participate in
    # users.email's unique index, so reserve them while choosing new addresses.
    non_person_emails = set()
    for user in await db.users.find({"role": {"$nin": ["mentor", "trainee", "nominator"]}}, {"email": 1}).to_list(None):
        email = str(user.get("email") or "").strip().casefold()
        if email:
            non_person_emails.add(email)

    # Keep already-compliant unique Mphasis addresses stable; allocate new
    # addresses around them so old records cannot take a valid user's email.
    preserved_emails = {}
    for collection_name, _, record in people:
        email = str(record.get("email") or "").strip().lower()
        key = (collection_name, str(record["_id"]))
        normalized = email.casefold()
        if email.endswith("@mphasis.com") and normalized not in non_person_emails and normalized not in preserved_emails.values():
            preserved_emails[key] = email
    used_emails = non_person_emails | {email.casefold() for email in preserved_emails.values()}

    used_ids = set()
    next_id = 1000000
    repairs = []
    linked_user_targets = {}
    for collection_name, owner_type, record in people:
        record_id = str(record["_id"])
        employee_id = valid_for_record.get((collection_name, record_id))
        if not employee_id:
            while True:
                next_id += 1
                if next_id > 9999999:
                    raise RuntimeError("No unused seven-digit employee IDs remain")
                candidate_id = f"{next_id:07d}"
                if candidate_id not in preserved_ids and candidate_id not in used_ids:
                    employee_id = candidate_id
                    break
        used_ids.add(employee_id)

        key = (collection_name, record_id)
        candidate_email = preserved_emails.get(key)
        if not candidate_email:
            raw_email = str(record.get("email") or "").strip().lower()
            local_part = raw_email.split("@", 1)[0] if "@" in raw_email else raw_email
            local_part = re.sub(r"[^a-z0-9._-]+", ".", local_part.casefold())
            local_part = re.sub(r"\.{2,}", ".", local_part).strip("._-")
            if not local_part:
                local_part = f"employee.{employee_id}"
            candidate_email = f"{local_part}@mphasis.com"
            suffix = 2
            while candidate_email.casefold() in used_emails:
                candidate_email = f"{local_part}.{suffix}@mphasis.com"
                suffix += 1
            used_emails.add(candidate_email.casefold())

        changes = {"employeeId": employee_id, "email": candidate_email}
        if any(record.get(field) != value for field, value in changes.items()):
            repairs.append((collection_name, record["_id"], changes))
        if collection_name == "users":
            linked_user_targets[record["_id"]] = changes
        if collection_name == "mentors" and record.get("userId"):
            try:
                linked_user_id = ObjectId(str(record["userId"]))
            except Exception:
                linked_user_id = record["userId"]
            linked_user_targets[linked_user_id] = changes

    # Only stage login accounts whose email is actually changing, then set all
    # final addresses. This frees old values for safe swaps and is a no-op on
    # subsequent startups after the data has been normalized once.
    for user_id, changes in linked_user_targets.items():
        current = await db.users.find_one({"_id": user_id}, {"email": 1})
        if current and current.get("email") != changes["email"]:
            await db.users.update_one(
                {"_id": user_id},
                {"$set": {"email": f"identity-migration-{user_id}@identity.invalid"}},
            )

    for collection_name, record_id, changes in repairs:
        await db[collection_name].update_one({"_id": record_id}, {"$set": changes})
    for user_id, changes in linked_user_targets.items():
        await db.users.update_one({"_id": user_id}, {"$set": changes})


async def backfill_existing_person_identity_claims(db: AsyncIOMotorDatabase) -> None:
    """Claim existing identities once, retaining legacy records unchanged.

    Mentor login users linked to a mentor profile are not treated as a second
    person; the profile is the identity owner. Legacy collisions are left in
    place, but their first claim blocks creating another duplicate.
    """
    linked_user_ids = set()
    async for mentor in db.mentors.find({"userId": {"$exists": True, "$ne": None}}, {"userId": 1}):
        linked_user_ids.add(str(mentor.get("userId")))

    records = []
    for collection_name, owner_type, query in (
        ("mentors", "mentor", {}),
        ("trainees", "trainee", {}),
        ("nominators", "nominator", {}),
        ("users", "nominator", {"role": "nominator"}),
        ("users", "user", {"role": {"$in": ["mentor", "trainee"]}}),
    ):
        async for record in db[collection_name].find(query, {"email": 1, "employeeId": 1}):
            owner_id = str(record["_id"])
            if collection_name == "users" and owner_id in linked_user_ids:
                continue
            records.append((owner_type, owner_id, record))

    for owner_type, owner_id, record in records:
        for field, normalizer in (("email", _normalize_email), ("employeeId", _normalize_employee_id)):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            await db.personIdentityClaims.update_one(
                {"claim": f"{field}:{normalizer(value)}"},
                {"$setOnInsert": {"claim": f"{field}:{normalizer(value)}", "ownerType": owner_type, "ownerId": owner_id}},
                upsert=True,
            )


def _duplicate_error(field: str) -> HTTPException:
    if field == "email":
        detail, code = "This email is already used by another person", "EMAIL_EXISTS"
    else:
        detail, code = "This employee ID is already used by another person", "EMPLOYEE_ID_EXISTS"
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail, headers={"code": code})


async def _assert_no_conflicting_records(
    db: AsyncIOMotorDatabase,
    email_key: str,
    employee_key: str,
    ignore_owner: Optional[tuple[str, str]] = None,
) -> None:
    """Raise 409 if another person's record already uses this email / employee ID."""
    linked_mentor_user_ids = set()
    async for mentor in db.mentors.find({"userId": {"$exists": True, "$ne": None}}, {"userId": 1}):
        linked_mentor_user_ids.add(str(mentor.get("userId")))

    searches = (
        ("mentors", "mentor", "email", email_key),
        ("mentors", "mentor", "employeeId", employee_key),
        ("trainees", "trainee", "email", email_key),
        ("trainees", "trainee", "employeeId", employee_key),
        ("nominators", "nominator", "email", email_key),
        ("nominators", "nominator", "employeeId", employee_key),
        ("users", "nominator", "email", email_key),
        ("users", "nominator", "employeeId", employee_key),
        ("users", "user", "email", email_key),
        ("users", "user", "employeeId", employee_key),
        ("users", "admin", "email", email_key),
    )
    for collection_name, record_type, field, value in searches:
        if collection_name == "users" and record_type == "user":
            query = {"role": {"$in": ["mentor", "trainee"]}, field: value}
        elif collection_name == "users" and record_type == "admin":
            query = {"role": "admin", field: value}
        elif collection_name == "users":
            query = {"role": "nominator", field: value}
        else:
            query = {field: value}
        async for record in db[collection_name].find(query, {"_id": 1, "userId": 1}):
            record_id = str(record["_id"])
            if collection_name == "users" and record_id in linked_mentor_user_ids:
                continue
            if ignore_owner == (record_type, record_id):
                continue
            raise _duplicate_error(field)



async def claim_person_identity(
    db: AsyncIOMotorDatabase,
    *,
    owner_type: str,
    owner_id: str,
    email: str,
    employee_id: str,
    ignore_owner: Optional[tuple[str, str]] = None,
) -> list[str]:
    """Atomically reserve normalized email and employee ID claims.

    Existing documents are checked as a compatibility guard before the unique
    claim writes, so old databases are protected even before migration has
    populated all claims.
    """
    email = validate_mphasis_email(email)
    employee_id = validate_employee_id(employee_id)
    email_key = _normalize_email(email)
    employee_key = _normalize_employee_id(employee_id)
    if not email_key or not employee_key:
        raise HTTPException(status_code=422, detail="Email and employee ID are required")

    await backfill_existing_person_identity_claims(db)
    await _assert_no_conflicting_records(db, email_key, employee_key, ignore_owner)

    claims = [f"email:{email_key}", f"employeeId:{employee_key}"]
    inserted = []
    try:
        for claim in claims:
            await db.personIdentityClaims.insert_one({
                "claim": claim,
                "ownerType": owner_type,
                "ownerId": str(owner_id),
            })
            inserted.append(claim)
    except DuplicateKeyError as exc:
        if inserted:
            await db.personIdentityClaims.delete_many({"claim": {"$in": inserted}, "ownerId": str(owner_id)})
        duplicate_claim = (exc.details or {}).get("keyValue", {}).get("claim", "")
        if not duplicate_claim:
            for claim in claims:
                if await db.personIdentityClaims.find_one({"claim": claim}, {"_id": 1}):
                    duplicate_claim = claim
                    break
        field = "employeeId" if duplicate_claim.startswith("employeeId:") else "email"
        raise _duplicate_error(field)
    except Exception:
        if inserted:
            await db.personIdentityClaims.delete_many({"claim": {"$in": inserted}, "ownerId": str(owner_id)})
        raise
    return claims


async def release_person_identity(db: AsyncIOMotorDatabase, owner_id: str) -> None:
    await db.personIdentityClaims.delete_many({"ownerId": str(owner_id)})


async def update_person_identity(
    db: AsyncIOMotorDatabase,
    *,
    owner_type: str,
    owner_id: str,
    email: str,
    employee_id: str,
) -> dict:
    """Move an existing person's email / employee ID claims to new values.

    New claims are reserved atomically (unique index) before anything else
    changes. Claims this person already holds are kept as-is, so editing only
    one of the two values works. Returns {"added": [...], "stale": [...]}:
    the caller rolls back `added` if the profile update fails, and releases
    `stale` (the old values) once it succeeds.
    """
    email = validate_mphasis_email(email)
    employee_id = validate_employee_id(employee_id)
    email_key = _normalize_email(email)
    employee_key = _normalize_employee_id(employee_id)
    if not email_key or not employee_key:
        raise HTTPException(status_code=422, detail="Email and employee ID are required")

    await backfill_existing_person_identity_claims(db)
    await _assert_no_conflicting_records(db, email_key, employee_key, (owner_type, str(owner_id)))

    wanted = [f"email:{email_key}", f"employeeId:{employee_key}"]
    held = {
        row["claim"]
        async for row in db.personIdentityClaims.find({"ownerId": str(owner_id)}, {"claim": 1})
    }
    added = []
    try:
        for claim in wanted:
            if claim in held:
                continue
            await db.personIdentityClaims.insert_one({
                "claim": claim, "ownerType": owner_type, "ownerId": str(owner_id),
            })
            added.append(claim)
    except DuplicateKeyError:
        if added:
            await db.personIdentityClaims.delete_many({"claim": {"$in": added}, "ownerId": str(owner_id)})
        raise _duplicate_error("employeeId" if claim.startswith("employeeId:") else "email")
    except Exception:
        if added:
            await db.personIdentityClaims.delete_many({"claim": {"$in": added}, "ownerId": str(owner_id)})
        raise
    return {"added": added, "stale": sorted(held - set(wanted))}


async def rollback_identity_update(db: AsyncIOMotorDatabase, owner_id: str, added: list) -> None:
    if added:
        await db.personIdentityClaims.delete_many({"claim": {"$in": added}, "ownerId": str(owner_id)})


async def release_stale_identity_claims(db: AsyncIOMotorDatabase, owner_id: str, stale: list) -> None:
    if stale:
        await db.personIdentityClaims.delete_many({"claim": {"$in": stale}, "ownerId": str(owner_id)})
