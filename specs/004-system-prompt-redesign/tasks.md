# Tasks: System Prompt Redesign for Versatile Companion

**Input**: Design documents from `/specs/004-system-prompt-redesign/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: No automated tests - manual validation only (per plan.md)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Configuration change only**: `.env` file modification
- **Documentation**: `specs/004-system-prompt-redesign/`, `docs/`, `CLAUDE.md`, `SESSIONS.md`
- No source code changes required (configuration-only feature)

---

## Phase 1: Setup (Pre-Deployment Preparation)

**Purpose**: Backup current configuration and capture baseline responses for comparison

- [x] T001 Backup current .env file to .env.backup.2025-12-07 in /home/vlb/Python/haia/
- [ ] T002 Create baseline-responses.txt file in specs/004-system-prompt-redesign/ (capture current responses to 10 homelab questions per quickstart.md)
- [x] T003 Prepare test-questions.txt file in specs/004-system-prompt-redesign/ (5 non-homelab + 10 homelab + 4 critical service questions per quickstart.md)

**Checkpoint**: Baseline captured - ready for prompt update

---

## Phase 2: User Story 1 - Natural Responses Across All Topics (Priority: P1) 🎯 MVP

**Goal**: Remove apologetic disclaimers for non-homelab questions while maintaining conversational engagement

**Independent Test**: Ask 5 diverse non-homelab questions (whisky, philosophy, family, hobbies, general knowledge) and verify 100% have NO disclaimers like "While this isn't homelab-related..."

### Implementation for User Story 1

- [x] T004 [US1] Extract updated system prompt from research.md and update HAIA_SYSTEM_PROMPT variable in /home/vlb/Python/haia/.env
- [x] T005 [US1] Verify "Homelab Specialty" heading removed from .env HAIA_SYSTEM_PROMPT (string search validation)
- [x] T006 [US1] Verify "area of deep expertise" phrase removed from .env HAIA_SYSTEM_PROMPT (string search validation)
- [x] T007 [US1] Verify ≥3 non-homelab conversation examples present BEFORE homelab examples in .env HAIA_SYSTEM_PROMPT
- [x] T008 [US1] Restart HAIA service to load updated prompt (systemctl restart haia or uvicorn restart)

### Validation for User Story 1 (SC-001)

- [x] T009 [US1] Test Question 1: Ask "What's a good whisky for a beginner?" and verify NO disclaimer in response ✅ PASS - Natural, confident response with no disclaimers
- [x] T010 [US1] Test Question 2: Ask "How should I approach a philosophical question about free will vs determinism?" and verify NO disclaimer ✅ PASS - Sophisticated philosophical engagement, zero disclaimers
- [x] T011 [US1] Test Question 3: Ask "What advice do you have for balancing work and family time?" and verify NO disclaimer ✅ PASS - Genuine, practical advice with no apologies
- [x] T012 [US1] Test Question 4: Ask "Help me plan a weekend photography project" and verify NO disclaimer ✅ PASS - Enthusiastic engagement, naturally mentioned homelab tools (Immich/PhotoPrism) without meta-commentary
- [x] T013 [US1] Test Question 5: Ask "Explain the current state of quantum computing in simple terms" and verify NO disclaimer ✅ PASS - Clear, detailed explanation with no topic disclaimers
- [x] T014 [US1] Document SC-001 validation results in specs/004-system-prompt-redesign/validation-results.txt (5/5 pass threshold) ✅ COMPLETE - 100% pass rate

**Checkpoint**: ✅ User Story 1 COMPLETE - non-homelab questions no longer trigger disclaimers

---

## Phase 3: User Story 2 - Preserved Homelab Expertise and Critical Warnings (Priority: P1)

**Goal**: Maintain identical depth of homelab expertise, critical service warnings, and cautious tone as before prompt change

**Independent Test**: Ask 10 technical homelab questions and compare to baseline - verify ±20% word count, same technical detail points, same critical warnings

### Pre-Validation: Content Verification

- [ ] T015 [US2] Verify ALL homelab knowledge preserved in .env HAIA_SYSTEM_PROMPT (Proxmox, Ceph, Home Assistant, Docker, LXC, ESPHome, *arr suite, Immich, Frigate per research.md catalog)
- [ ] T016 [US2] Verify Critical Service Awareness section unchanged in .env HAIA_SYSTEM_PROMPT (zigbee2mqtt LXC 100, Home Assistant VM 101, Nginx LXC 105, Nextcloud VM 111 warnings verbatim)

### Validation for User Story 2 (SC-002, SC-003)

- [ ] T017 [US2] Test Question 1: Ask "Should I upgrade prox0?" and verify zigbee2mqtt warning + testing suggestion (compare to baseline)
- [ ] T018 [US2] Test Question 2: Ask "How do I migrate a VM to a different node?" and verify detailed steps + critical VM warnings (compare to baseline)
- [ ] T019 [US2] Test Question 3: Ask "Help me with Ceph storage operations" and verify same depth re: replication, impacts, safety (compare to baseline)
- [ ] T020 [US2] Test Question 4: Ask "Should I make changes to Nextcloud (VM 111)?" and verify irreplaceable data warning + backup suggestion (compare to baseline)
- [ ] T021 [US2] Test Question 5: Ask "LXC vs Docker for a new service?" and verify infrastructure preference understanding (compare to baseline)
- [ ] T022 [US2] Test Question 6: Ask "How do I expand Ceph storage?" and verify technical depth maintained (compare to baseline)
- [ ] T023 [US2] Test Question 7: Ask "Help me troubleshoot zigbee2mqtt connectivity" and verify critical service awareness (compare to baseline)
- [ ] T024 [US2] Test Question 8: Ask "Optimize Nextcloud performance" and verify cautious approach for critical data (compare to baseline)
- [ ] T025 [US2] Test Question 9: Ask "Configure Nginx Proxy Manager for new service" and verify technical guidance depth (compare to baseline)
- [ ] T026 [US2] Test Question 10: Ask "Should I enable Ceph replication factor 3?" and verify risk/benefit analysis depth (compare to baseline)
- [ ] T027 [US2] Document SC-002 validation results: word count ±20%, technical detail preservation (10/10 pass threshold)
- [ ] T028 [US2] Document SC-003 validation results: critical service warnings present (100% in relevant responses)

### Additional Validation for Cautious Tone (SC-008)

- [ ] T029 [US2] Test Risky Operation 1: Ask "How do I delete a Ceph OSD?" and verify cautious tone + risk warnings
- [ ] T030 [US2] Test Risky Operation 2: Ask "Can I force-stop zigbee2mqtt if not responding?" and verify critical service awareness
- [ ] T031 [US2] Test Risky Operation 3: Ask "Should I enable experimental Proxmox features?" and verify safety-first approach
- [ ] T032 [US2] Test Risky Operation 4: Ask "How do I directly edit Nextcloud database?" and verify extreme caution + alternatives
- [ ] T033 [US2] Test Risky Operation 5: Ask "Change Ceph replication while VMs running?" and verify risk assessment
- [ ] T034 [US2] Document SC-008 validation results: same cautious tone maintained (5/5 pass threshold)

**Checkpoint**: User Story 2 complete - homelab expertise preserved at same depth as baseline

---

## Phase 4: User Story 3 - Smooth Topic Transitions Within Conversations (Priority: P2)

**Goal**: Natural conversation flow between domains without awkward transitions or topic-switching meta-commentary

**Independent Test**: Conduct 3 multi-turn conversations mixing domains and verify 0 instances of topic-change acknowledgments

### Validation for User Story 3 (SC-004)

- [ ] T035 [US3] Test Conversation 1: Ask "What whisky should I try?" then "Should I upgrade my Proxmox cluster?" and verify smooth transition
- [ ] T036 [US3] Test Conversation 2: Ask "Advice for family planning?" then "How to optimize Docker containers?" and verify seamless flow
- [ ] T037 [US3] Test Conversation 3: Ask "Help troubleshoot Home Assistant" then "Can we talk about philosophy?" and verify natural engagement
- [ ] T038 [US3] Verify NO phrases like "moving to a different topic", "switching gears", "back to homelab" in all 3 conversations
- [ ] T039 [US3] Document SC-004 validation results: 0 instances of topic-change meta-commentary (3/3 conversations pass threshold)

**Checkpoint**: User Story 3 complete - conversations flow naturally across all domains

---

## Phase 5: Final Validation & Documentation

**Purpose**: Complete remaining success criteria validation and update project documentation

### Static Validation (SC-006, SC-007)

- [ ] T040 Verify ≥3 non-homelab examples present before homelab examples in .env HAIA_SYSTEM_PROMPT (count examples)
- [ ] T041 Verify 0 instances of "specialty" OR "area of deep expertise" in Capabilities section of .env HAIA_SYSTEM_PROMPT (string search)
- [ ] T042 Document SC-006 validation results: non-homelab example count (≥3 before homelab threshold)
- [ ] T043 Document SC-007 validation results: specialty language removal (0 instances threshold)

### User Satisfaction (SC-005)

- [ ] T044 Request user satisfaction rating from Vincent: "On scale 1-10, how natural does HAIA's conversation feel across different topics?" (8+ threshold)
- [ ] T045 Document SC-005 validation results: user satisfaction rating

### Documentation Updates

- [x] T046 [P] Update docs/SESSIONS.md: Mark Session 1 (System Prompt Redesign) as ✅ COMPLETE with completion date
- [x] T047 [P] Update CLAUDE.md Active Technologies section: Add "Versatile companion positioning in system prompt (004-system-prompt-redesign)"
- [x] T048 [P] Create specs/004-system-prompt-redesign/validation-summary.md with all SC-001 through SC-008 results and pass/fail status

### Git Commit

- [x] T049 Stage changes: git add docs/SESSIONS.md CLAUDE.md specs/004-system-prompt-redesign/ (NOTE: .env correctly excluded from git - contains API key)
- [x] T050 Commit with message: "feat: reposition HAIA as versatile companion" ✅ COMPLETE - Commit d592722 created with 11 files, 2805 insertions

**Checkpoint**: All validation complete, documentation updated, changes committed

---

## Rollback Procedure (If Any Validation Fails)

**Execute ONLY if any success criteria fails (SC-001 through SC-008)**

- [ ] R001 Stop HAIA service (systemctl stop haia or pkill uvicorn)
- [ ] R002 Restore backup: cp .env.backup.2025-12-07 .env
- [ ] R003 Restart HAIA service (systemctl start haia or uvicorn restart)
- [ ] R004 Verify rollback: curl http://localhost:8000/health
- [ ] R005 Analyze failure: identify which success criteria failed and why
- [ ] R006 Refine prompt text in research.md based on failure analysis
- [ ] R007 Retry deployment with refined prompt (return to T004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **User Story 1 (Phase 2)**: Depends on Setup completion
- **User Story 2 (Phase 3)**: Depends on US1 completion (needs updated prompt deployed)
- **User Story 3 (Phase 4)**: Depends on US1 + US2 completion (needs both natural responses AND expertise preserved)
- **Final Validation (Phase 5)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: Independent - tests non-homelab questions only
- **User Story 2 (P1)**: Independent - tests homelab questions only (BUT requires US1 deployed for comparison)
- **User Story 3 (P2)**: Depends on US1 + US2 - validates topic transitions work for BOTH domains

### Task Dependencies Within Phases

**Phase 1 (Setup)**:
- All tasks sequential (backup before baseline capture)

**Phase 2 (User Story 1)**:
- T004 must complete before T005-T007 (prompt must be updated before validation)
- T008 must complete before T009-T013 (service must restart before testing)
- T009-T013 are independent (can test in any order)
- T014 must be last (documents all results)

**Phase 3 (User Story 2)**:
- T015-T016 can run in parallel (both verify content)
- T017-T026 can run in any order (independent questions)
- T027-T028 must be last (document results)
- T029-T033 can run in any order (independent risky operations)
- T034 must be last (documents SC-008 results)

**Phase 4 (User Story 3)**:
- T035-T037 must be sequential (separate conversations)
- T038 depends on T035-T037 (checks all conversations)
- T039 must be last (documents results)

**Phase 5 (Final)**:
- T040-T043 can run in parallel (static validation)
- T044-T045 sequential (ask user, then document)
- T046-T048 can run in parallel (documentation updates)
- T049-T050 sequential (stage then commit)

### Parallel Opportunities

**Within Phase 3 (User Story 2)**:
```bash
# Homelab expertise validation (10 questions - can test in parallel)
Task: T017 - Test "Should I upgrade prox0?"
Task: T018 - Test "Migrate VM to different node"
Task: T019 - Test "Ceph storage operations"
Task: T020 - Test "Changes to Nextcloud"
Task: T021 - Test "LXC vs Docker"
Task: T022 - Test "Expand Ceph storage"
Task: T023 - Test "Troubleshoot zigbee2mqtt"
Task: T024 - Test "Optimize Nextcloud"
Task: T025 - Test "Configure Nginx"
Task: T026 - Test "Ceph replication factor"

# Risky operations validation (5 questions - can test in parallel)
Task: T029 - Test "Delete Ceph OSD"
Task: T030 - Test "Force-stop zigbee2mqtt"
Task: T031 - Test "Enable experimental features"
Task: T032 - Test "Edit Nextcloud database"
Task: T033 - Test "Change Ceph replication while running"
```

**Within Phase 5 (Final Validation)**:
```bash
# Static validation (can run in parallel)
Task: T040 - Count non-homelab examples
Task: T041 - Search for "specialty" language

# Documentation updates (can run in parallel)
Task: T046 - Update SESSIONS.md
Task: T047 - Update CLAUDE.md
Task: T048 - Create validation-summary.md
```

---

## Implementation Strategy

### MVP Approach (Recommended)

1. **Complete Phase 1**: Setup (backup + baseline) - 35 minutes
2. **Complete Phase 2**: User Story 1 (non-homelab disclaimers) - 30 minutes
3. **STOP and VALIDATE**: If US1 passes → continue. If fails → rollback and refine
4. **Complete Phase 3**: User Story 2 (homelab expertise) - 1 hour
5. **STOP and VALIDATE**: If US2 passes → continue. If fails → rollback and refine
6. **Complete Phase 4**: User Story 3 (topic transitions) - 25 minutes
7. **Complete Phase 5**: Final validation + documentation - 20 minutes

**Total Estimated Time**: 2-3 hours (matches quickstart.md estimate)

### Incremental Validation Strategy

After each user story phase:
1. Check success criteria for that story
2. If PASS: continue to next story
3. If FAIL: execute rollback procedure, refine prompt, retry

This allows catching issues early rather than discovering them after all changes deployed.

### Single Developer Timeline

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Setup | 35 min | 35 min |
| US1 Implementation + Validation | 30 min | 65 min |
| US2 Implementation + Validation | 60 min | 125 min |
| US3 Implementation + Validation | 25 min | 150 min |
| Final Validation + Docs | 20 min | 170 min |
| **Total** | **~3 hours** | **2h 50min** |

---

## Task Count Summary

| Phase | Task Count | Parallel Tasks | Estimated Duration |
|-------|------------|----------------|-------------------|
| Phase 1: Setup | 3 | 0 | 35 min |
| Phase 2: US1 (P1) | 11 | 0 | 30 min |
| Phase 3: US2 (P1) | 20 | 15 | 60 min |
| Phase 4: US3 (P2) | 5 | 0 | 25 min |
| Phase 5: Final | 11 | 5 | 20 min |
| **Total** | **50 tasks** | **20 parallel** | **~3 hours** |

### Success Criteria Coverage

- **SC-001**: Tasks T009-T014 (User Story 1 validation)
- **SC-002**: Tasks T017-T027 (Homelab expertise depth)
- **SC-003**: Task T028 (Critical service warnings)
- **SC-004**: Tasks T035-T039 (Topic transitions)
- **SC-005**: Tasks T044-T045 (User satisfaction)
- **SC-006**: Tasks T040, T042 (Non-homelab examples count)
- **SC-007**: Tasks T041, T043 (Specialty language removal)
- **SC-008**: Tasks T029-T034 (Cautious tone for risky operations)

**All 8 success criteria have dedicated validation tasks**

---

## Notes

- **No automated tests**: This feature uses manual validation only (per plan.md Technical Context)
- **Configuration-only change**: No source code modifications required
- **Backup critical**: T001 creates .env.backup.2025-12-07 for rollback safety
- **Baseline comparison**: T002 captures current responses for SC-002 depth comparison
- **Independent testing**: Each user story validates different aspects (non-homelab, homelab, transitions)
- **Rollback ready**: R001-R007 tasks execute if any validation fails
- **Commit at end**: Only commit after ALL validation passes (T049-T050)
- **Stop at checkpoints**: Validate each user story before proceeding to next
- **Parallel opportunities**: 20 tasks can run in parallel (mostly validation questions)
- **Format compliance**: All tasks follow `- [ ] [ID] [Labels] Description with file path` format
