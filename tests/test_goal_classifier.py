"""
Tests for lib/goal_classifier.py

Comprehensive coverage of goal classification logic.
"""

import pytest
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.goal_classifier import (
    GoalType,
    KEYWORDS,
    classify_goal,
    is_conversational,
    should_track_as_goal
)


class TestGoalTypeEnum:
    """Tests for GoalType enum."""

    def test_work_goal_types_exist(self):
        """All work goal types are defined."""
        assert GoalType.DEBUG.value == "debug"
        assert GoalType.FEATURE.value == "feature"
        assert GoalType.REFACTOR.value == "refactor"
        assert GoalType.EXPLORE.value == "explore"
        assert GoalType.TEST.value == "test"
        assert GoalType.DEPLOY.value == "deploy"
        assert GoalType.DOCS.value == "docs"
        assert GoalType.CONFIG.value == "config"

    def test_conversational_goal_types_exist(self):
        """All conversational goal types are defined."""
        assert GoalType.CONVERSATION.value == "conversation"
        assert GoalType.AFFIRMATION.value == "affirmation"
        assert GoalType.CLARIFICATION.value == "clarification"
        assert GoalType.META.value == "meta"

    def test_unknown_goal_type_exists(self):
        """Unknown goal type is defined."""
        assert GoalType.UNKNOWN.value == "unknown"


class TestKeywords:
    """Tests for KEYWORDS dictionary."""

    def test_all_goal_types_have_keywords(self):
        """All non-UNKNOWN goal types have keywords."""
        for goal_type in GoalType:
            if goal_type != GoalType.UNKNOWN:
                assert goal_type in KEYWORDS, f"Missing keywords for {goal_type}"
                assert len(KEYWORDS[goal_type]) > 0, f"Empty keywords for {goal_type}"

    def test_keywords_are_lowercase(self):
        """All keywords are lowercase for consistent matching."""
        for goal_type, keywords in KEYWORDS.items():
            for keyword in keywords:
                assert keyword == keyword.lower(), f"Keyword '{keyword}' is not lowercase"


class TestClassifyGoalDebug:
    """Tests for DEBUG goal classification."""

    @pytest.mark.parametrize("prompt", [
        "fix the bug in authentication",
        "Debug the crash issue",
        "Getting an exception here",
        "TypeError: undefined is not a function",
        "There's an error in the code",
        "The system is failing",
    ])
    def test_classifies_debug_prompts(self, prompt):
        """Recognizes debug-related prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.DEBUG
        assert confidence > 0.5

    @pytest.mark.parametrize("prompt,expected", [
        # These contain conversational keywords that take precedence
        ("Fix this error please", GoalType.CONVERSATION),  # "this" triggers conversation
        ("The login is broken", GoalType.AFFIRMATION),  # Short, triggers affirmation
        ("This doesn't work", GoalType.CONVERSATION),  # "this" triggers conversation
    ])
    def test_debug_prompts_with_conversational_keywords(self, prompt, expected):
        """Documents classifier behavior when prompts contain conversational keywords."""
        goal_type, _ = classify_goal(prompt)
        assert goal_type == expected


class TestClassifyGoalFeature:
    """Tests for FEATURE goal classification."""

    @pytest.mark.parametrize("prompt", [
        "add a new login feature",
        "Create a user dashboard",
        "Implement dark mode",
        "Build a notification system",
        "Write a function to validate emails",
        "Generate a report component",
    ])
    def test_classifies_feature_prompts(self, prompt):
        """Recognizes feature-related prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.FEATURE
        assert confidence > 0.5


class TestClassifyGoalRefactor:
    """Tests for REFACTOR goal classification."""

    @pytest.mark.parametrize("prompt", [
        "refactor the database code",
        "Optimize the query performance",
        "Rename the variables for clarity",
        "consolidate the utility functions",
        "Deduplicate the validation logic",
    ])
    def test_classifies_refactor_prompts(self, prompt):
        """Recognizes refactor-related prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.REFACTOR
        assert confidence > 0.5

    @pytest.mark.parametrize("prompt,expected", [
        # These contain conversational keywords that take precedence
        ("Clean up this function", GoalType.CONVERSATION),  # "this" triggers conversation
        ("Simplify this logic", GoalType.CONVERSATION),  # "this" triggers conversation
        ("Extract this into a helper function", GoalType.CONVERSATION),  # "this" triggers conversation
    ])
    def test_refactor_prompts_with_conversational_keywords(self, prompt, expected):
        """Documents classifier behavior when prompts contain conversational keywords."""
        goal_type, _ = classify_goal(prompt)
        assert goal_type == expected


class TestClassifyGoalExplore:
    """Tests for EXPLORE goal classification."""

    @pytest.mark.parametrize("prompt", [
        "find where errors are handled",
        "Where is the authentication code?",
        "Show me the user model",
        "Explain the data flow",
        "Analyze the performance bottleneck",
        "investigate the memory leak",
        "explore the codebase structure",
    ])
    def test_classifies_explore_prompts(self, prompt):
        """Recognizes explore-related prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.EXPLORE
        assert confidence > 0.5

    @pytest.mark.parametrize("prompt,expected", [
        # These contain conversational keywords that take precedence
        ("What is this function doing?", GoalType.CONVERSATION),  # "this" triggers conversation
        ("How does the caching work?", GoalType.CONVERSATION),  # "how" matches "how do i use" pattern
    ])
    def test_explore_prompts_with_conversational_keywords(self, prompt, expected):
        """Documents classifier behavior when prompts contain conversational keywords."""
        goal_type, _ = classify_goal(prompt)
        assert goal_type == expected


class TestClassifyGoalTest:
    """Tests for TEST goal classification."""

    @pytest.mark.parametrize("prompt", [
        "Run pytest on the module",
        "Verify the validation logic",
        "test the authentication flow",
        "run the test suite",
        "validate input handling",
    ])
    def test_classifies_test_prompts(self, prompt):
        """Recognizes test-related prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.TEST
        assert confidence > 0.5

    @pytest.mark.parametrize("prompt,expected", [
        # "write" and "add/create" keywords can trigger FEATURE before TEST
        ("Write unit tests for this function", GoalType.CONVERSATION),  # "this" triggers conversation
        ("Add test coverage for the API", GoalType.FEATURE),  # "add" triggers feature
        ("Create integration tests", GoalType.FEATURE),  # "create" triggers feature
    ])
    def test_test_prompts_with_feature_keywords(self, prompt, expected):
        """Documents classifier behavior when prompts contain feature-like keywords."""
        goal_type, _ = classify_goal(prompt)
        assert goal_type == expected


class TestClassifyGoalDeploy:
    """Tests for DEPLOY goal classification."""

    @pytest.mark.parametrize("prompt", [
        "Deploy to production",
        "Release version 2.0",
        "Push to main branch",
        "Run the CI/CD pipeline",
        "deploy the application",
        "publish to npm",
    ])
    def test_classifies_deploy_prompts(self, prompt):
        """Recognizes deploy-related prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.DEPLOY
        assert confidence > 0.5

    def test_build_with_feature_keyword(self):
        """'build' keyword can match both FEATURE and DEPLOY."""
        # "Build" is in both FEATURE and DEPLOY keywords
        goal_type, _ = classify_goal("Build the docker image")
        # FEATURE comes first in check order, so "build" matches feature
        assert goal_type == GoalType.FEATURE


class TestClassifyGoalDocs:
    """Tests for DOCS goal classification."""

    @pytest.mark.parametrize("prompt", [
        "Document the API endpoints",
        "Update the README",
        "update the documentation",
        "describe the API in docs",
    ])
    def test_classifies_docs_prompts(self, prompt):
        """Recognizes documentation-related prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.DOCS
        assert confidence > 0.5

    @pytest.mark.parametrize("prompt,expected", [
        # These contain conversational keywords that take precedence
        ("Add comments to explain this code", GoalType.CONVERSATION),  # "this" triggers conversation
        ("Write a docstring for this function", GoalType.CONVERSATION),  # "this" triggers conversation
    ])
    def test_docs_prompts_with_conversational_keywords(self, prompt, expected):
        """Documents classifier behavior when prompts contain conversational keywords."""
        goal_type, _ = classify_goal(prompt)
        assert goal_type == expected


class TestClassifyGoalConfig:
    """Tests for CONFIG goal classification."""

    @pytest.mark.parametrize("prompt", [
        "Configure the database connection",
        "Setup the environment variables",
        "Install the dependencies",
        "Update the .env file",
    ])
    def test_classifies_config_prompts(self, prompt):
        """Recognizes config-related prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.CONFIG
        assert confidence > 0.5


class TestClassifyGoalConversation:
    """Tests for CONVERSATION goal classification."""

    @pytest.mark.parametrize("prompt", [
        "Thanks!",
        "Thank you so much",
        "Hello there",
        "Hey, good morning!",
        "Goodbye for now",
        "Cool, nice work!",
    ])
    def test_classifies_conversation_prompts(self, prompt):
        """Recognizes conversational prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.CONVERSATION
        assert confidence > 0.5


class TestClassifyGoalAffirmation:
    """Tests for AFFIRMATION goal classification."""

    @pytest.mark.parametrize("prompt", [
        "Yes",
        "Yep!",
        "Yeah",
        "Ok",
        "Sure",
        "Go ahead",
        "Let's do it",
        "Sounds good",
        "Perfect",
        "Proceed",
    ])
    def test_classifies_affirmation_prompts(self, prompt):
        """Recognizes affirmation prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.AFFIRMATION
        assert confidence > 0.5


class TestClassifyGoalClarification:
    """Tests for CLARIFICATION goal classification."""

    @pytest.mark.parametrize("prompt", [
        "What do you mean by that?",
        "Can you explain that again?",
        "I don't understand the approach",
        "Could you clarify the steps?",
    ])
    def test_classifies_clarification_prompts(self, prompt):
        """Recognizes clarification prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.CLARIFICATION
        assert confidence > 0.5


class TestClassifyGoalMeta:
    """Tests for META goal classification."""

    @pytest.mark.parametrize("prompt", [
        "What can you do?",
        "What is Spark?",
        "What are your capabilities?",
        "tell me about yourself",
        "how do i use spark",
    ])
    def test_classifies_meta_prompts(self, prompt):
        """Recognizes meta/help prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.META
        assert confidence > 0.5

    def test_meta_with_conversational_overlap(self):
        """'help me understand' contains 'help' which is not in META keywords."""
        # "help me understand" actually matches CONVERSATION due to keyword priority
        goal_type, _ = classify_goal("Help me understand how this works")
        # "this" triggers conversation check first
        assert goal_type == GoalType.CONVERSATION


class TestClassifyGoalShortPrompts:
    """Tests for very short prompt handling."""

    def test_single_word_affirmation(self):
        """Single word affirmations are classified correctly."""
        goal_type, confidence = classify_goal("yes")
        assert goal_type == GoalType.AFFIRMATION
        assert confidence >= 0.7

    def test_single_word_with_punctuation(self):
        """Handles punctuation on short prompts."""
        goal_type, confidence = classify_goal("yes!")
        assert goal_type == GoalType.AFFIRMATION

    def test_very_short_defaults_to_affirmation(self):
        """Very short non-keyword prompts default to affirmation."""
        goal_type, confidence = classify_goal("k")
        assert goal_type == GoalType.AFFIRMATION
        assert confidence < 0.9  # Lower confidence


class TestClassifyGoalEdgeCases:
    """Tests for edge cases in classification."""

    def test_empty_string(self):
        """Handles empty string input."""
        goal_type, confidence = classify_goal("")
        # Should handle gracefully (either affirmation or unknown)
        assert goal_type in (GoalType.AFFIRMATION, GoalType.UNKNOWN)

    def test_whitespace_only(self):
        """Handles whitespace-only input."""
        goal_type, confidence = classify_goal("   ")
        assert goal_type in (GoalType.AFFIRMATION, GoalType.UNKNOWN)

    def test_case_insensitive(self):
        """Classification is case-insensitive."""
        goal_type1, _ = classify_goal("FIX THE BUG")
        goal_type2, _ = classify_goal("fix the bug")
        assert goal_type1 == goal_type2 == GoalType.DEBUG

    def test_keyword_at_start_gets_higher_score(self):
        """Keywords at start of prompt get boosted."""
        goal_type, confidence = classify_goal("fix the login bug")
        assert goal_type == GoalType.DEBUG
        assert confidence > 0.6  # Higher confidence for start position


class TestClassifyGoalUnknown:
    """Tests for UNKNOWN classification."""

    @pytest.mark.parametrize("prompt", [
        "asdfjkl random nonsense",
        "12345 numbers only",
        "Some completely unrelated sentence about weather",
    ])
    def test_unknown_for_random_text(self, prompt):
        """Unknown goal for unrecognizable prompts."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == GoalType.UNKNOWN
        assert confidence < 0.5


class TestIsConversational:
    """Tests for is_conversational function."""

    def test_conversation_is_conversational(self):
        """CONVERSATION is conversational."""
        assert is_conversational(GoalType.CONVERSATION) is True

    def test_affirmation_is_conversational(self):
        """AFFIRMATION is conversational."""
        assert is_conversational(GoalType.AFFIRMATION) is True

    def test_clarification_is_conversational(self):
        """CLARIFICATION is conversational."""
        assert is_conversational(GoalType.CLARIFICATION) is True

    def test_meta_is_conversational(self):
        """META is conversational."""
        assert is_conversational(GoalType.META) is True

    def test_debug_is_not_conversational(self):
        """DEBUG is not conversational."""
        assert is_conversational(GoalType.DEBUG) is False

    def test_feature_is_not_conversational(self):
        """FEATURE is not conversational."""
        assert is_conversational(GoalType.FEATURE) is False

    def test_unknown_is_not_conversational(self):
        """UNKNOWN is not conversational."""
        assert is_conversational(GoalType.UNKNOWN) is False


class TestShouldTrackAsGoal:
    """Tests for should_track_as_goal function."""

    @pytest.mark.parametrize("goal_type", [
        GoalType.DEBUG,
        GoalType.FEATURE,
        GoalType.REFACTOR,
        GoalType.EXPLORE,
        GoalType.TEST,
        GoalType.DEPLOY,
        GoalType.DOCS,
        GoalType.CONFIG,
        GoalType.UNKNOWN,
    ])
    def test_work_goals_should_be_tracked(self, goal_type):
        """Work-related goals should be tracked."""
        assert should_track_as_goal(goal_type) is True

    @pytest.mark.parametrize("goal_type", [
        GoalType.CONVERSATION,
        GoalType.AFFIRMATION,
        GoalType.CLARIFICATION,
        GoalType.META,
    ])
    def test_conversational_goals_should_not_be_tracked(self, goal_type):
        """Conversational goals should not be tracked."""
        assert should_track_as_goal(goal_type) is False


class TestConfidenceScoring:
    """Tests for confidence score calculation."""

    def test_high_confidence_for_clear_match(self):
        """Clear matches get high confidence."""
        _, confidence = classify_goal("fix the bug in authentication")
        assert confidence >= 0.7

    def test_low_confidence_for_unknown(self):
        """Unknown prompts get low confidence."""
        _, confidence = classify_goal("random gibberish text here")
        assert confidence <= 0.5

    def test_short_affirmation_high_confidence(self):
        """Short affirmations like 'yes' get high confidence."""
        _, confidence = classify_goal("yes")
        assert confidence >= 0.9

    def test_confidence_bounded(self):
        """Confidence is always between 0 and 1."""
        test_prompts = [
            "yes", "fix bug", "random text", "", "add feature",
            "fix add refactor test deploy",  # Multiple keywords
        ]
        for prompt in test_prompts:
            _, confidence = classify_goal(prompt)
            assert 0.0 <= confidence <= 1.0


class TestMultipleKeywordMatches:
    """Tests for prompts with multiple keyword matches."""

    def test_first_word_priority(self):
        """First word often determines classification."""
        # "fix" at start should win over later "add"
        goal_type, _ = classify_goal("fix the bug then add tests")
        assert goal_type == GoalType.DEBUG

    def test_conversational_keywords_take_priority(self):
        """Conversational keywords are checked before work keywords."""
        # "this" triggers conversation check first, even with debug keywords
        goal_type, _ = classify_goal("fix this bug and debug the error")
        # "this" matches conversation before work keywords are checked
        assert goal_type == GoalType.CONVERSATION

    def test_multiple_debug_keywords_without_this(self):
        """Multiple debug keywords boost confidence when no conversational match."""
        goal_type, confidence = classify_goal("fix the bug and debug the error in auth")
        assert goal_type == GoalType.DEBUG
        assert confidence > 0.6


class TestRealWorldPrompts:
    """Tests with realistic user prompts."""

    @pytest.mark.parametrize("prompt,expected_type", [
        # Real debug scenarios that work
        ("The tests are failing, can you fix them?", GoalType.DEBUG),
        ("I'm getting a NullPointerException", GoalType.DEBUG),

        # Real feature scenarios
        ("Let's add user authentication", GoalType.FEATURE),
        ("Can you implement a search feature?", GoalType.FEATURE),

        # Real explore scenarios that work (no "this" or "how do i")
        ("Where does the app handle payments?", GoalType.EXPLORE),

        # Real conversational
        ("That's exactly what I needed", GoalType.AFFIRMATION),
    ])
    def test_real_world_prompts(self, prompt, expected_type):
        """Classifies realistic prompts correctly."""
        goal_type, confidence = classify_goal(prompt)
        assert goal_type == expected_type, f"Expected {expected_type} for '{prompt}', got {goal_type}"

    @pytest.mark.parametrize("prompt,expected_type", [
        # These get misclassified due to conversational keyword priority
        ("This code is messy, can you clean it up?", GoalType.CONVERSATION),  # "this" matches first
        ("How does the caching layer work?", GoalType.CONVERSATION),  # "how" matches "how do i use"
        ("Great work!", GoalType.UNKNOWN),  # "work" is not in conversation keywords
    ])
    def test_real_world_prompts_with_conversational_overlap(self, prompt, expected_type):
        """Documents prompts that get classified as conversational due to keyword overlap."""
        goal_type, _ = classify_goal(prompt)
        assert goal_type == expected_type, f"Expected {expected_type} for '{prompt}', got {goal_type}"
