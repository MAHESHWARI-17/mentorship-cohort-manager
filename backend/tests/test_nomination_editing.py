"""Editing nominee details: nominator (own records only) and admin (any record)."""
import pytest
from bson import ObjectId

from app.core.security import create_access_token, get_password_hash

MENTOR = {"name": "Maya Mentor", "email": "maya@example.com", "employeeId": "EMP-M1",
          "location": "Pune, India", "timezone": "Asia/Kolkata"}
TRAINEE = {"name": "Tom Trainee", "email": "tom@example.com", "employeeId": "EMP-T1",
           "location": "Pune, India", "timezone": "Asia/Kolkata"}


@pytest.fixture(autouse=True)
async def clean_identity_state(test_db):
    # Identity claims and cohorts persist between tests unless cleared here.
    for name in ("personIdentityClaims", "cohorts"):
        await test_db[name].delete_many({})


@pytest.fixture
async def other_nominator_headers(test_db):
    res = await test_db.users.insert_one({
        "name": "Other Nominator", "email": "other.nominator@test.com",
        "passwordHash": get_password_hash("Nom@123"), "role": "nominator", "isActive": True,
    })
    return {"Authorization": f"Bearer {create_access_token(subject=str(res.inserted_id), role='nominator')}"}


async def _nominate(client, headers, kind, payload):
    res = await client.post(f"/api/nominations/{kind}s", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["id"]


async def _mine(client, headers, kind):
    res = await client.get(f"/api/nominations/mine/{kind}s", headers=headers)
    assert res.status_code == 200
    return res.json()


# ---- nominator ------------------------------------------------------------

@pytest.mark.asyncio
async def test_nominator_edits_trainee_name(client, nominator_headers, test_db):
    tid = await _nominate(client, nominator_headers, "trainee", TRAINEE)
    before = await test_db.trainees.find_one({"_id": ObjectId(tid)})

    res = await client.put(f"/api/nominations/mine/trainees/{tid}", json={"name": "Thomas Trainee"}, headers=nominator_headers)
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Thomas Trainee"

    listing = await _mine(client, nominator_headers, "trainee")
    assert listing["total"] == 1                       # no duplicate nomination
    assert listing["items"][0]["name"] == "Thomas Trainee"
    after = await test_db.trainees.find_one({"_id": ObjectId(tid)})
    assert after["nominatedBy"] == before["nominatedBy"] and after["createdAt"] == before["createdAt"]
    assert after["email"] == before["email"] and after["employeeId"] == before["employeeId"]


@pytest.mark.asyncio
async def test_nominator_edits_trainee_email_and_employee_id(client, nominator_headers):
    tid = await _nominate(client, nominator_headers, "trainee", TRAINEE)
    res = await client.put(f"/api/nominations/mine/trainees/{tid}", json={
        "email": "Tom.New@Example.com", "employeeId": "EMP-T99",
    }, headers=nominator_headers)
    assert res.status_code == 200, res.text
    item = (await _mine(client, nominator_headers, "trainee"))["items"][0]
    assert item["email"] == "tom.new@example.com" and item["employeeId"] == "EMP-T99"

    # old identity is released, new identity is protected
    again_old = await client.post("/api/nominations/trainees", json=TRAINEE, headers=nominator_headers)
    assert again_old.status_code == 200
    dup_new = await client.post("/api/nominations/trainees", json={
        **TRAINEE, "email": "tom.new@example.com", "employeeId": "EMP-OTHER"}, headers=nominator_headers)
    assert dup_new.status_code == 409


@pytest.mark.asyncio
async def test_nominator_edits_mentor(client, nominator_headers):
    mid = await _nominate(client, nominator_headers, "mentor", MENTOR)
    res = await client.put(f"/api/nominations/mine/mentors/{mid}", json={
        "name": "Maya M.", "employeeId": "EMP-M2", "location": "Boston, USA", "timezone": "America/New_York",
    }, headers=nominator_headers)
    assert res.status_code == 200, res.text
    listing = await _mine(client, nominator_headers, "mentor")
    assert listing["total"] == 1
    item = listing["items"][0]
    assert (item["name"], item["employeeId"], item["location"], item["timezone"]) == (
        "Maya M.", "EMP-M2", "Boston, USA", "America/New_York")


@pytest.mark.asyncio
async def test_nominator_cannot_edit_another_nominators_record(
    client, nominator_headers, other_nominator_headers, test_db
):
    tid = await _nominate(client, nominator_headers, "trainee", TRAINEE)
    mid = await _nominate(client, nominator_headers, "mentor", MENTOR)

    res_t = await client.put(f"/api/nominations/mine/trainees/{tid}", json={"name": "Hacked"}, headers=other_nominator_headers)
    res_m = await client.put(f"/api/nominations/mine/mentors/{mid}", json={"name": "Hacked"}, headers=other_nominator_headers)
    assert res_t.status_code == 404 and res_m.status_code == 404
    assert (await test_db.trainees.find_one({"_id": ObjectId(tid)}))["name"] == TRAINEE["name"]
    assert (await test_db.mentors.find_one({"_id": ObjectId(mid)}))["name"] == MENTOR["name"]


@pytest.mark.asyncio
async def test_unauthorized_requests_rejected(client, nominator_headers, mentor_headers, test_db):
    tid = await _nominate(client, nominator_headers, "trainee", TRAINEE)
    for url in (f"/api/nominations/mine/trainees/{tid}", f"/api/nominations/trainees/{tid}"):
        assert (await client.put(url, json={"name": "X"})).status_code == 401
        assert (await client.put(url, json={"name": "X"}, headers=mentor_headers)).status_code == 403
    # a nominator cannot use the admin endpoint to reach any record
    res = await client.put(f"/api/nominations/trainees/{tid}", json={"name": "X"}, headers=nominator_headers)
    assert res.status_code == 403
    assert (await test_db.trainees.find_one({"_id": ObjectId(tid)}))["name"] == TRAINEE["name"]


@pytest.mark.asyncio
async def test_system_fields_cannot_be_changed_through_the_request(client, nominator_headers, test_db):
    tid = await _nominate(client, nominator_headers, "trainee", TRAINEE)
    before = await test_db.trainees.find_one({"_id": ObjectId(tid)})
    res = await client.put(f"/api/nominations/mine/trainees/{tid}", json={
        "name": "Renamed", "nominatedBy": "someone-else", "cohortId": "abc", "mentorId": "m", "status": "approved",
        "createdAt": "2000-01-01T00:00:00", "_id": str(ObjectId()),
    }, headers=nominator_headers)
    assert res.status_code == 200
    after = await test_db.trainees.find_one({"_id": ObjectId(tid)})
    for field in ("nominatedBy", "cohortId", "mentorId", "createdAt"):
        assert after.get(field) == before.get(field)
    assert after.get("status") == before.get("status")


@pytest.mark.asyncio
async def test_edit_conflicting_with_another_person_is_rejected(client, nominator_headers, test_db):
    tid = await _nominate(client, nominator_headers, "trainee", TRAINEE)
    await _nominate(client, nominator_headers, "trainee", {**TRAINEE, "name": "Uma", "email": "uma@example.com", "employeeId": "EMP-U1"})
    res = await client.put(f"/api/nominations/mine/trainees/{tid}", json={"email": "uma@example.com"}, headers=nominator_headers)
    assert res.status_code == 409 and res.json()["code"] == "EMAIL_EXISTS"
    res = await client.put(f"/api/nominations/mine/trainees/{tid}", json={"employeeId": "EMP-U1"}, headers=nominator_headers)
    assert res.status_code == 409 and res.json()["code"] == "EMPLOYEE_ID_EXISTS"
    doc = await test_db.trainees.find_one({"_id": ObjectId(tid)})
    assert doc["email"] == TRAINEE["email"] and doc["employeeId"] == TRAINEE["employeeId"]
    # the original identity is still claimed after the failed edits
    dup = await client.post("/api/nominations/trainees", json={**TRAINEE, "employeeId": "EMP-FRESH"}, headers=nominator_headers)
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_trainee_location_and_timezone_cannot_be_blanked(client, nominator_headers):
    tid = await _nominate(client, nominator_headers, "trainee", TRAINEE)
    res = await client.put(f"/api/nominations/mine/trainees/{tid}", json={"location": ""}, headers=nominator_headers)
    assert res.status_code == 422
    res = await client.put(f"/api/nominations/mine/trainees/{tid}", json={"name": "  "}, headers=nominator_headers)
    assert res.status_code == 422


# ---- admin ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_edits_trainee_and_mentor_from_any_nominator(client, nominator_headers, admin_headers):
    tid = await _nominate(client, nominator_headers, "trainee", TRAINEE)
    mid = await _nominate(client, nominator_headers, "mentor", MENTOR)

    rt = await client.put(f"/api/nominations/trainees/{tid}", json={"name": "Tom Fixed", "employeeId": "EMP-T7"}, headers=admin_headers)
    rm = await client.put(f"/api/nominations/mentors/{mid}", json={"email": "maya.fixed@example.com"}, headers=admin_headers)
    assert rt.status_code == 200 and rm.status_code == 200, (rt.text, rm.text)

    trainees = (await client.get("/api/nominations/trainees", headers=admin_headers)).json()
    mentors = (await client.get("/api/nominations/mentors", headers=admin_headers)).json()
    assert trainees["total"] == 1 and mentors["total"] == 1       # no duplicates
    assert (trainees["items"][0]["name"], trainees["items"][0]["employeeId"]) == ("Tom Fixed", "EMP-T7")
    assert mentors["items"][0]["email"] == "maya.fixed@example.com"
    assert trainees["items"][0]["nominatorName"] == "Test Nominator"   # original nominator preserved

    # the nominator sees the admin's correction too
    assert (await _mine(client, nominator_headers, "trainee"))["items"][0]["name"] == "Tom Fixed"
    assert (await client.put(f"/api/nominations/trainees/{ObjectId()}", json={"name": "x"}, headers=admin_headers)).status_code == 404


@pytest.mark.asyncio
async def test_editing_allocated_nominees_keeps_cohort_mentor_and_workflow(client, nominator_headers, admin_headers, test_db):
    mid = await _nominate(client, nominator_headers, "mentor", MENTOR)
    tid = await _nominate(client, nominator_headers, "trainee", TRAINEE)
    cohort = await client.post("/api/cohorts", json={"name": "C1", "startDate": "2026-05-01", "endDate": "2026-05-31"}, headers=admin_headers)
    cohort_id = cohort.json()["id"]
    await client.post(f"/api/cohorts/{cohort_id}/mentors/allocate", json={"ids": [mid]}, headers=admin_headers)
    await client.post(f"/api/cohorts/{cohort_id}/trainees/allocate", json={"ids": [tid]}, headers=admin_headers)
    assert (await client.put(f"/api/trainees/{tid}/mentor", json={"mentorId": mid}, headers=admin_headers)).status_code == 200

    t_before = await test_db.trainees.find_one({"_id": ObjectId(tid)})
    m_before = await test_db.mentors.find_one({"_id": ObjectId(mid)})

    assert (await client.put(f"/api/nominations/trainees/{tid}", json={"name": "Tom Allocated"}, headers=admin_headers)).status_code == 200
    assert (await client.put(f"/api/nominations/mine/mentors/{mid}", json={"name": "Maya Allocated"}, headers=nominator_headers)).status_code == 200

    t_after = await test_db.trainees.find_one({"_id": ObjectId(tid)})
    m_after = await test_db.mentors.find_one({"_id": ObjectId(mid)})
    for field in ("cohortId", "mentorId", "cohortAssignmentHistory", "status"):
        assert t_after.get(field) == t_before.get(field)
    for field in ("cohortId", "cohortIds", "cohortAssignmentHistory", "isActive"):
        assert m_after.get(field) == m_before.get(field)
    assert await test_db.trainees.count_documents({}) == 1 and await test_db.mentors.count_documents({}) == 1

    # existing workflows still work after an edit: cohort listing, re-assignment, reallocation skip
    members = await client.get(f"/api/cohorts/{cohort_id}/trainees", headers=admin_headers)
    assert members.json()["total"] == 1 and members.json()["items"][0]["name"] == "Tom Allocated"
    again = await client.post(f"/api/cohorts/{cohort_id}/trainees/allocate", json={"ids": [tid]}, headers=admin_headers)
    assert again.json()["allocated"] == 0
    assert (await client.put(f"/api/nominations/trainees/{tid}/cohort", json={"cohortId": None}, headers=admin_headers)).status_code == 200


@pytest.mark.asyncio
async def test_mentor_with_active_login_keeps_login_in_sync(client, nominator_headers, admin_headers, test_db):
    mid = await _nominate(client, nominator_headers, "mentor", MENTOR)
    user = await test_db.users.insert_one({
        "name": MENTOR["name"], "email": MENTOR["email"], "role": "mentor", "isActive": True,
        "passwordHash": get_password_hash("Mentor@123"),
    })
    await test_db.mentors.update_one({"_id": ObjectId(mid)}, {"$set": {"userId": str(user.inserted_id)}})

    res = await client.put(f"/api/nominations/mentors/{mid}", json={"name": "Maya Renamed", "email": "maya.renamed@example.com"}, headers=admin_headers)
    assert res.status_code == 200, res.text
    login = await test_db.users.find_one({"_id": user.inserted_id})
    assert (login["name"], login["email"]) == ("Maya Renamed", "maya.renamed@example.com")
    assert (await test_db.mentors.find_one({"_id": ObjectId(mid)}))["userId"] == str(user.inserted_id)


# ---- creation unchanged -----------------------------------------------------

@pytest.mark.asyncio
async def test_creation_and_duplicate_rules_unchanged(client, nominator_headers):
    await _nominate(client, nominator_headers, "trainee", TRAINEE)
    dup = await client.post("/api/nominations/trainees", json=TRAINEE, headers=nominator_headers)
    assert dup.status_code == 409
    await _nominate(client, nominator_headers, "mentor", MENTOR)
    assert (await _mine(client, nominator_headers, "mentor"))["total"] == 1
