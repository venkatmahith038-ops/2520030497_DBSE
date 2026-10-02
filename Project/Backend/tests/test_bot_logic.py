"""The pure decision functions in the automation engine.

These gate compliance behaviour — who gets messaged and when — so they are the
functions where a silent regression is most expensive.
"""
from datetime import datetime

import pytest

from backend.bot import (
    MATCH_MODE_ANY,
    MATCH_MODE_EXACT,
    comment_matches_trigger,
    is_exact_trigger_match,
    is_valid_instagram_username,
    is_within_working_hours,
    parse_spintax,
)


# ── Working hours ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hour,expected", [(7, False), (8, True), (14, True), (21, True), (22, False), (23, False)])
def test_daytime_window(hour, expected):
    now = datetime(2026, 7, 25, hour, 30)
    assert is_within_working_hours("08:00", "22:00", now) is expected


@pytest.mark.parametrize("hour,expected", [(23, True), (2, True), (5, False), (12, False), (21, False)])
def test_window_crossing_midnight(hour, expected):
    """A 22:00–04:00 window has to wrap, not evaluate to 'never'."""
    now = datetime(2026, 7, 25, hour, 0)
    assert is_within_working_hours("22:00", "04:00", now) is expected


def test_malformed_hours_do_not_crash_the_loop(recwarn):
    now = datetime(2026, 7, 25, 12, 0)
    # Whatever the policy, it must return a bool rather than raise — a crash
    # here takes down the whole worker.
    assert isinstance(is_within_working_hours("not-a-time", "22:00", now), bool)


# ── Spintax ──────────────────────────────────────────────────────────────────

def test_spintax_picks_one_option():
    for _ in range(30):
        assert parse_spintax("{Hi|Hello|Hey} there") in ("Hi there", "Hello there", "Hey there")


def test_spintax_leaves_plain_text_alone():
    assert parse_spintax("No variants here") == "No variants here"


def test_spintax_handles_multiple_groups():
    result = parse_spintax("{Hi|Hey} {there|friend}")
    assert result in ("Hi there", "Hi friend", "Hey there", "Hey friend")


def test_spintax_eventually_produces_variety():
    seen = {parse_spintax("{a|b|c}") for _ in range(60)}
    assert len(seen) > 1, "spintax collapsed to a single option"


# ── Consent: exact trigger matching ──────────────────────────────────────────

@pytest.mark.parametrize("comment", ["SEND", "send", "  Send  ", "sEnD"])
def test_trigger_matches_regardless_of_case_and_padding(comment):
    assert is_exact_trigger_match(comment, "send") is True


@pytest.mark.parametrize("comment", ["send me the link", "please send", "sending", "resend", ""])
def test_trigger_requires_an_exact_comment(comment):
    """Consent comes from the comment being exactly the keyword. Substring
    matching here would mean DMing people who never opted in."""
    assert is_exact_trigger_match(comment, "send") is False


# ── Username validation ──────────────────────────────────────────────────────

@pytest.mark.parametrize("username", ["valid_user", "user.name", "abc", "a" * 30])
def test_accepts_real_usernames(username):
    assert is_valid_instagram_username(username) is True


@pytest.mark.parametrize("username", ["", "a" * 31, "has space", "bad!char", "@leading"])
def test_rejects_malformed_usernames(username):
    assert is_valid_instagram_username(username) is False


# ── Match modes ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("comment", [
    "send",              # the keyword itself
    "anything at all",
    "a long paragraph explaining exactly why this person is interested in the offer",
    "🔥",                # bare emoji
    "😍😍😍",
    "❤️ love this",
    "नमस्ते",             # non-latin script
    "?",
])
def test_any_mode_triggers_on_every_comment(comment):
    """Whatever the comment contains — word, paragraph, emoji — it triggers."""
    assert comment_matches_trigger(comment, "send", MATCH_MODE_ANY) is True


@pytest.mark.parametrize("comment", ["", "   ", "\n\t "])
def test_any_mode_still_ignores_empty_comments(comment):
    """An empty comment is not a person asking for anything."""
    assert comment_matches_trigger(comment, "send", MATCH_MODE_ANY) is False


def test_any_mode_does_not_need_a_keyword():
    assert comment_matches_trigger("hello", "", MATCH_MODE_ANY) is True


@pytest.mark.parametrize("comment,expected", [
    ("send", True),
    ("SEND", True),
    ("  send  ", True),
    ("send me the link", False),
    ("🔥", False),
    ("", False),
])
def test_exact_mode_is_unchanged(comment, expected):
    assert comment_matches_trigger(comment, "send", MATCH_MODE_EXACT) is expected


def test_default_mode_is_exact():
    """Consent-preserving behaviour must be what you get without asking."""
    assert comment_matches_trigger("anything", "send") is False
    assert comment_matches_trigger("send", "send") is True


def test_unknown_mode_falls_back_to_exact():
    """A bad value must never silently widen who gets messaged."""
    assert comment_matches_trigger("anything", "send", "nonsense") is False
