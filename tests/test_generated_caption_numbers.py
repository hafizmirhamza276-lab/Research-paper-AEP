"""A caption is a claim, and rule 3 says claims come from macros.

``docs/26`` §3 rule 3 and ``docs/25`` R14. The defect: ``paper_tables.py`` built
the deployment table's caption with ``f"{tex(b3 - b0)}"`` -- 28.0 ms, computed
inline from three-run medians and never a ``\\newcommand``. Phase 26 retired
that figure from every ``.tex`` and from the macro set; the caption kept
printing it; the built PDF stated it beside a section saying the opposite; every
gate stayed green, because every gate's coverage is defined by the macro
mechanism and this number was outside it.

``docs/25`` R17: nothing here executes an older generator. The failing-branch
evidence is the real pre-fix caption text, reproduced as a fixture and run
through the current check.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_paper_numbers import (  # noqa: E402
    CAPTION_LITERALS,
    Result,
    check_generated_captions_use_macros,
)

#: The caption exactly as `paper_tables.py` emitted it before this fix, trimmed
#: to the clause that carried the number. Kept verbatim so the test fails for
#: the reason the paper failed, not for a reason invented here.
PRE_FIX_CAPTION = (
    r"\multicolumn{6}{@{}p{0.96\textwidth}@{}}{\footnotesize "
    r"`Over floor' is the same median less the provider's "
    r"2\,000\,ms delay, and so includes the 28.0\,ms the protocol "
    r"costs with the barrier already removed.}\\"
)

FIXED_CAPTION = (
    r"\multicolumn{6}{@{}p{0.96\textwidth}@{}}{\footnotesize "
    r"`Over floor' is the same median less the provider's "
    r"2\,000\,ms delay, and so includes whatever the protocol costs with "
    r"the barrier already removed -- a quantity this evaluation cannot "
    r"separate from zero: \ProtocolMinusBarrierFifteen{}\,ms "
    r"[\ProtocolMinusBarrierFifteenLow{}, \ProtocolMinusBarrierFifteenHigh{}] "
    r"pooled.}\\"
)

NUMBERS = (
    "\\newcommand{\\ProtocolMinusBarrierFifteen}{33.9}\n"
    "\\newcommand{\\ProtocolMinusBarrierFifteenLow}{-122.6}\n"
    "\\newcommand{\\ProtocolMinusBarrierFifteenHigh}{120.1}\n"
)


def build(tmp_path: Path, caption: str) -> Path:
    paper = tmp_path / "paper"
    (paper / "generated").mkdir(parents=True)
    (paper / "generated" / "numbers.tex").write_text(NUMBERS, encoding="utf-8")
    (paper / "generated" / "table-deployment-choice.tex").write_text(
        caption + "\n", encoding="utf-8")
    return paper


def run(paper: Path) -> Result:
    result = Result()
    check_generated_captions_use_macros(result, paper)
    return result


def test_the_pre_fix_caption_fails(tmp_path):
    """Rule 13. This is the number the paper actually printed."""
    result = run(build(tmp_path, PRE_FIX_CAPTION))

    assert result.failures, "the check did not see 28.0"
    assert any("28.0" in f for f in result.failures), result.failures


def test_the_fixed_caption_passes(tmp_path):
    result = run(build(tmp_path, FIXED_CAPTION))
    assert not result.failures, result.failures


def test_a_thousands_separator_is_not_two_numbers(tmp_path):
    """``2\\,000`` is one number. A check that split it would report ``000``
    forever and be switched off."""
    result = run(build(tmp_path, FIXED_CAPTION))
    assert not any("000" in f for f in result.failures), result.failures


def test_the_provider_delay_is_allowed_and_says_why(tmp_path):
    """It is a configured setting, not a measurement, so it is a literal --
    and the allowlist records that rather than leaving it unexplained."""
    assert "2000" in CAPTION_LITERALS
    assert "setting" in CAPTION_LITERALS["2000"]


def test_an_unbacked_number_in_any_generated_caption_fails(tmp_path):
    """Not special-cased to the deployment table: the class is the defect."""
    caption = (
        r"\multicolumn{2}{c}{\footnotesize The rate was 41.7\% across the "
        r"cells.}\\"
    )
    result = run(build(tmp_path, caption))
    assert any("41.7" in f for f in result.failures), result.failures


def test_a_macro_backed_number_written_out_also_passes(tmp_path):
    """If a caption spells a value that some macro holds, that is traceable
    even though it is not a macro invocation -- the number is still the
    generator's own and a reader can find it."""
    caption = (
        r"\multicolumn{2}{c}{\footnotesize The pooled figure is 33.9\,ms.}\\"
    )
    result = run(build(tmp_path, caption))
    assert not result.failures, result.failures
