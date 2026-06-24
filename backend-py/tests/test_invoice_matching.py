"""Regression tests for invoice-payment ILIKE matching fix.

The old code used `%invoice_id:1%` which matched invoice_id:10, invoice_id:100.
The fix uses exact boundary patterns so invoice_id:1 only matches itself.
"""

import re


def sql_like_match(pattern, text):
    """Simulate SQL LIKE pattern matching."""
    parts = pattern.split('%')
    regex_parts = [re.escape(p) for p in parts]
    regex = "^" + ".*".join(regex_parts) + "$"
    return bool(re.match(regex, text, re.IGNORECASE | re.DOTALL))


def matches_any_pattern(invoice_id, note_text):
    """Check if note_text matches any of the new exact patterns for the given invoice_id."""
    exact_marker = f"% invoice_id:{invoice_id} |%"
    end_marker = f"% invoice_id:{invoice_id}"
    pipe_marker = f"invoice_id:{invoice_id} |%"
    solo_marker = f"invoice_id:{invoice_id}"

    for pattern in [exact_marker, end_marker, pipe_marker, solo_marker]:
        if sql_like_match(pattern, note_text):
            return True
    return False


def test_marker_matches_invoice_id_1():
    note = "دفعة تلقائية من فاتورة #INV-1 | invoice_id:1 | method:cash"
    assert matches_any_pattern(1, note) is True


def test_marker_does_not_match_invoice_id_10():
    note = "دفعة تلقائية من فاتورة #INV-10 | invoice_id:10 | method:cash"
    assert matches_any_pattern(1, note) is False


def test_marker_does_not_match_invoice_id_100():
    note = "دفعة تلقائية من فاتورة #INV-100 | invoice_id:100 | method:cash"
    assert matches_any_pattern(1, note) is False


def test_marker_does_not_match_invoice_id_12():
    note = "some text | invoice_id:12 | method:transfer"
    assert matches_any_pattern(1, note) is False


def test_marker_matches_solo_note():
    assert matches_any_pattern(5, "invoice_id:5") is True


def test_marker_does_not_match_solo_prefix():
    assert matches_any_pattern(5, "invoice_id:50") is False


def test_marker_matches_end_of_note():
    note = "some note | invoice_id:3"
    assert matches_any_pattern(3, note) is True


def test_marker_does_not_match_end_prefix():
    note = "some note | invoice_id:30"
    assert matches_any_pattern(3, note) is False


def test_marker_matches_start_of_note_with_pipe():
    note = "invoice_id:7 | method:cash"
    assert matches_any_pattern(7, note) is True


def test_old_ilike_pattern_was_broken():
    """Verify that the OLD pattern %invoice_id:1% incorrectly matches invoice_id:10."""
    old_pattern = "%invoice_id:1%"
    note_10 = "note | invoice_id:10 | method:cash"
    assert sql_like_match(old_pattern, note_10) is True, \
        "Old pattern incorrectly matched invoice_id:10 — this test proves the bug existed"


def test_new_patterns_dont_match_id_10():
    """New patterns must NOT match invoice_id:10 when searching for invoice_id:1."""
    note_10 = "note | invoice_id:10 | method:cash"
    assert matches_any_pattern(1, note_10) is False


def test_approval_auto_payment_note_format():
    """Match the exact note format used in approve_invoice."""
    note = "دفعة تلقائية من اعتماد فاتورة #INV-42 | invoice_id:42 | method:cash"
    assert matches_any_pattern(42, note) is True
    assert matches_any_pattern(4, note) is False
    assert matches_any_pattern(420, note) is False
