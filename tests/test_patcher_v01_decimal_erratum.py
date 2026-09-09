"""Regression tests for Patcher v0.1 Decimal no-rounding erratum (0041)."""
from __future__ import annotations

import unittest
from decimal import Decimal, getcontext

from formatador_academico.operation_plan.model import LengthValue
from formatador_academico.patcher.model import PatchReason
from formatador_academico.patcher.xml_patch import Reject, half_points_lexical


class PatcherDecimalExactnessErratumTests(unittest.TestCase):
    def _length(self, value: str) -> LengthValue:
        return LengthValue(Decimal(value), "pt")

    def test_adversarial_decimal_is_rejected_not_rounded(self):
        with self.assertRaises(Reject) as cm:
            half_points_lexical(self._length("1.000000000000000000000000000005"))
        self.assertIs(cm.exception.reason, PatchReason.UNREPRESENTABLE_VALUE)

    def test_global_decimal_precision_does_not_change_result(self):
        old = getcontext().prec
        try:
            getcontext().prec = 3
            self.assertEqual(half_points_lexical(self._length("11.5")), "23")
            with self.assertRaises(Reject):
                half_points_lexical(self._length("11.25"))
            with self.assertRaises(Reject):
                half_points_lexical(self._length("1.000000000000000000000000000005"))
        finally:
            getcontext().prec = old

    def test_existing_exact_cases_remain_unchanged(self):
        self.assertEqual(half_points_lexical(self._length("12")), "24")
        self.assertEqual(half_points_lexical(self._length("11.5")), "23")
        self.assertEqual(half_points_lexical(self._length("1638")), "3276")
        with self.assertRaises(Reject) as cm:
            half_points_lexical(self._length("11.25"))
        self.assertIs(cm.exception.reason, PatchReason.UNREPRESENTABLE_VALUE)
        with self.assertRaises(Reject) as cm:
            half_points_lexical(self._length("1638.5"))
        self.assertIs(cm.exception.reason, PatchReason.UNREPRESENTABLE_VALUE)

    def test_extreme_exponents_are_rejected_without_materializing_huge_powers(self):
        for value in ("1E+1000000", "1E-1000000"):
            with self.subTest(value=value):
                with self.assertRaises(Reject) as cm:
                    half_points_lexical(self._length(value))
                self.assertIs(cm.exception.reason, PatchReason.UNREPRESENTABLE_VALUE)
