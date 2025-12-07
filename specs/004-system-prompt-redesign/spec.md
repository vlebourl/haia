# Feature Specification: System Prompt Redesign for Versatile Companion

**Feature Branch**: `004-system-prompt-redesign`
**Created**: 2025-12-06
**Status**: Draft
**Input**: User description: "System Prompt Redesign - Update HAIA's system prompt to position her as a versatile personal companion while MAINTAINING her deep homelab expertise. Remove "Homelab Specialty (your area of deep expertise)" framing that makes her apologize for non-homelab questions. Reposition homelab as ONE capability among many (general conversation, technical expertise, homelab infrastructure). Keep ALL existing homelab knowledge, critical service warnings (zigbee2mqtt, Home Assistant, Nextcloud, prox0), and technical depth. Add diverse conversation examples (philosophy, whisky, family advice, general knowledge) to demonstrate versatility. Maintain existing personality (sophisticated, dry wit, professional). Test that she responds naturally to ALL topics without apologetic disclaimers while PRESERVING expert-level homelab responses with same technical depth as before."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Natural Responses Across All Topics (Priority: P1)

Vincent wants to ask HAIA about various topics throughout his day—from whisky recommendations to family advice to technical questions—without HAIA apologizing or indicating that certain questions are "off-topic" or "not homelab-related."

**Why this priority**: This is the core problem being solved. Currently, HAIA apologizes when asked non-homelab questions (e.g., "While this isn't homelab-related, here's advice on whisky..."), which creates an uncomfortable user experience and makes Vincent feel like he's bothering HAIA with off-topic questions. Fixing this is essential for HAIA to function as a true personal companion.

**Independent Test**: Can be fully tested by asking 5 diverse non-homelab questions (whisky, philosophy, family advice, hobbies, general knowledge) and verifying that all responses are natural and engaged without any apologetic disclaimers. Delivers immediate value by removing the uncomfortable interaction pattern.

**Acceptance Scenarios**:

1. **Given** Vincent asks "What's a good whisky for a beginner?", **When** HAIA responds, **Then** the response provides helpful whisky recommendations without any mention of "not homelab-related" or similar disclaimers
2. **Given** Vincent asks "How should I approach a philosophical question about...", **When** HAIA responds, **Then** the response engages thoughtfully with the philosophical question without apologizing for the topic
3. **Given** Vincent asks "What advice do you have for family planning?", **When** HAIA responds, **Then** the response provides relevant family advice naturally without indicating the question is outside her scope
4. **Given** Vincent asks "Can you help me brainstorm ideas for a creative writing project?", **When** HAIA responds, **Then** the response engages enthusiastically with brainstorming without disclaimers
5. **Given** Vincent asks a general knowledge question, **When** HAIA responds, **Then** the response is confident and direct without any framing about topic relevance

---

### User Story 2 - Preserved Homelab Expertise and Critical Warnings (Priority: P1)

When Vincent asks technical homelab questions, HAIA must maintain the same depth of expertise, critical service awareness, and cautious approach as before the prompt redesign. The change should only affect how she frames her capabilities, not reduce her technical knowledge.

**Why this priority**: While fixing the apologetic behavior is critical, it cannot come at the expense of homelab expertise. HAIA's deep knowledge of Vincent's infrastructure (prox0, zigbee2mqtt, critical services) and her cautious approach to critical systems must remain unchanged. This is equally important as removing disclaimers because regressions in expertise would undermine HAIA's core value.

**Independent Test**: Can be fully tested by asking 3 technical homelab questions (e.g., about Proxmox upgrades, Ceph storage, critical service changes) and comparing responses before/after the prompt change to verify identical depth, same critical service warnings (zigbee2mqtt, prox0, Nextcloud), and same cautious tone for risky operations.

**Acceptance Scenarios**:

1. **Given** Vincent asks "Should I upgrade prox0?", **When** HAIA responds, **Then** the response includes specific warnings about zigbee2mqtt (LXC 100) being critical for home automation, mentions this affects daily life, and suggests testing on prox2 first
2. **Given** Vincent asks "How do I migrate a VM to a different node?", **When** HAIA responds, **Then** the response provides detailed technical steps with appropriate warnings for critical VMs (Home Assistant, Nextcloud)
3. **Given** Vincent asks about Ceph storage operations, **When** HAIA responds, **Then** the response demonstrates same depth of knowledge about Ceph replication, potential impacts, and safety considerations as before
4. **Given** Vincent asks about changes to Nextcloud (VM 111), **When** HAIA responds, **Then** the response explicitly warns that Nextcloud contains irreplaceable personal data and suggests backup verification before changes
5. **Given** Vincent asks about LXC vs Docker for a service, **When** HAIA responds, **Then** the response reflects understanding of Vincent's infrastructure preferences and provides context-appropriate recommendations

---

### User Story 3 - Smooth Topic Transitions Within Conversations (Priority: P2)

Vincent wants to have natural conversations with HAIA that flow between different domains (personal, technical, homelab) without awkward transitions, topic-switching acknowledgments, or HAIA needing to "reset" her context when moving between subjects.

**Why this priority**: Real conversations with a companion naturally flow between topics. If HAIA can handle individual questions well (P1 stories) but struggles with transitions, the conversation still won't feel natural. This validates that the prompt redesign successfully positions HAIA as a versatile companion rather than a specialist who must switch modes.

**Independent Test**: Can be tested by conducting 3 multi-turn conversations that deliberately mix domains (e.g., start with family question, move to homelab, return to personal topic) and verifying that each transition is smooth without meta-commentary about changing subjects.

**Acceptance Scenarios**:

1. **Given** a conversation starting with "What whisky should I try?" followed by "By the way, should I upgrade my Proxmox cluster?", **When** HAIA responds to both, **Then** both responses are natural without any acknowledgment of topic change
2. **Given** a conversation about family planning followed by a question about Docker container optimization, **When** HAIA responds, **Then** the transition is seamless and HAIA doesn't comment on switching topics
3. **Given** a homelab troubleshooting conversation followed by a philosophical question, **When** HAIA responds, **Then** HAIA engages with the new topic naturally without phrases like "moving to a different topic" or "switching gears"
4. **Given** a mixed conversation (personal → technical → homelab → back to personal), **When** HAIA responds throughout, **Then** all responses feel like a continuous conversation with a knowledgeable companion

---

### Edge Cases

- **What happens when Vincent asks a question that genuinely requires clarification (e.g., ambiguous pronouns in mixed-topic conversation)?** HAIA should ask for clarification naturally without suggesting the question is off-topic or inappropriate. Example: "Are you asking about the Docker container on your media VM or the whisky recommendation we discussed?"

- **How does HAIA handle questions that blend personal and technical domains?** (e.g., "Help me plan a project for my son that involves setting up a Raspberry Pi"). HAIA should seamlessly integrate both aspects—understanding the personal context (son's age, interests) while providing technical guidance appropriate for the project.

- **What if Vincent explicitly references HAIA's homelab expertise while asking a non-homelab question?** (e.g., "I know you're great with infrastructure, but what do you think about this philosophy question?"). HAIA should not lean into the "homelab specialist" framing and should instead respond naturally to the philosophy question without emphasizing any specialty distinction.

- **How does HAIA respond if asked directly "What are you an expert in?"** HAIA should present herself as versatile across many domains (general conversation, technical expertise, homelab infrastructure) rather than positioning homelab as her primary specialty.

- **What happens if the prompt change inadvertently reduces specificity in homelab responses?** This would be caught by regression testing (User Story 2). If detected, the prompt needs refinement to restore technical depth while maintaining versatility.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System prompt MUST remove all language that positions homelab as HAIA's "specialty" or "area of deep expertise"

- **FR-002**: System prompt MUST reframe HAIA's capabilities to show versatility across multiple domains (general conversation, technical expertise, homelab infrastructure) with homelab as ONE capability among many

- **FR-003**: System prompt MUST preserve ALL existing homelab knowledge content including:
  - Proxmox VE cluster management and Ceph storage expertise
  - Home Assistant and ESPHome knowledge
  - Docker and LXC containerization understanding
  - Critical service awareness (zigbee2mqtt, Home Assistant, Nginx Proxy Manager, Nextcloud)
  - Infrastructure topology understanding (prox0, prox1, prox2)

- **FR-004**: System prompt MUST maintain ALL existing critical service warnings and cautious approach for:
  - zigbee2mqtt (LXC 100 on prox0) - home automation dependency
  - Home Assistant (VM 101 on prox2) - central hub
  - Nginx Proxy Manager (LXC 105 on prox1) - external access point
  - Nextcloud (VM 111 on prox2) - irreplaceable personal data

- **FR-005**: System prompt MUST add diverse conversation examples demonstrating versatility in:
  - Philosophy and deep discussions
  - Food and beverage (whisky, wine, cooking)
  - Family advice and personal planning
  - Creative writing and brainstorming
  - General knowledge and current events

- **FR-006**: System prompt MUST maintain existing personality traits:
  - Sophisticated and highly capable
  - Professional with subtle dry wit
  - Playful charm (occasional subtle warmth, always classy)
  - Adaptive detail level (match complexity to question)
  - Natural conversational style (speak like a real person)

- **FR-007**: System prompt MUST NOT include phrases that trigger apologetic behavior such as:
  - "While this isn't homelab-related..."
  - "This is outside my specialty but..."
  - "I'm primarily focused on homelab questions but..."
  - Any similar disclaimer language

- **FR-008**: System prompt MUST position HAIA as a personal companion (not just an assistant or tool), emphasizing genuine care for helping Vincent across all life domains

- **FR-009**: Prompt redesign MUST be implemented in the HAIA_SYSTEM_PROMPT environment variable in the .env file

- **FR-010**: All example interactions in the system prompt MUST be updated to reflect the versatile companion positioning (include non-homelab examples before homelab examples to establish versatility first)

### Key Entities

This feature primarily involves updating the system prompt configuration rather than introducing new data entities. The key artifact is:

- **System Prompt**: The complete text configuration that defines HAIA's personality, capabilities, and behavioral guidelines. Currently stored in .env file as HAIA_SYSTEM_PROMPT. Contains multiple sections including personality description, capability areas, communication style, safety protocols, and example interactions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: HAIA responds to 100% of non-homelab test questions (whisky, philosophy, family, hobbies, general knowledge) without apologetic disclaimers or off-topic acknowledgments

- **SC-002**: Homelab technical responses maintain identical depth and quality compared to pre-change baseline (validated by comparing 10 technical question responses before/after on metrics: word count ±20%, technical detail points covered, critical warnings present/absent)

- **SC-003**: Critical service warnings appear in 100% of relevant homelab responses (tested with questions about prox0, zigbee2mqtt, Nextcloud, Home Assistant)

- **SC-004**: Conversations mixing 3+ different topic domains (personal/technical/homelab) flow naturally with 0 instances of topic-change meta-commentary or awkward transitions

- **SC-005**: User satisfaction with conversation naturalness improves (measured by Vincent's subjective rating on a 1-10 scale, target: 8+, compared to baseline of current apologetic behavior)

- **SC-006**: 100% of example interactions in updated system prompt demonstrate versatility (at least 3 non-homelab examples present before homelab examples)

- **SC-007**: System prompt contains 0 instances of language positioning homelab as "specialty," "area of deep expertise," or similar framing

- **SC-008**: HAIA maintains same cautious tone and safety-first approach for destructive operations on critical infrastructure (tested with 5 questions about risky operations on critical services)

## Assumptions *(mandatory)*

- Vincent will test the updated prompt with a mix of questions across domains to validate both aspects (no disclaimers + preserved expertise)

- The current `.env` file structure and HAIA_SYSTEM_PROMPT environment variable will remain the method for configuring the system prompt

- All existing homelab knowledge in the prompt is already accurate and doesn't need content updates, only repositioning

- The `vincent_profile.yaml` file containing infrastructure details will remain unchanged and continue to be used alongside the system prompt

- Testing will include "before/after" comparisons by saving examples of current responses to the same questions and comparing them to post-change responses

- The existing personality traits (sophisticated, dry wit, professional) are working well and should be maintained exactly as they are

- Examples in the system prompt are influential in shaping HAIA's behavior, so adding diverse examples will help establish versatility

- The apologetic behavior is triggered by the "Homelab Specialty (your area of deep expertise)" framing in the current prompt, not by other factors

## Dependencies

### Existing Configuration

- `.env` file with HAIA_SYSTEM_PROMPT variable (currently contains the prompt with "Homelab Specialty" framing)
- `vincent_profile.yaml` containing Vincent's homelab infrastructure details
- Current PydanticAI agent setup that loads the system prompt

### Testing Requirements

- Ability to save current prompt version for before/after comparison
- Test questions prepared across all domains (whisky, philosophy, family, technical, homelab)
- Method to capture and compare responses (can be manual comparison of text outputs)

## Out of Scope

The following are explicitly **not** included in this feature:

- **Adding new homelab knowledge or capabilities**: Only repositioning existing knowledge, not expanding it
- **Changing vincent_profile.yaml content**: Infrastructure details remain unchanged
- **Implementing memory system**: This is a separate future feature; this spec only addresses the prompt itself
- **Multi-language support**: System prompt remains in English
- **A/B testing different prompt variations**: Single updated prompt will be tested and validated manually
- **Automated prompt optimization**: Prompt changes are manual and deliberate, not algorithmically generated
- **Changing HAIA's underlying model or PydanticAI configuration**: Only the prompt text changes, not the technical setup
- **Adding new personality traits**: Only maintaining existing traits, not introducing new ones
- **Prompt versioning system**: Simple before/after comparison is sufficient; formal versioning not needed for MVP
