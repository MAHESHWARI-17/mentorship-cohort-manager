from datetime import datetime, timezone

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.deps import ensure_mentor_cohort_access
from app.schemas.evaluation import MentorEvaluationRequest


COMPETENCIES = {
    "problemDiscovery": "Problem Discovery",
    "ownership": "Ownership",
    "solutionQuality": "Solution Quality",
    "communication": "Communication",
    "leadershipDefense": "Leadership Defense",
}

BEHAVIORS = {
    "customerObsession": "Customer Obsession",
    "biasForAction": "Bias for Action",
    "ownership": "Ownership",
    "systemsThinking": "Systems Thinking",
    "learningAgility": "Learning Agility",
    "executivePresence": "Executive Presence",
}


class EvaluationService:
    @staticmethod
    async def _attendance_for_trainee(db: AsyncIOMotorDatabase, trainee: dict, cohort_id: str) -> dict:
        trainee_id = str(trainee["_id"])
        trainee_refs = [trainee_id, trainee["_id"]]
        cohort_refs = [cohort_id]
        try:
            cohort_refs.append(ObjectId(cohort_id))
        except Exception:
            pass
        batches = await db.batches.find({
            "cohortId": {"$in": cohort_refs},
            "traineeIds": {"$in": trainee_refs},
        }, {"_id": 1}).to_list(None)
        batch_ids = [batch["_id"] for batch in batches]
        sessions = await db.sessions.find({
            "batchId": {"$in": batch_ids},
            "status": "completed",
        }, {"attendance": 1, "roster": 1}).to_list(None) if batch_ids else []

        counts = {"present": 0, "late": 0, "absent": 0, "excused": 0}
        for session in sessions:
            roster = session.get("roster")
            if roster and not any(str(member.get("traineeId")) == trainee_id for member in roster):
                continue
            record = next((row for row in session.get("attendance", [])
                           if str(row.get("traineeId")) == trainee_id), None)
            if record and record.get("status") in counts:
                counts[record["status"]] += 1
        marked = sum(counts.values())
        attended = counts["present"] + counts["late"]
        rate = round(attended / marked * 100, 2) if marked else 0.0
        return {"sessionsMarked": marked, "sessionsAttended": attended, "attendanceRate": rate, **counts}

    @staticmethod
    async def submit(db: AsyncIOMotorDatabase, trainee_id: str, cohort_id: str | None,
                     request: MentorEvaluationRequest, user: dict) -> dict:
        try:
            trainee = await db.trainees.find_one({"_id": ObjectId(trainee_id)})
        except Exception:
            trainee = None
        if not trainee:
            raise HTTPException(status_code=404, detail="Trainee not found")
        if trainee.get("status") == "dropped_out":
            raise HTTPException(status_code=400, detail="An evaluation cannot be submitted for a trainee who has dropped out")

        actual_cohort_id = str(trainee.get("cohortId", ""))
        if cohort_id and str(cohort_id) != actual_cohort_id:
            raise HTTPException(status_code=403, detail="Trainee does not belong to the selected cohort")
        try:
            mentor = await db.mentors.find_one({"_id": ObjectId(str(trainee.get("mentorId")))})
        except Exception:
            mentor = None
        if not mentor or str(mentor.get("userId")) != str(user["id"]):
            raise HTTPException(status_code=403, detail="Only the trainee's assigned mentor can submit this evaluation")
        await ensure_mentor_cohort_access(db, user, actual_cohort_id)

        if set(request.competencyScores) != set(COMPETENCIES):
            raise HTTPException(status_code=422, detail="All five competency ratings are required")
        if set(request.behaviorScores) != set(BEHAVIORS):
            raise HTTPException(status_code=422, detail="All six behavior ratings are required")
        for score in [*request.competencyScores.values(), *request.behaviorScores.values()]:
            if isinstance(score, bool) or not isinstance(score, int) or score < 1 or score > 5:
                raise HTTPException(status_code=422, detail="Ratings must be whole numbers from 1 to 5")
        if not request.strengths.strip() or not request.growthAreas.strip():
            raise HTTPException(status_code=422, detail="Strengths and growth areas are required")

        cohort = await db.cohorts.find_one({"_id": ObjectId(actual_cohort_id)})
        attendance = await EvaluationService._attendance_for_trainee(db, trainee, actual_cohort_id)
        now = datetime.now(timezone.utc)
        key = {"traineeId": trainee_id, "cohortId": actual_cohort_id}
        previous = await db.mentorEvaluations.find_one(key)
        competency_average = round(sum(request.competencyScores.values()) / len(COMPETENCIES), 2)
        behavior_average = round(sum(request.behaviorScores.values()) / len(BEHAVIORS), 2)
        competency_points = round(((competency_average - 1) / 4) * 60, 2)
        behavior_points = round(((behavior_average - 1) / 4) * 30, 2)
        attendance_points = round(attendance["attendanceRate"] * 0.1, 2)
        document = {
            **key,
            "mentorId": str(mentor["_id"]),
            "mentorUserId": str(user["id"]),
            "mentorName": mentor.get("name") or user.get("name"),
            "mentorEmail": mentor.get("email") or user.get("email"),
            "traineeName": trainee.get("name"),
            "traineeEmployeeId": trainee.get("employeeId"),
            "cohortName": cohort.get("name") if cohort else None,
            "competencyScores": request.competencyScores,
            "behaviorScores": request.behaviorScores,
            "strengths": request.strengths.strip(),
            "growthAreas": request.growthAreas.strip(),
            "recommendation": request.recommendation,
            "competencyAverage": competency_average,
            "behaviorAverage": behavior_average,
            "attendance": attendance,
            "scoreSummary": {
                "competencyPoints": competency_points,
                "behaviorPoints": behavior_points,
                "attendancePoints": attendance_points,
                "totalScore": round(competency_points + behavior_points + attendance_points, 2),
                "maxScore": 100,
            },
            "submittedAt": now,
            "updatedAt": now,
            "createdAt": previous.get("createdAt", now) if previous else now,
        }
        await db.mentorEvaluations.update_one(key, {"$set": document}, upsert=True)
        saved = await db.mentorEvaluations.find_one(key)
        saved["id"] = str(saved.pop("_id"))
        return saved

    @staticmethod
    async def get_for_trainee(db: AsyncIOMotorDatabase, trainee_id: str, cohort_id: str) -> dict | None:
        evaluation = await db.mentorEvaluations.find_one({"traineeId": trainee_id, "cohortId": cohort_id})
        if not evaluation:
            return None
        evaluation["id"] = str(evaluation.pop("_id"))
        return evaluation
