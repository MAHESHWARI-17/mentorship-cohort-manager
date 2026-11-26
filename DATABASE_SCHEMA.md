# Cohort Manager — Current MongoDB Schema

This document describes the application data model from the backend source. MongoDB is schemaless; these are the document shapes used by the application, not MongoDB-enforced validators. No demo or seed records are included here.

## Database

- Default database: `cohort_manager` (`DATABASE_NAME` can override it).
- Documents use MongoDB `_id` values, generally `ObjectId`.
- Some references are represented as strings and some as `ObjectId` values for compatibility with existing API paths.
- Passwords are stored as bcrypt hashes. Attendance is embedded in session documents.
- Mentor, trainee, and nominator records require a unique seven-digit employee ID and an email ending in `@mphasis.com`. Email and employee ID uniqueness is enforced globally through `personIdentityClaims`; values are normalized before comparison. A mentor profile and its linked login account represent the same person and do not conflict. Legacy records are normalized during backend startup.

## Collections

### `users`

Login identities for administrators, mentors, and nominators.

```js
{
  _id: ObjectId,
  name: String,
  email: String,                   // unique among accounts; person claim is global for people
  passwordHash: String,
  role: "admin" | "mentor" | "nominator",
  isActive: Boolean,
  employeeId: String?,             // required for people; exactly 7 digits and globally unique
  firstLoginPasswordReset: Boolean?,
  temporaryPassword: String?,      // transitional setup field
  createdAt: Date?, updatedAt: Date?, lastLoginAt: Date?
}
```

### `personIdentityClaims`

One document per normalized email or employee ID. The unique `claim` index prevents simultaneous creation of the same identity in different person collections.

```js
{
  _id: ObjectId,
  claim: "email:person@mphasis.com" | "employeeId:1234567", // unique, normalized
  ownerType: "mentor" | "trainee" | "nominator" | "user",
  ownerId: String
}
```

Existing identities are backfilled at application startup and checked again before person creation. Existing duplicate records are preserved; their first claim prevents adding another duplicate.

### `cohorts`

```js
{
  _id: ObjectId,
  name: String,
  description: String?,
  startDate: String,
  endDate: String,
  status: "draft" | "active" | "closed",
  trainingPlanId: String?,
  feedbackFormId: String?,
  talentnextCourses: [{ courseId: String, isMandatory: Boolean }],
  createdBy: String,
  createdAt: Date
}
```

### `mentors`

```js
{
  _id: ObjectId,
  cohortId: String | null,   // legacy/primary cohort reference kept for compatibility
  cohortIds: [String],       // all cohort memberships; empty = not assigned
  cohortAccess: { [cohortId: string]: Boolean }, // per-cohort access; missing means enabled
  cohortAssignmentHistory: [{ action: String?, fromCohortId: String?, toCohortId: String?, cohortId: String?, cohortIds: [String]?, at: Date }],
  cohortAccessHistory: [{ cohortId: String, isActive: Boolean, at: Date }],
  isActive: Boolean,         // global account status, separate from cohortAccess
  nominatedBy: String?,
  userId: String?,                 // linked login in users
  name: String,
  email: String,
  employeeId: String,              // globally unique person claim
  department: String?,
  location: String?,
  timezone: String?,
  experience: String?,
  skills: [String]?,
  status: String?,
  createdAt: Date?, approvedAt: Date?
}
```

### `trainees`

```js
{
  _id: ObjectId,
  cohortId: String | null,   // null = nominated but not yet added to a cohort
  cohortAssignmentHistory: [{ fromCohortId: String?, toCohortId: String?, at: Date }],
  nominatedBy: String?,
  mentorId: ObjectId | String?,   // assigned mentor profile
  name: String,
  email: String,
  employeeId: String,              // globally unique person claim
  department: String?,
  location: String?,
  timezone: String?,
  experience: String?,
  skills: [String]?,
  status: String?,                // includes "dropped_out"
  droppedOutAt: Date?,
  droppedOutBy: String?,
  dropoutReason: String?,
  createdAt: Date?, approvedAt: Date?
}
```

Dropped-out trainees remain stored so cohort and attendance history can be reported.

### `trainingTemplates` and `cohortTrainingPlans`

`trainingTemplates` are reusable training plans. `cohortTrainingPlans` stores the cohort-specific plan copy.

```js
{
  _id: ObjectId,
  cohortId: ObjectId | String?,   // present on cohort plan copies
  name: String,
  totalWeeks: Number,
  coreWeeks: Number?,             // cohort plan copy
  bufferWeeks: Number?,           // cohort plan copy
  weeks: [{
    weekNumber: Number,
    title: String,
    isBuffer: Boolean?,
    courses: [{
      courseId: String?,
      title: String,
      description: String?,
      durationHrs: Number?
    }]
  }],
  talentnextCourses: [{
    courseId: String,              // references talentnextCourses._id
    isMandatory: Boolean
  }],
  createdAt: Date
}
```

TalentNext assignments configured on a reusable template are copied into the cohort plan and cohort when that template is applied. The cohort copy can subsequently be managed independently.

### `feedbackTemplates` and `cohortFeedbackForms`

Reusable feedback templates and their cohort-specific copies.

```js
{
  _id: ObjectId,
  cohortId: ObjectId | String?,   // present on cohort form copies
  name: String,
  fields: [{
    key: String,
    label: String,
    type: "rating" | "text" | "select",
    options: [String]?,
    required: Boolean
  }],
  createdAt: Date
}
```

### `progress`

```js
{
  _id: ObjectId,
  cohortId: ObjectId | String,
  traineeId: ObjectId | String,   // unique per trainee
  mentorId: ObjectId | String?,
  planId: ObjectId | String?,
  items: [{
    weekNumber: Number,
    courseId: String?,
    title: String?,
    completed: Boolean,
    completedAt: Date?,
    completedBy: String?
  }],
  percentComplete: Number?,
  createdAt: Date?, updatedAt: Date?
}
```

### `feedbackResponses`

```js
{
  _id: ObjectId,
  cohortId: ObjectId | String,
  traineeId: ObjectId | String,
  mentorId: ObjectId | String?,
  formId: ObjectId | String?,
  weekNumber: Number,
  answers: Object,
  submittedAt: Date?
}
```

There is a unique index on `(traineeId, weekNumber)`.

### `mentorEvaluations`

One leadership evaluation per trainee and cohort. A mentor may update their existing evaluation. The backend permits only the trainee's assigned mentor to submit it; admins can read evaluations for their cohorts.

```js
{
  _id: ObjectId,
  traineeId: String,
  cohortId: String,
  mentorId: String,
  mentorUserId: String,
  mentorName: String?,
  mentorEmail: String?,
  traineeName: String?,
  traineeEmployeeId: String?,
  cohortName: String?,
  competencyScores: {                 // exactly five ratings, each integer 1–5
    problemDiscovery: Number,
    ownership: Number,
    solutionQuality: Number,
    communication: Number,
    leadershipDefense: Number
  },
  behaviorScores: {                   // exactly six ratings, each integer 1–5
    customerObsession: Number,
    biasForAction: Number,
    ownership: Number,
    systemsThinking: Number,
    learningAgility: Number,
    executivePresence: Number
  },
  strengths: String,
  growthAreas: String,
  recommendation: "ready_now" | "ready_with_coaching" | "not_yet_ready",
  competencyAverage: Number,
  behaviorAverage: Number,
  attendance: {
    sessionsMarked: Number,
    sessionsAttended: Number,         // present + late
    attendanceRate: Number,           // percentage, 0–100
    present: Number,
    late: Number,
    absent: Number,
    excused: Number
  },
  scoreSummary: {
    competencyPoints: Number,         // maximum 60
    behaviorPoints: Number,           // maximum 30
    attendancePoints: Number,         // maximum 10
    totalScore: Number,               // maximum 100
    maxScore: 100
  },
  submittedAt: Date,
  createdAt: Date,
  updatedAt: Date
}
```

The unique index on `(traineeId, cohortId)` prevents duplicate evaluations. The score is calculated as:

```text
competencyAverage = sum of the five competency ratings / 5
competencyPoints  = ((competencyAverage - 1) / 4) × 60

behaviorAverage   = sum of the six behavior ratings / 6
behaviorPoints    = ((behaviorAverage - 1) / 4) × 30

attendanceRate    = (present + late) / sessionsMarked
attendancePoints  = attendanceRate × 10

totalScore        = competencyPoints + behaviorPoints + attendancePoints
```

Attendance contributes 10% of the total (below the 15% ceiling). Only completed sessions with recorded attendance are counted. An unmarked session does not enter the denominator; if no attendance has been marked, attendance contributes zero. `present` and `late` count as attended; `absent` and `excused` do not. Each rating is 1–5, linearly mapped so that 1 is zero points and 5 is the category maximum. Values are rounded to two decimal places.

### `talentnextCourses` and `talentnextProgress`

```js
// talentnextCourses
{ _id: ObjectId, name: String, createdAt: Date? }

// talentnextProgress
{
  _id: ObjectId,
  cohortId: ObjectId | String,
  traineeId: ObjectId | String,
  completionMap: {
    [courseId: string]: {
      completed: Boolean,
      completedAt: Date?,
      completedBy: String?
    }
  },
  createdAt: Date?, updatedAt: Date?
}
```

### `batches`

A mentor-created group of trainees within a cohort.

```js
{
  _id: ObjectId,
  mentorId: ObjectId,
  cohortId: ObjectId,
  name: String,
  description: String?,
  timezone: String?,
  trainingLevel: String?,
  maxTrainees: Number?,
  startDate: Date?, endDate: Date?,
  status: "draft" | "active" | "completed" | "paused" | "archived",
  traineeIds: [ObjectId],
  createdAt: Date,
  updatedAt: Date?
}
```

A trainee can belong to at most one active batch at a time. The application enforces this rule.

### `sessions`

A scheduled mentor meeting for one batch. **Attendance is stored inside the session document**, in `attendance[]`, so each session retains its own attendance history.

```js
{
  _id: ObjectId,
  batchId: ObjectId,
  mentorId: ObjectId,
  sessionDate: Date,
  startTime: String,
  endTime: String,
  title: String,
  description: String?,
  format: String?,
  location: String?,
  meetingLink: String?,
  maxAttendees: Number?,
  roster: [{                       // snapshot of the batch roster for the session
    traineeId: String,
    name: String,
    email: String,
    location: String?,
    status: String?
  }],
  status: "scheduled" | "in_progress" | "completed" | "cancelled",
  attendance: [{
    traineeId: String,
    status: "present" | "late" | "absent" | "excused",
    markedAt: Date,
    markedBy: String
  }],
  createdAt: Date,
  updatedAt: Date?
}
```

Attendance is editable after it has been submitted. A session can hold multiple attendance entries, one for each trainee in its roster.

## Relationships and indexes

- `users` → `mentors`: optional account/profile link through `mentors.userId`.
- `users` (role `nominator`) → `mentors` / `trainees`: a nominator owns the people they nominated through `nominatedBy`. Nominators are not linked to cohorts.
- `mentors`: one mentor profile/login can belong to many cohorts through `cohortIds`; `cohortId` remains as a compatibility reference. Additional memberships never create another mentor profile or login.
- `trainees`: `cohortId` is `null` while a nominee is only in the nomination pool. A trainee belongs to at most one cohort at a time; reassignment history is retained in `cohortAssignmentHistory`.
- Mentor `isActive` is the global account switch. `cohortAccess[cohortId]` is the independent per-cohort access switch; global deactivation denies access everywhere.
- `cohorts` → `mentors`, `trainees`, `batches`, and cohort-specific training/feedback copies.
- `mentors` → `trainees`: trainee assignment through `trainees.mentorId`.
- `trainees` → `progress`: one progress document per trainee.
- `trainees` → `feedbackResponses`: one response per trainee and week.
- `batches` → `trainees`: embedded ID list in `batches.traineeIds`.
- `batches` → `sessions`: session documents reference `batches._id`.
- `sessions` → attendance: embedded in `sessions.attendance[]`.

Indexes initialized by the backend include unique `users.email`, unique `personIdentityClaims.claim`, unique `progress.traineeId`, unique `feedbackResponses.(traineeId, weekNumber)`, unique `mentorEvaluations.(traineeId, cohortId)`, mentor lookup indexes by `userId` and `cohortIds`, batch lookup indexes, mentor/trainee cohort-location-timezone indexes, and session batch/date indexes.

See [DATABASE_SCHEMA_DIAGRAM.md](DATABASE_SCHEMA_DIAGRAM.md) for the entity relationship diagram.
