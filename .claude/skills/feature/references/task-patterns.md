# Task Patterns Reference

Common patterns for creating effective task lists.

## Task Granularity

### Too Coarse (Bad)
```
- Implement authentication system
```

### Too Fine (Bad)
```
- Create User class
- Add email field to User class
- Add password field to User class
- Add validation for email field
```

### Just Right (Good)
```
- Create User model with email and password fields
- Implement password hashing and validation
- Create login endpoint with JWT token generation
- Add authentication middleware
- Write tests for auth flow
```

## Task Categories

### 1. Setup/Preparation
Tasks that prepare the environment or scaffolding:
- Install dependencies
- Create directory structure
- Set up configuration files
- Create base classes/interfaces

### 2. Core Implementation
Main feature development:
- Implement business logic
- Create data models
- Build API endpoints
- Develop UI components

### 3. Integration
Connecting components:
- Wire up dependencies
- Connect to external services
- Integrate with existing features

### 4. Verification — NOT a category of its own

**Verification is not a phase at the end.** Phase 4 of `/feature` pairs EVERY
implementation task with a `verify:` task that names the scenario IDs and the
command, so verification tasks are interleaved, never collected into a final
block. Writing the tests is part of the implementation task they verify.

A trailing block is allowed for exactly one thing: the slowest configured tier,
run once at the end (see "Implementation Loop" in
`.claude/skills/feature/SKILL.md`).

### 5. Documentation (Optional)
Only when explicitly needed:
- Update API docs
- Add code comments for complex logic

## Dependency Ordering

Order tasks by dependencies:

```
1. [Independent] Create database schema
2. [Independent] Define TypeScript interfaces
3. [Depends on 1,2] Implement data access layer
4. [Depends on 3] Build service layer
5. [Depends on 4] Create API endpoints
6. [Depends on 5] Add authentication checks
```

## Task Status Flow

```
pending → in_progress → completed
                ↓
         (if blocked)
                ↓
        Create new task for blocker
```

## Example: User Authentication Feature

```
## Setup
- [ ] Add bcrypt and jsonwebtoken dependencies
- [ ] Create auth/ directory structure

## Core Implementation
- [ ] Create User model with password hashing
- [ ] verify:task V1 — .claude/scripts/verify-task
- [ ] Implement UserRepository with CRUD operations
- [ ] verify:task V2 — .claude/scripts/verify-task
- [ ] Create AuthService with login/register logic
- [ ] verify:task V3 — .claude/scripts/verify-task
- [ ] Build POST /auth/register and /auth/login endpoints
- [ ] Implement JWT middleware for protected routes
- [ ] verify:task V4 — .claude/scripts/verify-task

## Integration
- [ ] Add auth middleware to existing protected routes
- [ ] verify:task V5 — .claude/scripts/verify-task
- [ ] Update user creation flow to use new auth
- [ ] verify:task V6 — .claude/scripts/verify-task

## End of the unit
- [ ] verify:unit V1-V6 — .claude/scripts/verify-unit   (slowest configured tier)
```

Every implementation line above is followed by the `verify:` line that proves it
— that is the shape Phase 4 requires. The scenario IDs come from the Phase 2b
verification plan; they are not invented here.

## Complexity Estimation

From deep-reasoning analysis, tag tasks with complexity:

| Complexity | Time Estimate | Characteristics |
|------------|---------------|-----------------|
| Low | 5-15 min | Single file, clear pattern |
| Medium | 15-30 min | Multiple files, some decisions |
| High | 30-60 min | Complex logic, research needed |

## When to Re-plan

Create new tasks or consult deep-reasoning again when:

1. **Unexpected complexity** — Task taking 2x+ estimated time
2. **Blocker discovered** — Dependency on unfinished work
3. **Scope change** — User adds new requirements
4. **Technical pivot** — Chosen approach doesn't work
