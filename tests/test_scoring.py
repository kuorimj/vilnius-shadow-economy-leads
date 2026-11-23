from datetime import date

from shadow.score.leads import (
    Company,
    annual_revenue,
    caveats,
    explanation,
    is_lead,
    is_sales_lead,
    sales_explanation,
    supporting_reasons,
)


def company(**overrides):
    values = dict(
        code="1",
        name='UAB "Fabai"',
        legal_form="Uždaroji akcinė bendrovė",
        registered_on=date(2013, 5, 1),
        status="Teisinis stat neįregistruotas",
        activity_code="56.11.00",
        places=["Fabai"],
        place_categories={"cafe_restaurant"},
        reviews=3700,
        insured=2,
        peak_insured=2,
    )
    values.update(overrides)
    return Company(**values)


def test_busy_and_lightly_staffed_company_is_a_lead():
    assert is_lead(company(), median_reviews=152, typical_insured=7, median_ratio=25)


def test_well_staffed_busy_restaurant_is_not_a_lead():
    assert not is_lead(company(reviews=5500, insured=44), median_reviews=152, typical_insured=7, median_ratio=25)


def test_quiet_small_business_is_not_a_lead():
    assert not is_lead(company(reviews=40, insured=1), median_reviews=152, typical_insured=7, median_ratio=25)


def test_zero_employees_counts_as_one_for_the_ratio():
    assert company(reviews=169, insured=0).reviews_per_employee == 169


def test_category_follows_declared_activity():
    salon = company(activity_code="96.21.00", place_categories={"cafe_restaurant", "hair_beauty"})
    assert salon.category == "hair_beauty"


def test_supporting_reasons():
    dropped = company(insured=0, peak_insured=7)
    assert supporting_reasons(dropped, 2026) == ["insured employees fell from 7 to 0 during the year"]

    reregistered = company(registered_on=date(2025, 3, 1), years_in_business=7)
    assert "registered in 2025" in supporting_reasons(reregistered, 2026)[0]

    liquidating = company(status="Likviduojamas")
    assert supporting_reasons(liquidating, 2026) == ["company status: Likviduojamas"]

    assert supporting_reasons(company(), 2026) == []


def test_caveats_flag_small_partnerships_and_multiple_places():
    notes = caveats(company(legal_form="Mažoji bendrija", places=["A", "B"]))
    assert any("MB" in note for note in notes)
    assert any("2 places" in note for note in notes)


def test_explanation_reads_naturally():
    text = explanation(company(), median_reviews=151.5, typical_insured=7.0, ratio=59.1, sodra_month=date(2026, 9, 1))
    assert text == (
        "3,700 Google reviews across 1 place (median for cafés and restaurants: 152); "
        "2 insured employees in Sep 2026 (typical Vilnius food service company: 7); "
        "59.1x the category median of reviews per employee."
    )


def test_revenue_is_scaled_to_twelve_months():
    assert annual_revenue(130_000, date(2021, 1, 1), date(2022, 1, 31)) == 120_000
    assert annual_revenue(426_740, date(2024, 1, 1), date(2024, 12, 31)) == 426_740


def test_low_revenue_for_the_reviews_is_a_supporting_reason():
    busy = company(revenue=40_000, revenue_year=2024)  # 3,700 reviews: 925 per EUR 10k
    assert supporting_reasons(busy, 2026, median_revenue_ratio=50) == [
        "low declared revenue for its reviews: 925.0 reviews per EUR 10k of 2024 revenue, 18.5x the category median"
    ]
    fabai = company(revenue=426_740, revenue_year=2024)  # 86.7 per EUR 10k: 1.7x, below the 3x threshold
    assert supporting_reasons(fabai, 2026, median_revenue_ratio=50) == []


def test_zero_revenue_is_a_supporting_reason():
    assert supporting_reasons(company(revenue=0, revenue_year=2024), 2026, median_revenue_ratio=20) == [
        "declared no sales revenue in 2024"
    ]


def test_caveats_say_which_year_the_revenue_is_from():
    assert "revenue is from the 2024 financial statements" in caveats(company(revenue=1, revenue_year=2024))
    assert "no financial statements found" in caveats(company())


def darmelita(**overrides):
    values = dict(
        name='Uždaroji akcinė bendrovė "DARMELITA"', activity_code="96.02.00", places=["Darmelita"],
        place_categories={"hair_beauty"}, reviews=136, insured=8, peak_insured=8, avg_wage=1102.0,
        revenue=3249.0, revenue_year=2025, previous_revenue=42397.0, previous_revenue_year=2024,
    )
    values.update(overrides)
    return company(**values)


def test_revenue_drop_and_wage_bill():
    assert darmelita().revenue_dropped
    assert darmelita().wage_bill == 8 * 1102 * 12
    assert darmelita().below_wages
    assert not darmelita(revenue=30000.0).revenue_dropped
    assert not darmelita(previous_revenue=None).revenue_dropped
    assert not darmelita(avg_wage=None).below_wages


def test_busy_company_with_contradicting_declarations_is_a_sales_lead():
    assert is_sales_lead(darmelita(), median_reviews=116.5)
    assert not is_sales_lead(darmelita(reviews=40), median_reviews=116.5)
    healthy = darmelita(revenue=450000.0, previous_revenue=420000.0)
    assert not is_sales_lead(healthy, median_reviews=116.5)


def test_sales_explanation_reads_naturally():
    assert sales_explanation(darmelita(activity_code="96.21.00"), median_reviews=116.5) == (
        "136 Google reviews across 1 place (median for hair and beauty salons: 116), "
        "but declared revenue fell from EUR 42,397 in 2024 to EUR 3,249 in 2025, "
        "below its estimated wage bill of EUR 105,792."
    )
