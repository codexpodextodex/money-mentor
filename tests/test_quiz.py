"""The basket quiz uses the customer's own payments and the same rules as everything else."""

import pytest

from app import db, quiz

CUSTOMERS = ["CUST00086", "CUST00874", "CUST00728", "CUST02396", "CUST00001"]


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_quiz_questions_are_real_payments_with_the_right_basket(cid):
    got = quiz.basket_quiz(cid)
    questions = got["questions"]
    assert 3 <= len(questions) <= 6
    assert len({q["kind"] for q in questions}) == len(questions)
    for q in questions:
        match = db.scalar(
            "SELECT count(*) FROM tx WHERE customer_id = ? AND tx_date = ? AND subcategory = ? AND basket = ? "
            "AND abs(-amount - ?) < 0.005",
            [cid, q["date"], q["what"], q["basket"], q["amount"]],
        )
        assert match >= 1, q
        assert q["why"]
    # at most two per basket, so no basket dominates the quiz
    for basket in ("essentials", "unexpected", "everyday"):
        assert sum(1 for q in questions if q["basket"] == basket) <= 2


def test_quiz_is_the_same_every_time():
    assert quiz.basket_quiz("CUST00086") == quiz.basket_quiz("CUST00086")


@pytest.mark.parametrize("cid", CUSTOMERS)
def test_quiz_real_split_adds_up(cid):
    got = quiz.basket_quiz(cid)
    assert [s["basket"] for s in got["your_real_split"]] == ["essentials", "unexpected", "everyday"]
    assert sum(s["share_pct"] for s in got["your_real_split"]) == pytest.approx(100, abs=0.3)
    spend = db.scalar(
        "SELECT -sum(amount) FROM tx WHERE customer_id = ? AND flow = 'spend' AND tx_date BETWEEN DATE '2026-04-01' AND DATE '2026-09-30'",
        [cid],
    )
    assert sum(s["total"] for s in got["your_real_split"]) == pytest.approx(spend, abs=0.05)
