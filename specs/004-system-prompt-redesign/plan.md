# Implementation Plan: System Prompt Redesign for Versatile Companion

**Branch**: `004-system-prompt-redesign` | **Date**: 2025-12-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-system-prompt-redesign/spec.md`

## Summary

Update HAIA's system prompt to position her as a versatile personal companion while maintaining deep homelab expertise. Remove "Homelab Specialty (your area of deep expertise)" framing that triggers apologetic behavior for non-homelab questions. Reposition homelab as ONE capability among many (general conversation, technical expertise, homelab infrastructure). Preserve ALL existing homelab knowledge, critical service warnings, and technical depth. Add diverse conversation examples to demonstrate versatility. Test that responses are natural across ALL topics without disclaimers while preserving expert-level homelab responses.

**Technical Approach**: Direct text modification of HAIA_SYSTEM_PROMPT environment variable in `.env` file. No code changes required - this is a configuration-only change affecting LLM behavior through prompt engineering.

## Technical Context

**Language/Version**: Python 3.11+ (existing codebase, no changes)
**Primary Dependencies**: PydanticAI 1.25.1+ (no changes), existing agent configuration
**Storage**: Configuration file (`.env`) - text-based prompt storage
**Testing**: Manual validation (before/after response comparison), no automated tests required
**Target Platform**: Linux server (existing deployment, no changes)
**Project Type**: Single project (configuration change only)
**Performance Goals**: N/A (prompt modification doesn't affect performance)
**Constraints**: Maintain prompt readability (<5000 tokens), preserve all critical service warnings
**Scale/Scope**: Single configuration file, ~200 lines of prompt text

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ Model-Agnostic Design
**Status**: PASS
**Rationale**: This is a prompt text change that works identically with any PydanticAI-supported model (Anthropic, Ollama, etc.). No model-specific code or assumptions.

### ✅ Safety-First Operations
**Status**: PASS
**Rationale**: This change enhances safety by maintaining critical service warnings (FR-004, SC-003). All existing safety protocols preserved in updated prompt.

### ✅ Compact, Clear, Efficient Code
**Status**: PASS
**Rationale**: No code changes required - this is configuration-only. Updated prompt will be concise and clear.

### ✅ Type Safety
**Status**: PASS
**Rationale**: No code changes, no type annotations affected. Existing type-safe configuration loading unchanged.

### ✅ Async-First Architecture
**Status**: PASS
**Rationale**: No async code affected - this is a text configuration change.

### ✅ MCP Extensibility
**Status**: PASS
**Rationale**: No tools or MCP servers affected by prompt changes.

### ✅ Observability
**Status**: PASS
**Rationale**: No logging changes required. Existing structured logging continues to capture all agent actions.

### ✅ Security Requirements
**Status**: PASS
**Rationale**: Prompt stored in `.env` file (already in `.gitignore`). No new security concerns introduced.

**Gate Result**: ✅ ALL CHECKS PASSED - No violations, proceed to Phase 0

**Re-evaluation after Phase 1**: [Will be filled after design phase]

## Project Structure

### Documentation (this feature)

```text
specs/004-system-prompt-redesign/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # Feature specification (already created)
├── checklists/
│   └── requirements.md  # Quality validation checklist (already created)
├── research.md          # Phase 0 output (to be created)
├── data-model.md        # Phase 1 output (N/A for this feature - config only)
├── quickstart.md        # Phase 1 output (to be created)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# No source code changes - configuration only

.env                     # MODIFIED: HAIA_SYSTEM_PROMPT variable updated
vincent_profile.yaml     # NO CHANGES: Infrastructure details remain unchanged
src/haia/agent.py        # NO CHANGES: Prompt loading code unchanged
```

**Structure Decision**: This is a configuration-only change affecting `.env` file. No source code modifications required. The existing PydanticAI agent setup already loads `HAIA_SYSTEM_PROMPT` from environment variables via `pydantic-settings`.

## Complexity Tracking

**No violations** - Constitution Check passed all gates. This table is not applicable.

---

## Phase 0: Research & Analysis

### Research Tasks

1. **Current Prompt Analysis**
   - Extract current HAIA_SYSTEM_PROMPT from `.env`
   - Identify all sections that position homelab as "specialty" or "area of deep expertise"
   - Catalog all existing homelab knowledge sections for preservation
   - Document all critical service warnings that MUST be maintained

2. **Baseline Response Capture**
   - Prepare 10 technical homelab test questions covering:
     - Proxmox upgrades (prox0, prox2)
     - Ceph storage operations
     - Critical service changes (zigbee2mqtt, Home Assistant, Nextcloud)
     - VM migration and container management
   - Capture current responses to establish baseline for SC-002 (±20% word count, technical detail preservation)

3. **Test Question Preparation**
   - Prepare 5 diverse non-homelab test questions for SC-001:
     - Whisky: "What's a good whisky for a beginner?"
     - Philosophy: "How should I approach a philosophical question about free will vs determinism?"
     - Family: "What advice do you have for balancing work and family time?"
     - Hobbies: "Help me plan a weekend photography project"
     - General knowledge: "Explain the current state of quantum computing in simple terms"

4. **Prompt Engineering Research**
   - Best practices for positioning AI capabilities without triggering apologetic behavior
   - Techniques for maintaining deep expertise while demonstrating versatility
   - Example formatting patterns that establish breadth-first, depth-when-needed behavior
   - Industry patterns from ChatGPT, Claude, other general-purpose assistants

5. **Conversation Example Design**
   - Design 3-5 non-homelab example interactions demonstrating versatility (FR-005):
     - Philosophy discussion example
     - Whisky/food recommendation example
     - Family advice example
     - Creative brainstorming example
   - Ensure examples are placed BEFORE homelab examples (FR-010)

### Research Deliverable

All findings consolidated in `research.md` with:
- Decision: How to reframe capabilities section
- Rationale: Why this framing avoids apologetic behavior
- Alternatives considered: Other positioning approaches evaluated
- Baseline metrics: Current response characteristics for comparison

---

## Phase 1: Design & Implementation Specification

### 1. Prompt Structure Design

**Artifact**: `quickstart.md` (implementation guide for prompt update)

Design the updated prompt structure:

```text
## Proposed Prompt Structure (Summary)

1. **Identity Section** ("Who You Are")
   - Reframe: "You're versatile across many domains" (not "homelab specialist")
   - Position homelab as ONE expertise area among many
   - Remove "Homelab Specialty (your area of deep expertise)" heading

2. **Personality Section** (no changes)
   - Maintain existing personality traits (FR-006)
   - Sophisticated, dry wit, professional, playful charm

3. **Capabilities Section** ("Your Capabilities")
   - NEW ORDER: General → Technical → Homelab (demonstrate versatility first)
   - "General Knowledge & Assistance" (conversations, creative, learning)
   - "Technical & Professional" (software dev, DevOps, architecture)
   - "Homelab Infrastructure" (Proxmox, Home Assistant, Docker) - NOT "Specialty"

4. **Example Interactions Section**
   - NEW: Add 3-5 non-homelab examples FIRST (FR-005, FR-010)
   - Philosophy, whisky, family advice, creative brainstorming
   - THEN homelab examples (maintain existing technical depth)

5. **Critical Service Awareness Section** (no changes to content)
   - Preserve ALL warnings (FR-004): zigbee2mqtt, Home Assistant, Nginx, Nextcloud
   - Maintain cautious tone for critical infrastructure
```

### 2. Updated Prompt Draft

**Artifact**: `research.md` (includes full updated prompt text)

Create complete updated HAIA_SYSTEM_PROMPT text following structure above, ensuring:
- FR-001: Remove "specialty" language ✓
- FR-002: Reframe capabilities to show versatility ✓
- FR-003: Preserve ALL homelab knowledge ✓
- FR-004: Maintain ALL critical service warnings ✓
- FR-005: Add diverse conversation examples ✓
- FR-006: Maintain existing personality traits ✓
- FR-007: Remove apologetic behavior triggers ✓
- FR-008: Position as personal companion ✓
- FR-010: Non-homelab examples before homelab examples ✓

### 3. Validation Checklist

**Artifact**: `quickstart.md` (testing instructions)

Define validation process:

**Pre-Deployment Validation**:
1. String search for forbidden phrases (FR-007):
   - "While this isn't homelab-related"
   - "This is outside my specialty"
   - "I'm primarily focused on homelab"
   - "specialty" or "area of deep expertise" in Capabilities section

2. Section presence check:
   - [ ] "General Knowledge & Assistance" section exists
   - [ ] "Technical & Professional" section exists
   - [ ] "Homelab Infrastructure" section exists (NOT "Homelab Specialty")
   - [ ] Critical Service Awareness section unchanged
   - [ ] Example Interactions includes ≥3 non-homelab examples BEFORE homelab examples

**Post-Deployment Validation** (Success Criteria):
- SC-001: Test 5 non-homelab questions → 100% no disclaimers
- SC-002: Test 10 homelab questions → maintain ±20% word count + technical depth
- SC-003: Test critical service questions → 100% warnings present
- SC-004: Test 3 mixed-domain conversations → 0 topic-change meta-commentary
- SC-006: Count example interactions → ≥3 non-homelab before homelab
- SC-007: String search → 0 instances of "specialty"/"area of deep expertise"
- SC-008: Test 5 risky operations → same cautious tone maintained

### 4. Agent Context Update

**Action**: Run `.specify/scripts/bash/update-agent-context.sh claude`

**Expected Result**: Update `CLAUDE.md` with new entry:
```markdown
## Active Technologies
- Stateless API design - client manages conversation history (003-openai-chat-api)
- Versatile companion positioning in system prompt (004-system-prompt-redesign)
```

**Note**: No new technologies added - this is a configuration change, not a technical stack change. Script may report "no updates needed" - that's expected.

### Data Model

**N/A** - This feature involves configuration text changes, not data structures. No `data-model.md` file required.

### API Contracts

**N/A** - No API changes. The OpenAI-compatible `/v1/chat/completions` endpoint remains unchanged. Prompt text affects LLM behavior, not API contract.

---

## Phase 1 Completion: Constitution Re-Check

*Re-evaluate constitution compliance after design phase*

### ✅ Model-Agnostic Design (Re-check)
**Status**: PASS
**Evidence**: Updated prompt text is model-agnostic, works with any PydanticAI-supported model.

### ✅ Safety-First Operations (Re-check)
**Status**: PASS
**Evidence**: Critical Service Awareness section preserved verbatim. All warnings maintained (FR-004).

### ✅ Compact, Clear, Efficient Code (Re-check)
**Status**: PASS
**Evidence**: No code changes. Updated prompt is concise and clear.

### ✅ Security Requirements (Re-check)
**Status**: PASS
**Evidence**: Prompt remains in `.env` file (gitignored). No security concerns.

**Final Gate Result**: ✅ ALL CHECKS PASSED - Ready for Phase 2 (task breakdown)

---

## Implementation Strategy

### Deployment Approach

**Option 1: Direct Update (Recommended)**
1. Backup current `.env` file → `.env.backup.2025-12-07`
2. Update `HAIA_SYSTEM_PROMPT` variable in `.env`
3. Restart HAIA service (or reload configuration if supported)
4. Run post-deployment validation tests
5. Compare responses to baseline captured in Phase 0

**Option 2: A/B Testing (If Desired)**
1. Create `.env.versatile` with updated prompt
2. Run HAIA with both prompts alternately
3. Compare response quality side-by-side
4. Select better performing prompt

**Recommendation**: Option 1 (Direct Update) - simpler, faster, sufficient for MVP validation.

### Rollback Plan

If post-deployment validation fails (e.g., homelab expertise degraded):
1. Stop HAIA service
2. Restore `.env` from `.env.backup.2025-12-07`
3. Restart HAIA service
4. Analyze failure: which success criteria failed?
5. Refine prompt text based on failure analysis
6. Retry deployment

### Testing Timeline

**Pre-Deployment**: 30 minutes
- Capture 10 baseline homelab responses
- Prepare 5 non-homelab test questions

**Deployment**: 5 minutes
- Backup `.env`
- Update `HAIA_SYSTEM_PROMPT`
- Restart service

**Post-Deployment Validation**: 1-2 hours
- SC-001: Test 5 non-homelab questions (15 min)
- SC-002: Test 10 homelab questions, compare to baseline (30 min)
- SC-003: Test critical service warnings (15 min)
- SC-004: Test 3 mixed-domain conversations (20 min)
- SC-006, SC-007: Static validation (string search) (5 min)
- SC-008: Test 5 risky operations (15 min)

**Total Estimated Time**: 2-3 hours (including baseline capture, deployment, validation)

---

## Risk Analysis

### Risk 1: Homelab Expertise Degradation
**Likelihood**: Medium
**Impact**: High
**Mitigation**:
- Comprehensive baseline capture (10 questions)
- Quantitative comparison (±20% word count, technical detail checklist)
- Strict SC-002 and SC-003 validation before accepting changes
- Rollback plan ready if regression detected

### Risk 2: Overcorrection (Too Generic)
**Likelihood**: Low
**Impact**: Medium
**Mitigation**:
- Maintain ALL existing homelab content (FR-003)
- Keep Critical Service Awareness section verbatim
- SC-008 validates cautious tone preserved

### Risk 3: Apologetic Behavior Persists
**Likelihood**: Low
**Impact**: Medium
**Mitigation**:
- Remove ALL identified trigger phrases (FR-007)
- Reorder examples (non-homelab first) to establish versatility pattern
- SC-001 validates 100% of non-homelab questions have no disclaimers

### Risk 4: Unintended Personality Change
**Likelihood**: Low
**Impact**: Medium
**Mitigation**:
- Personality section unchanged (FR-006)
- Manual review during Phase 1 design
- User satisfaction metric (SC-005) catches personality regressions

---

## Success Metrics Summary

| ID | Metric | Target | Validation Method |
|----|--------|--------|------------------|
| SC-001 | Non-homelab questions without disclaimers | 100% | Manual test (5 questions) |
| SC-002 | Homelab response depth preserved | ±20% word count + technical detail | Baseline comparison (10 questions) |
| SC-003 | Critical service warnings present | 100% | Manual test (critical service questions) |
| SC-004 | Topic transitions without meta-commentary | 0 instances | Manual test (3 mixed conversations) |
| SC-005 | User satisfaction rating | 8+/10 | Vincent's subjective rating |
| SC-006 | Non-homelab examples in prompt | ≥3 before homelab | String count in prompt |
| SC-007 | "Specialty" language removed | 0 instances | String search in prompt |
| SC-008 | Cautious tone for risky operations | Same as baseline | Manual test (5 risky operations) |

---

## Next Steps

After completing Phase 1 (this plan):

1. **Execute Phase 0 Research**: Create `research.md` with current prompt analysis, baseline responses, and updated prompt draft
2. **Execute Phase 1 Design**: Create `quickstart.md` with implementation instructions and validation checklist
3. **Run `/speckit.tasks`**: Generate actionable task breakdown from this plan
4. **Execute Tasks**: Implement prompt update following task sequence
5. **Validate**: Run complete validation suite (SC-001 through SC-008)
6. **Iterate if Needed**: Refine prompt based on validation results

**Estimated Total Timeline**: 1-2 days (including research, design, implementation, validation, iteration)
