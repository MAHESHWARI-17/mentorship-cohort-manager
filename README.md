# Mentorship Cohort Manager

A role-based application for managing mentorship cohorts, nominations, training plans, mentor assignments, sessions, attendance, feedback, and learner evaluations.

## Application stack

- **Frontend:** React 18, Vite, React Router, TanStack Query, and Tailwind CSS
- **Backend:** FastAPI, Python, and Motor (async MongoDB driver)
- **Database:** MongoDB
- **Deployment:** Frontend can be hosted on Vercel; API can be hosted on Render; MongoDB can be hosted on MongoDB Atlas. Local development can use a local MongoDB or Atlas.

## Roles and main workflows

- **Admin:** Manage cohorts, users, nominations, feedback templates, training plans, TalentNext courses, and cohort leadership evaluations.
- **Nominator:** Nominate trainees and mentors for permitted cohorts.
- **Mentor:** Manage assigned trainees, training progress, batches, sessions, attendance, feedback, and leadership evaluations.
- **Trainee:** Review assigned learning and progress where enabled by the application.

Person records (nominators, mentors, and trainees) require a globally unique **seven-digit employee ID** and a unique email ending in **`@mphasis.com`**. Uniqueness applies across those person types. A mentor profile and its linked login account are treated as one identity. On startup the backend normalizes legacy person records and rebuilds identity claims; see [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for details.

## Run locally without Docker

Prerequisites: Python 3.10+, Node.js 18+, npm, and a reachable MongoDB instance.

1. Configure the backend environment using `backend/.env.example` (if present) or the settings documented in `backend/app/core/config.py`. Set the MongoDB connection string, database name, and a private JWT secret. Do not commit real credentials.
2. Install and start the backend:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

3. In a second terminal, install and start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Open <http://localhost:5173>. The API is at <http://localhost:8000>; FastAPI's interactive API documentation is at <http://localhost:8000/api/docs>.

The frontend API base URL is configured through its environment settings. Point local development to the local API and production to the deployed API. Never place a server secret or MongoDB URI in frontend environment variables.

## Run with Docker Compose

See [DOCKER.md](DOCKER.md) for the Compose workflow. The Compose setup includes the frontend, API, and MongoDB services. The demo seed profile is optional and destructive to existing application data.

## Demo data

The current sample dataset is defined in `backend/seed.py`. To seed manually, configure the backend environment first, then run:

```powershell
cd backend
python seed.py
```

**Warning:** the seed script clears and recreates application collections in its configured database. Use it only with a disposable development database or after making a backup. Never point it at production or valuable Atlas data.

The dedicated demo nominator helper is `backend/create_demo_nominator.py`; its usage is described in [DOCKER.md](DOCKER.md).

## Mentor leadership evaluation

Mentors can submit or update a leadership evaluation for their assigned trainee. Admins can review the scores, attendance, written strengths and growth areas, and recommendation in the cohort's **Leadership** section. The evaluation is unique per trainee and cohort and uses five competencies, six leadership behaviors, and attendance from completed sessions.

Each rating is an integer from 1 to 5. The total is out of 100, with attendance weighted at **10%** (below the requested 15% ceiling):

```text
Competency average = sum of 5 competency ratings / 5
Competency points   = ((competency average - 1) / 4) × 60

Behavior average    = sum of 6 behavior ratings / 6
Behavior points     = ((behavior average - 1) / 4) × 30

Attendance rate     = (present sessions + late sessions) / marked completed sessions
Attendance points   = attendance rate × 10

Final score         = competency points + behavior points + attendance points
                      (maximum 100)
```

The linear 1–5 scaling makes a rating of 1 contribute zero points and a rating of 5 contribute the full weight of that category. Attendance counts `present` and `late` as attended; `absent` and `excused` are marked but not attended. Only completed sessions with attendance records contribute. If no sessions have been marked, the attendance rate and attendance points are zero. Scores are rounded to two decimal places. See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for the stored evaluation shape.

## Documentation

- [Database schema](DATABASE_SCHEMA.md)
- [Database schema diagram](DATABASE_SCHEMA_DIAGRAM.md)
- [Docker Compose guide](DOCKER.md)

## Source layout

```text
backend/   FastAPI app, MongoDB services, schemas, and seed data
frontend/  React application
docker-compose.yml
DATABASE_SCHEMA.md
DATABASE_SCHEMA_DIAGRAM.md
DOCKER.md
```
