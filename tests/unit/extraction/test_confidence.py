"""Unit tests for confidence calculation algorithms."""

from haia.extraction.confidence import (
    ConfidenceCalculator,
    calculate_confidence,
    detect_correction_patterns,
    detect_multi_mentions,
)


class TestConfidenceCalculator:
    """Tests for ConfidenceCalculator class."""

    def test_base_confidence_only(self):
        """Test calculation with only base confidence."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(base_confidence=0.6)
        assert result == 0.6

    def test_explicit_boost(self):
        """Test explicit statement boost (+0.1)."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(base_confidence=0.6, is_explicit=True)
        assert result == 0.7

    def test_multi_mention_boost_single_extra(self):
        """Test multi-mention boost with 2 mentions (+0.05)."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(base_confidence=0.6, mention_count=2)
        assert result == 0.65

    def test_multi_mention_boost_multiple(self):
        """Test multi-mention boost with 3 mentions (+0.10)."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(base_confidence=0.6, mention_count=3)
        assert result == 0.7

    def test_multi_mention_boost_capped(self):
        """Test multi-mention boost is capped at +0.2."""
        calculator = ConfidenceCalculator()
        # 5 mentions would be +0.20, 10 mentions would still cap at +0.2
        result = calculator.calculate(base_confidence=0.5, mention_count=10)
        assert result == 0.7  # 0.5 + 0.2 (capped)

    def test_contradiction_penalty(self):
        """Test contradiction penalty (-0.3)."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(base_confidence=0.8, has_contradiction=True)
        assert result == 0.5

    def test_correction_override(self):
        """Test correction pattern overrides to fixed 0.8."""
        calculator = ConfidenceCalculator()
        # Base confidence should be ignored
        result = calculator.calculate(base_confidence=0.3, is_correction=True)
        assert result == 0.8

    def test_correction_override_ignores_other_factors(self):
        """Test correction ignores all other factors."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(
            base_confidence=0.5,
            is_correction=True,
            is_explicit=True,
            mention_count=5,
            has_contradiction=True,
        )
        assert result == 0.8  # All other factors ignored

    def test_combined_boosts(self):
        """Test combining explicit + multi-mention boosts."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(
            base_confidence=0.5, is_explicit=True, mention_count=3
        )
        # 0.5 + 0.1 (explicit) + 0.1 (2 extra mentions) = 0.7
        assert result == 0.7

    def test_boost_with_contradiction(self):
        """Test boosts with contradiction penalty."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(
            base_confidence=0.7,
            is_explicit=True,
            mention_count=2,
            has_contradiction=True,
        )
        # 0.7 + 0.1 (explicit) + 0.05 (1 extra mention) - 0.3 (contradiction) = 0.55
        assert result == 0.55

    def test_clamping_upper_bound(self):
        """Test confidence is clamped to 1.0."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(
            base_confidence=0.9, is_explicit=True, mention_count=5
        )
        # 0.9 + 0.1 + 0.2 (capped) = 1.2, should clamp to 1.0
        assert result == 1.0

    def test_clamping_lower_bound(self):
        """Test confidence is clamped to 0.0."""
        calculator = ConfidenceCalculator()
        result = calculator.calculate(base_confidence=0.2, has_contradiction=True)
        # 0.2 - 0.3 = -0.1, should clamp to 0.0
        assert result == 0.0

    def test_custom_parameters(self):
        """Test calculator with custom parameters."""
        calculator = ConfidenceCalculator(
            explicit_boost=0.2,
            multi_mention_boost=0.1,
            contradiction_penalty=0.4,
            correction_confidence=0.9,
        )
        result = calculator.calculate(base_confidence=0.5, is_explicit=True)
        assert result == 0.7  # 0.5 + 0.2 (custom explicit_boost)

        result_correction = calculator.calculate(
            base_confidence=0.5, is_correction=True
        )
        assert result_correction == 0.9  # Custom correction_confidence


class TestCalculateConfidenceFunction:
    """Tests for calculate_confidence convenience function."""

    def test_convenience_function_basic(self):
        """Test convenience function with basic parameters."""
        result = calculate_confidence(base=0.6)
        assert result == 0.6

    def test_convenience_function_explicit(self):
        """Test convenience function with explicit boost."""
        result = calculate_confidence(base=0.7, is_explicit=True)
        assert abs(result - 0.8) < 0.0001  # Floating point tolerance

    def test_convenience_function_multi_mention(self):
        """Test convenience function with mention count."""
        result = calculate_confidence(base=0.6, mention_count=3)
        assert result == 0.7

    def test_convenience_function_contradiction(self):
        """Test convenience function with contradiction."""
        result = calculate_confidence(base=0.8, has_contradiction=True)
        assert result == 0.5

    def test_convenience_function_correction(self):
        """Test convenience function with correction."""
        result = calculate_confidence(base=0.5, is_correction=True)
        assert result == 0.8


class TestDetectCorrectionPatterns:
    """Tests for detect_correction_patterns function."""

    def test_detects_actually(self):
        """Test detection of 'actually' pattern."""
        assert detect_correction_patterns("Actually, I meant Docker not Podman")
        assert detect_correction_patterns("I ACTUALLY prefer vim")

    def test_detects_i_meant(self):
        """Test detection of 'i meant' pattern."""
        assert detect_correction_patterns("I meant Docker, not Podman")
        assert detect_correction_patterns("What I meant was...")

    def test_detects_correction(self):
        """Test detection of 'correction' keyword."""
        assert detect_correction_patterns("Correction: it's Docker")
        assert detect_correction_patterns("Let me make a correction")

    def test_detects_sorry(self):
        """Test detection of 'sorry' pattern."""
        assert detect_correction_patterns("Sorry, I misspoke earlier")

    def test_detects_no_wait(self):
        """Test detection of 'no wait' pattern."""
        assert detect_correction_patterns("No wait, that's wrong")

    def test_detects_to_be_clear(self):
        """Test detection of 'to be clear' pattern."""
        assert detect_correction_patterns("To be clear, I use Docker")

    def test_detects_not_pattern(self):
        """Test detection of 'not' in context."""
        assert detect_correction_patterns("I use Docker not Podman")

    def test_no_detection_normal_text(self):
        """Test no false positives on normal text."""
        assert not detect_correction_patterns("I prefer Docker")
        assert not detect_correction_patterns("Docker is great for containers")

    def test_case_insensitive(self):
        """Test case-insensitive detection."""
        assert detect_correction_patterns("ACTUALLY I meant docker")
        assert detect_correction_patterns("Actually I Meant Docker")


class TestDetectMultiMentions:
    """Tests for detect_multi_mentions function."""

    def test_single_mention(self):
        """Test content mentioned once."""
        content = "User prefers Docker"
        messages = [
            {"content": "I like Docker for my homelab", "speaker": "user"},
            {"content": "Kubernetes is also good", "speaker": "user"},
        ]
        count = detect_multi_mentions(content, messages)
        assert count == 1

    def test_multiple_mentions(self):
        """Test content mentioned multiple times."""
        content = "User prefers Docker"
        messages = [
            {"content": "I prefer Docker for containers", "speaker": "user"},
            {"content": "I use Docker daily", "speaker": "assistant"},
            {"content": "Docker is great", "speaker": "user"},
        ]
        count = detect_multi_mentions(content, messages)
        assert count == 3

    def test_no_mentions(self):
        """Test content not mentioned (returns minimum 1)."""
        content = "User prefers Kubernetes"
        messages = [
            {"content": "I like Docker", "speaker": "user"},
            {"content": "Podman is interesting", "speaker": "user"},
        ]
        count = detect_multi_mentions(content, messages)
        assert count == 1  # Minimum is 1

    def test_partial_keyword_match(self):
        """Test matching with partial keywords."""
        content = "User has Proxmox cluster"
        messages = [
            {"content": "My Proxmox setup is great", "speaker": "user"},
            {"content": "I have a 3-node cluster", "speaker": "user"},
            {"content": "Tell me about Proxmox", "speaker": "assistant"},
        ]
        count = detect_multi_mentions(content, messages)
        assert count >= 2  # Should match 'Proxmox' and 'cluster'

    def test_filters_short_words(self):
        """Test that short words are filtered out."""
        content = "I use Docker and Podman"
        messages = [
            {"content": "I like Docker", "speaker": "user"},
            {"content": "Podman is great", "speaker": "user"},
        ]
        # "I", "use", "and" should be filtered (≤4 chars)
        # "Docker" and "Podman" should be kept (>4 chars)
        count = detect_multi_mentions(content, messages)
        assert count == 2  # Both messages contain key terms

    def test_empty_content_returns_one(self):
        """Test empty content returns minimum count."""
        content = "a b c"  # All short words filtered
        messages = [{"content": "Some message", "speaker": "user"}]
        count = detect_multi_mentions(content, messages)
        assert count == 1

    def test_case_insensitive_matching(self):
        """Test case-insensitive keyword matching."""
        content = "User prefers Docker"
        messages = [
            {"content": "I prefer DOCKER", "speaker": "user"},
            {"content": "docker is great", "speaker": "user"},
        ]
        count = detect_multi_mentions(content, messages)
        assert count == 2
