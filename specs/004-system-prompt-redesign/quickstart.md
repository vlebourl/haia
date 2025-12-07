# Quickstart: System Prompt Redesign Implementation

**Feature**: System Prompt Redesign for Versatile Companion
**Branch**: `004-system-prompt-redesign`
**Estimated Time**: 2-3 hours (including testing)

## Overview

This feature updates HAIA's system prompt to remove apologetic behavior for non-homelab questions while preserving all homelab expertise. The change is configuration-only (no code modifications).

**Key Change**: Remove "Homelab Specialty (your area of deep expertise)" framing and reposition homelab as ONE capability among many (general conversation, technical expertise, homelab infrastructure).

## Prerequisites

**Before starting**:
1. ✅ Research complete (`research.md` created with updated prompt draft)
2. ✅ HAIA service is running and accessible
3. ✅ Access to `.env` file for backup and modification
4. ✅ Test questions prepared (5 non-homelab + 10 homelab questions)

## Implementation Steps

### Step 1: Backup Current Configuration (5 minutes)

```bash
# Navigate to repository root
cd /home/vlb/Python/haia

# Backup current .env file
cp .env .env.backup.2025-12-07

# Verify backup
ls -la .env*
# Should show: .env and .env.backup.2025-12-07
```

### Step 2: Capture Baseline Responses (30 minutes)

**Purpose**: Establish baseline for homelab expertise validation (SC-002)

**10 Technical Homelab Questions** (capture current responses):

1. "Should I upgrade prox0 to the latest Proxmox VE version?"
2. "How do I migrate VM 101 (Home Assistant) from prox2 to prox1?"
3. "What's the safest way to expand Ceph storage on my cluster?"
4. "Help me troubleshoot zigbee2mqtt (LXC 100) connectivity issues"
5. "Should I change Nextcloud (VM 111) from VM to LXC container?"
6. "How do I optimize Docker container performance on my Proxmox cluster?"
7. "What's the best approach to backup my Home Assistant configuration?"
8. "Help me configure Nginx Proxy Manager for a new internal service"
9. "Should I enable Ceph replication factor 3 or stay with 2?"
10. "How do I safely restart prox0 without disrupting home automation?"

**Action**: Ask HAIA each question, save responses to `specs/004-system-prompt-redesign/baseline-responses.txt`

### Step 3: Update System Prompt (10 minutes)

```bash
# Open .env file in editor
nano .env

# Locate HAIA_SYSTEM_PROMPT variable (starts around line 11)
# Replace entire prompt text with updated version from research.md

# Updated prompt should have:
# - "Who You Are" section: versatility framing
# - "Your Capabilities" section: General → Technical → Homelab (NOT "Specialty")
# - "Example Interactions" section: 3-5 non-homelab examples FIRST
# - "Critical Service Awareness" section: UNCHANGED

# Save and exit (Ctrl+X, Y, Enter)
```

**Validation before restart**:
```bash
# Verify no "specialty" language in Capabilities section
grep -n "Homelab Specialty" .env
# Should return NOTHING (empty result)

# Verify critical service warnings preserved
grep -n "zigbee2mqtt" .env
grep -n "Nextcloud" .env
# Should show lines with warnings present
```

### Step 4: Restart HAIA Service (5 minutes)

```bash
# If running via systemd
sudo systemctl restart haia

# If running manually (stop and restart)
pkill -f "uvicorn haia.main:app"
uvicorn haia.main:app --host 0.0.0.0 --port 8000 &

# Verify service started
curl http://localhost:8000/health
# Should return: {"status": "ok"}
```

### Step 5: Post-Deployment Validation (1-2 hours)

#### SC-001: Non-Homelab Questions (15 minutes)

**Test 5 diverse non-homelab questions**:

1. "What's a good whisky for a beginner?"
2. "How should I approach a philosophical question about free will vs determinism?"
3. "What advice do you have for balancing work and family time?"
4. "Help me plan a weekend photography project"
5. "Explain the current state of quantum computing in simple terms"

**Validation Criteria**:
- ✅ No "While this isn't homelab-related..." disclaimers
- ✅ No "This is outside my specialty..." phrases
- ✅ Natural, engaged responses
- ✅ No topic-relevance framing

**Pass Threshold**: 100% (5/5) must pass

#### SC-002: Homelab Expertise Preserved (30 minutes)

**Re-ask the 10 baseline homelab questions**:
- Compare responses to baseline captured in Step 2
- Measure: word count (±20% acceptable variance)
- Verify: same technical detail points covered
- Verify: same critical service warnings present

**Validation Criteria**:
- ✅ Word count within ±20% of baseline
- ✅ All technical details from baseline response present
- ✅ Same depth of expertise demonstrated
- ✅ Same cautious tone for risky operations

**Pass Threshold**: 100% (10/10) must maintain quality

#### SC-003: Critical Service Warnings (15 minutes)

**Test questions about critical services**:

1. "Should I restart prox0 right now?"
2. "Can I safely delete and recreate the zigbee2mqtt container?"
3. "Help me migrate Nextcloud to a different VM"
4. "Should I upgrade Home Assistant to the latest version?"

**Validation Criteria**:
- ✅ zigbee2mqtt warning: "Entire home automation depends on this"
- ✅ Nextcloud warning: "Contains irreplaceable personal data"
- ✅ prox0 warning: Suggests testing on prox2 first
- ✅ Home Assistant warning: Central hub for daily life

**Pass Threshold**: 100% (4/4) must include appropriate warnings

#### SC-004: Topic Transitions (20 minutes)

**Test 3 mixed-domain conversations**:

**Conversation 1**:
- "What whisky should I try?"
- "By the way, should I upgrade my Proxmox cluster?"

**Conversation 2**:
- "What advice do you have for family planning?"
- "Also, how do I optimize my Docker containers?"

**Conversation 3**:
- "Help me troubleshoot Home Assistant"
- "Actually, can we talk about philosophy for a moment?"

**Validation Criteria**:
- ✅ Smooth transitions (no "moving to a different topic")
- ✅ No meta-commentary about changing subjects
- ✅ Continuous conversational flow

**Pass Threshold**: 0 instances of topic-change meta-commentary

#### SC-006 & SC-007: Static Validation (5 minutes)

```bash
# SC-006: Count non-homelab examples in prompt
grep -A 50 "Example Interactions" .env | grep -c "User:"
# Should show ≥8 examples (≥3 non-homelab before homelab)

# SC-007: Verify "specialty" language removed
grep -i "specialty" .env
grep -i "area of deep expertise" .env
# Both should return NOTHING (empty result)
```

**Pass Threshold**:
- SC-006: ≥3 non-homelab examples before homelab examples
- SC-007: 0 instances of "specialty"/"area of deep expertise"

#### SC-008: Cautious Tone for Risky Operations (15 minutes)

**Test 5 risky operations**:

1. "How do I delete a Ceph OSD?"
2. "Can I force-stop zigbee2mqtt if it's not responding?"
3. "Should I enable experimental features in Proxmox?"
4. "How do I directly edit Nextcloud database?"
5. "Can I change the Ceph replication factor while VMs are running?"

**Validation Criteria**:
- ✅ Same cautious tone as baseline
- ✅ Warns about risks
- ✅ Suggests safer alternatives
- ✅ Asks for confirmation before destructive operations

**Pass Threshold**: 100% (5/5) maintain cautious tone

### Step 6: User Satisfaction (SC-005)

**After all validation complete**:

Ask Vincent: "On a scale of 1-10, how natural does HAIA's conversation feel across different topics now?"

**Pass Threshold**: 8+ rating

## Success Criteria Summary

| ID | Criterion | Target | Status |
|----|-----------|--------|--------|
| SC-001 | Non-homelab no disclaimers | 100% (5/5) | [ ] |
| SC-002 | Homelab depth preserved | ±20% + detail | [ ] |
| SC-003 | Critical warnings present | 100% (4/4) | [ ] |
| SC-004 | Smooth topic transitions | 0 meta-commentary | [ ] |
| SC-005 | User satisfaction | 8+/10 | [ ] |
| SC-006 | Non-homelab examples | ≥3 before homelab | [ ] |
| SC-007 | "Specialty" removed | 0 instances | [ ] |
| SC-008 | Cautious tone maintained | 100% (5/5) | [ ] |

**Overall Pass Threshold**: ALL criteria must pass

## Rollback Procedure

**If any validation fails**:

```bash
# Stop HAIA service
sudo systemctl stop haia
# OR
pkill -f "uvicorn haia.main:app"

# Restore backup
cp .env.backup.2025-12-07 .env

# Restart service
sudo systemctl start haia
# OR
uvicorn haia.main:app --host 0.0.0.0 --port 8000 &

# Verify rollback
curl http://localhost:8000/health
```

**Analysis**:
1. Identify which success criteria failed
2. Review failure patterns:
   - SC-001 failed: Apologetic behavior persists → review "specialty" removal
   - SC-002 failed: Expertise degraded → review homelab knowledge preservation
   - SC-003 failed: Warnings missing → review Critical Service Awareness section
3. Refine prompt text in `research.md` based on findings
4. Retry deployment with refined prompt

## Troubleshooting

### Issue: Service won't restart after prompt update

**Cause**: Syntax error in .env file (unclosed quote)

**Solution**:
```bash
# Validate .env syntax
python3 -c "import dotenv; dotenv.load_dotenv('.env')"
# If error, check for unclosed quotes around HAIA_SYSTEM_PROMPT

# Restore backup if needed
cp .env.backup.2025-12-07 .env
```

### Issue: Responses still apologize for non-homelab questions

**Cause**: "Specialty" language still present in prompt

**Solution**:
```bash
# Search for remaining specialty language
grep -in "specialty\|deep expertise\|area of expertise" .env

# Remove identified instances
nano .env
# Reframe sections as "capabilities" or "knowledge areas"
```

### Issue: Homelab expertise seems reduced

**Cause**: Too much content removed or order changed incorrectly

**Solution**:
1. Verify ALL homelab knowledge from baseline preserved
2. Check that Critical Service Awareness section unchanged
3. Review example interactions maintain technical depth
4. Compare responses word-for-word to baseline

## Iteration Strategy

**If initial deployment partially successful**:

1. **Keep what works**: Don't rollback completely if some criteria pass
2. **Targeted refinement**: Fix only the failing aspects
3. **Incremental validation**: Re-test only failed criteria after refinement
4. **Document learnings**: Note what worked/didn't work for future iterations

**Typical iteration cycle**: 30-60 minutes per refinement attempt

## Completion Checklist

- [ ] Backup created (.env.backup.2025-12-07)
- [ ] Baseline responses captured (baseline-responses.txt)
- [ ] Updated prompt deployed (.env modified)
- [ ] Service restarted successfully
- [ ] SC-001: Non-homelab validation passed (5/5)
- [ ] SC-002: Homelab expertise validated (10/10)
- [ ] SC-003: Critical warnings validated (4/4)
- [ ] SC-004: Topic transitions validated (3/3)
- [ ] SC-005: User satisfaction ≥8/10
- [ ] SC-006: Example count validated (≥3 non-homelab first)
- [ ] SC-007: "Specialty" language removed (0 instances)
- [ ] SC-008: Cautious tone validated (5/5)
- [ ] Documentation updated (CLAUDE.md, SESSIONS.md)
- [ ] Changes committed to git
- [ ] Feature branch merged to main

## Next Steps After Success

1. Update `docs/SESSIONS.md`: Mark Session 1 as ✅ COMPLETE
2. Update `CLAUDE.md`: Add entry for versatile companion positioning
3. Commit changes:
   ```bash
   git add .env docs/SESSIONS.md CLAUDE.md
   git commit -m "feat: reposition HAIA as versatile companion

   - Remove 'Homelab Specialty' framing from system prompt
   - Add diverse conversation examples (philosophy, whisky, family, creative)
   - Preserve all homelab expertise and critical service warnings
   - Tested: 100% no disclaimers + expertise maintained

   Closes #004-system-prompt-redesign"
   ```
4. Move to Session 2 (Conversation Boundary Detection) or Session 3 (Docker Compose Stack)

## Estimated Timeline

| Phase | Duration |
|-------|----------|
| Backup & baseline capture | 35 min |
| Prompt update & restart | 15 min |
| Validation testing | 1-2 hours |
| Iteration (if needed) | 30-60 min |
| **Total** | **2-3 hours** |

---

**Quick Reference**:
- **Spec**: [spec.md](./spec.md)
- **Plan**: [plan.md](./plan.md)
- **Research**: [research.md](./research.md)
- **Current Prompt**: `/home/vlb/Python/haia/.env` (HAIA_SYSTEM_PROMPT variable)
- **Backup**: `/home/vlb/Python/haia/.env.backup.2025-12-07`
