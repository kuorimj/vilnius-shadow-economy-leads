"""Compare how busy confirmed companies look on Google with what they declare to Sodra."""

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from statistics import median

from shadow.config import (
    CATEGORY_ACTIVITIES,
    CATEGORY_LABELS,
    EMPLOYEE_DROP_MIN_PEAK,
    EMPLOYEE_DROP_SHARE,
    LEAD_RATIO_MULTIPLE,
    REVENUE_DROP_SHARE,
)
from shadow.match.places import activity_fits

NORMAL_STATUS = "Teisinis stat neįregistruotas"
SMALL_PARTNERSHIP = "Mažoji bendrija"

CONFIRMED_PLACES = """
    SELECT c.company_code, c.name, c.legal_form, c.registered_on, c.status, c.activity_code,
           p.name, p.categories, coalesce(p.reviews_count, 0), p.years_in_business
    FROM staging.place_matches m
    JOIN staging.google_places p USING (snapshot_month, cid)
    JOIN staging.companies c USING (snapshot_month, company_code)
    WHERE m.snapshot_month = %(month)s AND m.match_status = 'confirmed'
    ORDER BY c.company_code, p.name
"""

INSURED = """
    SELECT company_code,
           max(insured) FILTER (WHERE month = %(sodra_month)s) AS latest,
           max(insured) AS peak,
           max(avg_wage) FILTER (WHERE month = %(sodra_month)s) AS avg_wage
    FROM staging.company_monthly
    WHERE snapshot_month = %(month)s AND company_code = ANY(%(codes)s)
    GROUP BY company_code
"""

TYPICAL_INSURED = """
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY m.insured)
    FROM staging.companies c
    JOIN staging.company_monthly m USING (snapshot_month, company_code)
    WHERE c.snapshot_month = %(month)s AND m.month = %(sodra_month)s
      AND c.activity_code LIKE ANY(%(patterns)s)
"""

REVENUE_HISTORY = """
    SELECT DISTINCT ON (company_code, period_end) company_code, period_start, period_end, revenue
    FROM staging.company_revenue
    WHERE snapshot_month = %(month)s AND company_code = ANY(%(codes)s) AND revenue IS NOT NULL
    ORDER BY company_code, period_end DESC, submitted_on DESC
"""

INSERT_LEAD = """
    INSERT INTO mart.leads (
        snapshot_month, rank, lead_type, company_code, company_name, legal_form, category, places, reviews,
        insured, typical_insured, revenue, revenue_year, reviews_per_employee, times_category_median,
        sodra_month, supporting_reasons, caveats, explanation
    ) VALUES (
        %(snapshot_month)s, %(rank)s, %(lead_type)s, %(company_code)s, %(company_name)s, %(legal_form)s, %(category)s,
        %(places)s, %(reviews)s, %(insured)s, %(typical_insured)s, %(revenue)s, %(revenue_year)s,
        %(reviews_per_employee)s, %(times_category_median)s, %(sodra_month)s, %(supporting_reasons)s,
        %(caveats)s, %(explanation)s
    )
"""


@dataclass
class Company:
    code: str
    name: str
    legal_form: str | None
    registered_on: date | None
    status: str | None
    activity_code: str | None
    places: list[str] = field(default_factory=list)
    place_categories: set[str] = field(default_factory=set)
    reviews: int = 0
    years_in_business: int | None = None
    insured: int = 0
    peak_insured: int = 0
    avg_wage: float | None = None
    revenue: float | None = None
    revenue_year: int | None = None
    previous_revenue: float | None = None
    previous_revenue_year: int | None = None

    @property
    def category(self) -> str:
        for category in sorted(self.place_categories):
            if activity_fits([category], self.activity_code):
                return category
        return sorted(self.place_categories)[0]

    @property
    def reviews_per_employee(self) -> float:
        return self.reviews / max(self.insured, 1)

    @property
    def reviews_per_10k_revenue(self) -> float | None:
        if not self.revenue or self.revenue <= 0:
            return None
        return self.reviews / (self.revenue / 10_000)

    @property
    def revenue_dropped(self) -> bool:
        if self.revenue is None or not self.previous_revenue or self.previous_revenue <= 0:
            return False
        return self.revenue <= self.previous_revenue * REVENUE_DROP_SHARE

    @property
    def wage_bill(self) -> float | None:
        if not self.insured or not self.avg_wage:
            return None
        return self.insured * self.avg_wage * 12

    @property
    def below_wages(self) -> bool:
        return self.revenue is not None and self.wage_bill is not None and self.revenue < self.wage_bill


def annual_revenue(revenue: float, period_start: date, period_end: date) -> float:
    months = (period_end.year - period_start.year) * 12 + period_end.month - period_start.month + 1
    return revenue * 12 / months


def supporting_reasons(company: Company, snapshot_year: int, median_revenue_ratio: float | None = None) -> list[str]:
    reasons = []
    if company.revenue is not None and company.revenue <= 0:
        reasons.append(f"declared no sales revenue in {company.revenue_year}")
    if company.revenue_dropped:
        reasons.append(
            f"revenue fell from EUR {company.previous_revenue:,.0f} in {company.previous_revenue_year} "
            f"to EUR {company.revenue:,.0f} in {company.revenue_year}"
        )
    if company.below_wages:
        reasons.append(
            f"{company.revenue_year} revenue of EUR {company.revenue:,.0f} is below the estimated yearly wage bill "
            f"of EUR {company.wage_bill:,.0f} for {company.insured} insured employees"
        )
    ratio = company.reviews_per_10k_revenue
    if ratio and median_revenue_ratio and ratio >= LEAD_RATIO_MULTIPLE * median_revenue_ratio:
        reasons.append(
            f"low declared revenue for its reviews: {ratio:.1f} reviews per EUR 10k of {company.revenue_year} "
            f"revenue, {ratio / median_revenue_ratio:.1f}x the category median"
        )
    if company.peak_insured >= EMPLOYEE_DROP_MIN_PEAK and company.insured <= company.peak_insured * EMPLOYEE_DROP_SHARE:
        reasons.append(f"insured employees fell from {company.peak_insured} to {company.insured} during the year")
    if company.years_in_business and company.registered_on:
        company_age = snapshot_year - company.registered_on.year
        if company.years_in_business > company_age + 1:
            reasons.append(
                f"Google lists the business as {company.years_in_business}+ years old, "
                f"but the company was registered in {company.registered_on.year}"
            )
    if company.status and company.status != NORMAL_STATUS:
        reasons.append(f"company status: {company.status}")
    return reasons


def caveats(company: Company) -> list[str]:
    notes = ["review counts accumulate over years and include tourists"]
    if company.legal_form == SMALL_PARTNERSHIP:
        notes.append("small partnership (MB): owners may work without being insured employees")
    if len(company.places) > 1:
        notes.append(f"reviews summed over {len(company.places)} places")
    if company.revenue_year:
        notes.append(f"revenue is from the {company.revenue_year} financial statements")
    if company.revenue_dropped:
        notes.append("a sharp revenue drop can mean the business moved to a related company")
    if company.below_wages:
        notes.append("wage bill estimated from the latest Sodra month, without employer contributions")
    else:
        notes.append("no financial statements found")
    return notes


def is_lead(company: Company, median_reviews: float, typical_insured: float, median_ratio: float) -> bool:
    return (
        company.reviews >= median_reviews
        and company.insured <= typical_insured
        and company.reviews_per_employee >= LEAD_RATIO_MULTIPLE * median_ratio
    )


def is_sales_lead(company: Company, median_reviews: float) -> bool:
    return company.reviews >= median_reviews and (company.revenue_dropped or company.below_wages)


def sales_explanation(company: Company, median_reviews: float) -> str:
    plural, _ = CATEGORY_LABELS[company.category]
    places = f"{len(company.places)} place" + ("s" if len(company.places) > 1 else "")
    busy = f"{company.reviews:,} Google reviews across {places} (median for {plural}: {median_reviews:,.0f})"
    if company.revenue_dropped:
        declared = (
            f"declared revenue fell from EUR {company.previous_revenue:,.0f} in {company.previous_revenue_year} "
            f"to EUR {company.revenue:,.0f} in {company.revenue_year}"
        )
        if company.below_wages:
            declared += f", below its estimated wage bill of EUR {company.wage_bill:,.0f}"
    else:
        declared = (
            f"declared {company.revenue_year} revenue of EUR {company.revenue:,.0f} is below "
            f"its estimated wage bill of EUR {company.wage_bill:,.0f}"
        )
    return f"{busy}, but {declared}."


def explanation(company: Company, median_reviews: float, typical_insured: float, ratio: float, sodra_month: date) -> str:
    plural, activity = CATEGORY_LABELS[company.category]
    places = f"{len(company.places)} place" + ("s" if len(company.places) > 1 else "")
    return (
        f"{company.reviews:,} Google reviews across {places} (median for {plural}: {median_reviews:,.0f}); "
        f"{company.insured} insured employee{'' if company.insured == 1 else 's'} in {sodra_month:%b %Y} "
        f"(typical Vilnius {activity} company: {typical_insured:g}); "
        f"{ratio:.1f}x the category median of reviews per employee."
    )


def build_leads(conn, month: str) -> list[dict]:
    sodra_month = conn.execute(
        "SELECT max(month) FROM staging.company_monthly WHERE snapshot_month = %s", (month,)
    ).fetchone()[0]

    companies: dict[str, Company] = {}
    for code, name, form, registered, status, activity, place, categories, reviews, years in conn.execute(
        CONFIRMED_PLACES, {"month": month}
    ):
        company = companies.setdefault(code, Company(code, name, form, registered, status, activity))
        company.places.append(place)
        company.place_categories.update(categories)
        company.reviews += reviews
        if years:
            company.years_in_business = max(years, company.years_in_business or 0)

    for code, latest, peak, avg_wage in conn.execute(
        INSURED, {"month": month, "sodra_month": sodra_month, "codes": list(companies)}
    ):
        companies[code].insured = latest or 0
        companies[code].peak_insured = peak or 0
        companies[code].avg_wage = float(avg_wage) if avg_wage is not None else None

    for code, period_start, period_end, revenue in conn.execute(
        REVENUE_HISTORY, {"month": month, "codes": list(companies)}
    ):
        company = companies[code]
        yearly = annual_revenue(float(revenue), period_start, period_end)
        if company.revenue_year is None:
            company.revenue, company.revenue_year = yearly, period_end.year
        elif company.previous_revenue_year is None:
            company.previous_revenue, company.previous_revenue_year = yearly, period_end.year

    leads = []
    for category in CATEGORY_ACTIVITIES:
        group = [c for c in companies.values() if c.category == category]
        if not group:
            continue
        median_reviews = median(c.reviews for c in group)
        median_ratio = median(c.reviews_per_employee for c in group)
        revenue_ratios = [c.reviews_per_10k_revenue for c in group if c.reviews_per_10k_revenue]
        median_revenue_ratio = median(revenue_ratios) if revenue_ratios else None
        patterns = [f"{prefix}%" for prefix in CATEGORY_ACTIVITIES[category]]
        typical_insured = conn.execute(
            TYPICAL_INSURED, {"month": month, "sodra_month": sodra_month, "patterns": patterns}
        ).fetchone()[0]

        for company in group:
            ratio = company.reviews_per_employee / median_ratio if median_ratio else 0
            if is_lead(company, median_reviews, typical_insured, median_ratio):
                lead_type = "staff"
                text = explanation(company, median_reviews, typical_insured, ratio, sodra_month)
            elif is_sales_lead(company, median_reviews):
                lead_type = "sales"
                text = sales_explanation(company, median_reviews)
            else:
                continue
            leads.append(
                {
                    "snapshot_month": month,
                    "lead_type": lead_type,
                    "company_code": company.code,
                    "company_name": company.name,
                    "legal_form": company.legal_form,
                    "category": category,
                    "places": " / ".join(company.places),
                    "reviews": company.reviews,
                    "insured": company.insured,
                    "typical_insured": typical_insured,
                    "revenue": round(company.revenue) if company.revenue is not None else None,
                    "revenue_year": company.revenue_year,
                    "reviews_per_employee": round(company.reviews_per_employee, 1),
                    "times_category_median": round(ratio, 1) if lead_type == "staff" else None,
                    "sodra_month": sodra_month,
                    "supporting_reasons": supporting_reasons(company, int(month[:4]), median_revenue_ratio),
                    "caveats": caveats(company),
                    "explanation": text,
                }
            )

    leads.sort(key=lambda lead: (lead["lead_type"] != "staff", -(lead["times_category_median"] or 0)))
    for rank, lead in enumerate(leads, start=1):
        lead["rank"] = rank
    return leads


def load_leads(conn, month: str) -> list[dict]:
    leads = build_leads(conn, month)
    with conn.transaction():
        conn.execute("DELETE FROM mart.leads WHERE snapshot_month = %s", (month,))
        with conn.cursor() as cur:
            cur.executemany(INSERT_LEAD, leads)
    return leads


def export_csv(leads: list[dict], month: str, data_dir: str = "data") -> Path:
    out_dir = Path(data_dir) / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"leads_{month}.csv"
    columns = [
        "rank", "lead_type", "company_code", "company_name", "legal_form", "category", "places", "reviews",
        "insured", "typical_insured", "revenue", "revenue_year", "times_category_median",
        "supporting_reasons", "caveats", "explanation",
    ]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for lead in leads:
            writer.writerow(
                {**lead, "supporting_reasons": "; ".join(lead["supporting_reasons"]), "caveats": "; ".join(lead["caveats"])}
            )
    return path