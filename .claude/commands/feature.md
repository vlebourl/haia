---
description: Add a new feature to the ROADMAP with intelligent positioning and integration analysis
---

# Feature Roadmap Manager

You are managing the HAIA project roadmap. When a user requests adding a feature, follow this systematic process:

## Phase 1: Context Gathering

1. **Read project documentation** (in parallel):
   - `README.md` - Understand project architecture and current features
   - `.specify/memory/constitution.md` - Understand constraints and principles
   - `CLAUDE.md` - Understand technical decisions and patterns
   - `ROADMAP.md` - Understand existing and planned features (if file exists)

2. **Analyze the feature request**:
   - Extract core functionality being requested
   - Identify initial dependencies on project components
   - Note any obvious conflicts with constitution principles

## Phase 2: Clarifying Questions (1-5 questions)

Based on the feature request and project context, ask **1 to 5 targeted questions** to clarify:

### Question Selection Criteria

**Ask questions to clarify:**
- **Integration points**: How does this feature interact with existing/planned features?
- **Technical approach**: Which architecture pattern fits best (custom tool, MCP server, API endpoint)?
- **User interaction**: How will users access this feature (API, background scheduler, both)?
- **Dependencies**: What other features must exist first?
- **Scope boundaries**: What's included vs. what's future work?

**Number of questions (1-5) depends on:**
- 1 question: Feature is very clear and fits obviously into existing architecture
- 2-3 questions: Feature needs clarification on integration or scope
- 4-5 questions: Feature is complex, has multiple possible approaches, or has unclear dependencies

### Question Format

For each question:
1. **State the uncertainty** - "I need to understand..."
2. **Ask a specific question** - Clear, focused question
3. **Provide context/options** - Give 2-4 concrete options if applicable

**Example:**
```
I need to understand how users will trigger this monitoring.

Question 1: Should the Proxmox VM monitoring run:
a) On-demand when users ask in chat
b) On a background schedule (e.g., every 5 minutes)
c) Both on-demand and scheduled
d) Triggered by Prometheus alerts

This affects whether we implement this as an agent tool, a scheduler task, or both.
```

## Phase 3: Dependency & Integration Analysis

After receiving answers, analyze:

### Technical Fit
- ✅ **Constitution compliance**: Does this align with core principles?
  - Model-agnostic design
  - Safety-first operations
  - Compact code style
  - Type safety
  - Async-first
  - MCP extensibility
  - Observability
- ✅ **Architecture pattern**: Which pattern fits?
  - Custom `@agent.tool` (homelab-specific logic)
  - MCP server integration (standardized operations)
  - FastAPI endpoint (user-facing API)
  - Background scheduler task (proactive monitoring)
  - Combination of above

### Dependency Mapping

**Identify dependencies:**
- **MUST have first**: Features that must exist before this can be implemented
- **SHOULD have first**: Features that make this easier but aren't required
- **Independent**: Can be implemented without other features
- **Enables**: Features that this feature will enable in the future

**Example dependency analysis:**
```
Feature: "Proxmox VM health monitoring"

MUST have first:
- Proxmox API client (async)
- Configuration management (pydantic-settings)
- Agent setup with PydanticAI

SHOULD have first:
- Background scheduler (for automatic checks)
- Notification system (to alert on issues)

Independent:
- Can implement basic monitoring without notifications

Enables:
- Automated VM restart on failure
- Resource usage trending
- Capacity planning recommendations
```

### Roadmap Positioning

**Determine placement:**
1. **Phase 0 - Foundation**: Core infrastructure (config, agent setup, API structure)
2. **Phase 1 - MVP**: Minimal viable features to demonstrate value
3. **Phase 2 - Core Features**: Essential monitoring and management capabilities
4. **Phase 3 - Advanced Features**: Complex workflows, automation, intelligence
5. **Phase 4 - Future/Nice-to-Have**: Ideas for later consideration

**Placement rules:**
- Dependencies MUST come first in the roadmap
- Features in same phase can be parallel if no dependencies
- Safety-critical features should come earlier (monitoring before automation)
- Quick wins (high value, low effort) should be prioritized in MVP

## Phase 4: Generate Roadmap Entry

### Entry Format

Each feature in the roadmap should have:

```markdown
### [Phase X] Feature Name

**Description**: [1-2 sentence description]

**User Value**: [Why this matters to users]

**Implementation Approach**:
- [Architecture pattern - e.g., "Custom @agent.tool for Proxmox operations"]
- [Key components - e.g., "Async Proxmox client using proxmoxer"]
- [Integration points - e.g., "Hooks into background scheduler"]

**Dependencies**:
- ✅ [Completed feature name] (if already done)
- ⏳ [Planned feature name] - Phase X
- 📦 [External dependency] - e.g., "proxmoxer library"

**Constitution Compliance**:
- [Relevant principles - e.g., "Async-first: All Proxmox API calls are async"]
- [Safety consideration - e.g., "Read-only operations, write ops require approval"]

**Effort Estimate**: [XS/S/M/L/XL] - [Brief justification]

**Priority**: [P0/P1/P2/P3] - [Brief justification]
```

### Priority Definitions
- **P0**: Blocker - Nothing works without this (e.g., agent setup, config management)
- **P1**: Critical - MVP requires this (e.g., basic Proxmox querying)
- **P2**: Important - Core value but not MVP (e.g., advanced monitoring)
- **P3**: Nice-to-have - Future enhancement (e.g., predictive analytics)

## Phase 5: Update ROADMAP.md

### If ROADMAP.md doesn't exist:

Create it with this structure:

```markdown
# HAIA Development Roadmap

**Last Updated**: [DATE]
**Version**: 0.1.0

## Overview

This roadmap outlines the planned development of HAIA (Homelab AI Assistant). Features are organized by phase, with dependencies clearly marked.

## Roadmap Phases

### Phase 0: Foundation [Current]
[Foundation features]

### Phase 1: MVP
[MVP features]

### Phase 2: Core Features
[Core features]

### Phase 3: Advanced Features
[Advanced features]

### Phase 4: Future Considerations
[Future features]

## Completed Features

- ✅ [Feature name] - [Completion date]

## Changelog

- [DATE]: Initial roadmap created
```

### If ROADMAP.md exists:

1. **Read the current roadmap** completely
2. **Identify the correct phase** for the new feature based on dependencies
3. **Insert the feature** in the appropriate phase section
4. **Update "Last Updated" date**
5. **Add changelog entry** documenting the addition
6. **Reorder within phase if needed** to respect dependencies

### Insertion Rules

- If feature has dependencies, ensure they appear first in the roadmap
- If feature is a dependency for existing features, insert it before them
- If feature is independent, add to end of appropriate phase
- If feature should be higher priority than existing features in same phase, insert at top

## Phase 6: Summary Output

After updating the roadmap, provide a summary:

```
✅ Added to ROADMAP: [Feature Name]

📍 Position: Phase [X] - [Priority]
🔗 Dependencies: [List]
🎯 Enables: [List or "None - leaf feature"]
⚙️ Implementation: [Architecture pattern]
📏 Effort: [Size]

The feature has been positioned [before/after] [related features] because [dependency/priority reasoning].

Next steps:
- Review the updated ROADMAP.md
- Use /speckit.specify to create detailed specification when ready to implement
```

## Important Guidelines

1. **Always read before writing**: Never modify ROADMAP.md without reading it first
2. **Preserve existing content**: Don't remove or modify existing features unless explicitly asked
3. **Maintain dependencies**: Ensure dependency ordering is correct after insertion
4. **Constitution first**: Flag any feature that conflicts with constitution principles
5. **Be opinionated**: Make clear recommendations on architecture and positioning
6. **Think critically**: If a feature request is vague or problematic, ask clarifying questions

## Examples

### Good Feature Request Flow

User: "Add Proxmox VM monitoring"

*Read docs → Analyze → Ask 2 clarifying questions*

Questions:
1. Should monitoring run on-demand (user asks in chat) or scheduled (background checks)?
2. What should we monitor: just VM status, or also resource usage (CPU/RAM/disk)?

*User answers → Analyze dependencies*

Result:
- Phase 1 (MVP) if basic status checking
- Phase 2 if including resource metrics
- Dependencies: Proxmox client, scheduler (for background)
- Implementation: @agent.tool + scheduler task

### Feature Conflicts with Constitution

User: "Add feature to automatically restart any failed VM"

Response:
```
⚠️ Constitution Conflict Detected

This feature conflicts with Principle II (Safety-First Operations):
- Auto-restart is a write operation affecting infrastructure
- Constitution requires user approval for write operations

Recommended approach:
1. Monitor VM status (read operation - safe)
2. Notify user when VM fails (notification - safe)
3. Suggest restart action (LLM decision - safe)
4. Request user approval before restart (human-in-the-loop)
5. Execute approved restart (write operation - approved)

Should I add this feature with the human-approval workflow?
```

---

Now, please tell me what feature you'd like to add to the roadmap!
