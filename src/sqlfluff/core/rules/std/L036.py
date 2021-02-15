"""Implementation of Rule L036."""

from typing import List, NamedTuple

from sqlfluff.core.parser import BaseSegment
from sqlfluff.core.rules.base import BaseCrawler, LintFix, LintResult
from sqlfluff.core.rules.doc_decorators import document_fix_compatible


class EvalResult(NamedTuple):
    cnt_select_targets: int
    select_idx: int
    first_new_line_idx: int
    first_select_target_idx: int
    first_whitespace_idx: int
    select_targets: List[BaseSegment]


@document_fix_compatible
class Rule_L036(BaseCrawler):
    """Select targets should be on a new line unless there is only one select target.

    | **Anti-pattern**

    .. code-block:: sql

        select
            *
        from x


    | **Best practice**

    .. code-block:: sql

        select
            a,
            b,
            c
        from x

    """

    def _eval(self, segment, raw_stack, **kwargs):
        if segment.is_type("select_clause"):
            eval_result = self._get_indexes(segment)
            if eval_result.cnt_select_targets == 1:
                return self._eval_single_select_target_element(eval_result, segment)
            if eval_result.cnt_select_targets > 1:
                return self._eval_multiple_select_target_elements(eval_result, segment)

    @staticmethod
    def _get_indexes(segment):
        cnt_select_targets = 0
        select_idx = -1
        first_new_line_idx = -1
        first_select_target_idx = -1
        first_whitespace_idx = -1
        select_targets = []
        for fname_idx, seg in enumerate(segment.segments):
            if seg.is_type("select_target_element"):
                select_targets.append(seg)
                cnt_select_targets += 1
                if first_select_target_idx == -1:
                    first_select_target_idx = fname_idx
            if seg.is_type("keyword") and seg.name == "SELECT" and select_idx == -1:
                select_idx = fname_idx
            if seg.is_type("newline") and first_new_line_idx == -1:
                first_new_line_idx = fname_idx
            # TRICKY: Ignore whitespace prior to the first newline, e.g. if
            # the line with "SELECT" (before any select targets) has trailing
            # whitespace.
            if (
                seg.is_type("whitespace")
                and first_new_line_idx != -1
                and first_whitespace_idx == -1
            ):
                first_whitespace_idx = fname_idx

        eval_result = EvalResult(
            cnt_select_targets,
            select_idx,
            first_new_line_idx,
            first_select_target_idx,
            first_whitespace_idx,
            select_targets
        )

        return eval_result

    def _eval_multiple_select_target_elements(self, eval_result, segment):
        if eval_result.first_new_line_idx == -1:
            # there are multiple select targets but no new lines
            ins = self.make_newline(
                pos_marker=segment.pos_marker.advance_by(segment.raw))
            fixes = [LintFix("create", eval_result.select_targets[0], ins)]
            return LintResult(anchor=segment, fixes=fixes)

    def _eval_single_select_target_element(self, eval_result, select_clause):
        is_wildcard = False
        for segment in select_clause.segments:
            if segment.is_type("select_target_element"):
                for sub_segment in segment.segments:
                    if sub_segment.is_type("wildcard_expression"):
                        is_wildcard = True

        if is_wildcard:
            return None
        elif (
            eval_result.select_idx
            < eval_result.first_new_line_idx
            < eval_result.first_select_target_idx
        ):
            # there is a newline between select and select target
            fixes = [LintFix("delete", select_clause.segments[eval_result.first_new_line_idx])]
            return LintResult(anchor=select_clause, fixes=fixes)
        else:
            return None
