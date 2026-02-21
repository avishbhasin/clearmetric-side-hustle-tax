"""
Side Hustle Tax Estimator — Free Web Tool by ClearMetric
https://clearmetric.gumroad.com

Helps people with side income (freelance, Etsy, Uber, etc.) estimate their tax liability.
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Side Hustle Tax Estimator — ClearMetric",
    page_icon="📋",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS (navy theme)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; max-width: 1200px; }
    .stMetric { background: #f8f9fa; border-radius: 8px; padding: 12px; border-left: 4px solid #1a5276; }
    h1 { color: #1a5276; }
    h2, h3 { color: #2c3e50; }
    .cta-box {
        background: linear-gradient(135deg, #1a5276 0%, #2e86c1 100%);
        color: white; padding: 24px; border-radius: 12px; text-align: center;
        margin: 20px 0;
    }
    .cta-box a { color: #f0d78c; text-decoration: none; font-weight: bold; font-size: 1.1rem; }
    div[data-testid="stSidebar"] { background: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 2026 Tax Constants
# ---------------------------------------------------------------------------
SS_WAGE_BASE_2026 = 184_500
STANDARD_DEDUCTION = {
    "Single": 16_100,
    "Married Filing Jointly": 32_200,
    "Head of Household": 24_150,
}

# 2026 brackets: (rate, threshold) — threshold is "over this amount"
BRACKETS = {
    "Single": [
        (0.10, 0), (0.12, 12_400), (0.22, 50_400), (0.24, 105_700),
        (0.32, 201_775), (0.35, 256_225), (0.37, 640_600),
    ],
    "Married Filing Jointly": [
        (0.10, 0), (0.12, 24_800), (0.22, 100_800), (0.24, 211_400),
        (0.32, 403_550), (0.35, 512_450), (0.37, 768_700),
    ],
    "Head of Household": [
        (0.10, 0), (0.12, 17_700), (0.22, 67_450), (0.24, 105_700),
        (0.32, 201_775), (0.35, 256_200), (0.37, 640_600),
    ],
}

# Simplified flat state tax rates (2025/2026 approximate). 0 = no state income tax.
STATE_TAX_RATES = {
    "Alabama": 0.05, "Alaska": 0, "Arizona": 0.025, "Arkansas": 0.045,
    "California": 0.093, "Colorado": 0.0455, "Connecticut": 0.065,
    "Delaware": 0.066, "District of Columbia": 0.0975, "Florida": 0,
    "Georgia": 0.055, "Hawaii": 0.09, "Idaho": 0.058, "Illinois": 0.0495,
    "Indiana": 0.0315, "Iowa": 0.044, "Kansas": 0.057, "Kentucky": 0.045,
    "Louisiana": 0.0425, "Maine": 0.075, "Maryland": 0.0575,
    "Massachusetts": 0.05, "Michigan": 0.0425, "Minnesota": 0.0985,
    "Mississippi": 0.05, "Missouri": 0.045, "Montana": 0.069,
    "Nebraska": 0.0684, "Nevada": 0, "New Hampshire": 0,
    "New Jersey": 0.1075, "New Mexico": 0.059, "New York": 0.109,
    "North Carolina": 0.0475, "North Dakota": 0.029, "Ohio": 0.0395,
    "Oklahoma": 0.0475, "Oregon": 0.099, "Pennsylvania": 0.0307,
    "Rhode Island": 0.0599, "South Carolina": 0.065, "South Dakota": 0,
    "Tennessee": 0, "Texas": 0, "Utah": 0.0485, "Vermont": 0.0875,
    "Virginia": 0.0575, "Washington": 0, "West Virginia": 0.065,
    "Wisconsin": 0.0765, "Wyoming": 0,
}


def federal_income_tax(taxable_income: float, filing_status: str) -> tuple[float, float]:
    """Compute federal income tax and marginal rate. Returns (tax, marginal_rate)."""
    if taxable_income <= 0:
        return 0.0, 0.10
    brackets = BRACKETS[filing_status]
    tax = 0.0
    prev = 0
    marginal_rate = 0.10
    for rate, thresh in brackets:
        if taxable_income <= thresh:
            tax += (taxable_income - prev) * rate
            marginal_rate = rate
            break
        tax += (thresh - prev) * rate
        prev = thresh
        marginal_rate = rate
    else:
        tax += (taxable_income - prev) * marginal_rate
    return max(0, tax), marginal_rate


def self_employment_tax(net_profit: float, w2_wages: float) -> float:
    """SE tax: 15.3% on 92.35% of net profit, with SS cap at wage base."""
    se_taxable = net_profit * 0.9235
    remaining_ss_cap = max(0, SS_WAGE_BASE_2026 - w2_wages)
    ss_taxable = min(se_taxable, remaining_ss_cap)
    ss_tax = ss_taxable * 0.124
    medicare_tax = se_taxable * 0.029
    return ss_tax + medicare_tax


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("# 📋 Side Hustle Tax Estimator")
st.markdown("**Estimate your tax liability** — for freelance, Etsy, Uber, and other side income.")
st.markdown("---")

# ---------------------------------------------------------------------------
# Sidebar — User inputs
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## Your Numbers")

    st.markdown("### Filing & Income")
    filing_status = st.selectbox(
        "Filing Status",
        ["Single", "Married Filing Jointly", "Head of Household"],
    )
    w2_salary = st.number_input("W-2 Salary from Day Job ($)", value=75_000, min_value=0, step=5_000, format="%d")
    side_gross = st.number_input("Side Hustle Gross Income ($)", value=25_000, min_value=0, step=1_000, format="%d")

    st.markdown("### Side Hustle Expenses (Deductible)")
    exp_supplies = st.number_input("Supplies/Materials ($)", value=2_000, min_value=0, step=500, format="%d")
    exp_software = st.number_input("Software/Tools ($)", value=500, min_value=0, step=100, format="%d")
    exp_home_office = st.number_input("Home Office ($)", value=1_500, min_value=0, step=500, format="%d",
                                     help="$5/sqft simplified option")
    exp_vehicle = st.number_input("Vehicle/Mileage ($)", value=1_000, min_value=0, step=100, format="%d")
    exp_marketing = st.number_input("Marketing/Advertising ($)", value=500, min_value=0, step=100, format="%d")
    exp_other = st.number_input("Other Deductible Expenses ($)", value=500, min_value=0, step=100, format="%d")

    st.markdown("### Deductions & State")
    use_standard = st.toggle("Standard Deduction", value=True, help="Toggle off for itemized")
    if not use_standard:
        itemized_deduction = st.number_input("Itemized Deduction ($)", value=20_000, min_value=0, step=1000, format="%d")
    else:
        itemized_deduction = 0
    state = st.selectbox("State", list(STATE_TAX_RATES.keys()), index=list(STATE_TAX_RATES.keys()).index("California"))
    quarterly_paid = st.number_input("Quarterly Estimated Payments Already Made ($)", value=0, min_value=0, step=500, format="%d")

# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------
total_expenses = exp_supplies + exp_software + exp_home_office + exp_vehicle + exp_marketing + exp_other
side_net = max(0, side_gross - total_expenses)
total_gross = w2_salary + side_gross

se_tax = self_employment_tax(side_net, w2_salary)
se_deduction = se_tax * 0.5
deduction = STANDARD_DEDUCTION[filing_status] if use_standard else itemized_deduction
agi = total_gross - se_deduction
taxable_income = max(0, agi - deduction)
fed_tax, marginal_rate = federal_income_tax(taxable_income, filing_status)
state_rate = STATE_TAX_RATES[state]
state_tax = taxable_income * state_rate if state_rate > 0 else 0
total_tax = fed_tax + state_tax + se_tax
effective_rate = total_tax / total_gross if total_gross > 0 else 0

# Tax attributable to side hustle (incremental)
taxable_without = max(0, w2_salary - deduction)
fed_without, _ = federal_income_tax(taxable_without, filing_status)
state_without = taxable_without * state_rate if state_rate > 0 else 0
tax_without_side = fed_without + state_without
additional_tax_from_side = total_tax - tax_without_side if side_net > 0 else 0
fed_increment = fed_tax - fed_without if side_net > 0 else 0
state_increment = state_tax - state_without if side_net > 0 else 0

side_take_home = side_net - additional_tax_from_side
remaining_tax = max(0, total_tax - quarterly_paid)
quarterly_payment = remaining_tax / 4

# ---------------------------------------------------------------------------
# Display — Key metrics
# ---------------------------------------------------------------------------
st.markdown("## Key Results")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Tax Liability", f"${total_tax:,.0f}", f"After ${quarterly_paid:,.0f} paid" if quarterly_paid > 0 else None)
m2.metric("Effective Tax Rate", f"{effective_rate*100:.1f}%", "On total gross income")
m3.metric("Side Hustle Take-Home", f"${side_take_home:,.0f}", f"Net profit ${side_net:,.0f} − tax")
m4.metric("Quarterly Payment Needed", f"${quarterly_payment:,.0f}", "Each quarter (next year)")

st.markdown("---")

# ---------------------------------------------------------------------------
# Stacked bar: Tax breakdown
# ---------------------------------------------------------------------------
st.markdown("## Tax Breakdown")

breakdown = {
    "Federal Income Tax": fed_tax,
    "State Income Tax": state_tax,
    "Self-Employment Tax": se_tax,
    "Take-Home (from side)": side_take_home,
}
breakdown = {k: max(0, v) for k, v in breakdown.items() if v > 0}
if sum(breakdown.values()) > 0:
    fig_bar = go.Figure(data=[
        go.Bar(name=k, x=[k], y=[v], marker_color=c)
        for (k, v), c in zip(
            breakdown.items(),
            ["#1a5276", "#2e86c1", "#5dade2", "#27ae60"],
        )
    ])
    fig_bar.update_layout(
        barmode="stack",
        height=300,
        showlegend=True,
        legend=dict(orientation="h", y=1.02),
        margin=dict(t=40, b=40),
        template="plotly_white",
        xaxis=dict(showticklabels=False),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Pie chart: Where side hustle money goes
# ---------------------------------------------------------------------------
st.markdown("## Where Your Side Hustle Money Goes")

pie_data = {
    "Take-Home": side_take_home,
    "Federal Tax": fed_increment,
    "State Tax": state_increment,
    "SE Tax": se_tax,
    "Expenses": total_expenses,
}
pie_data = {k: max(0, v) for k, v in pie_data.items() if v > 0}
total_pie = sum(pie_data.values())
if total_pie > 0:
    fig_pie = go.Figure(data=[go.Pie(
        labels=list(pie_data.keys()),
        values=list(pie_data.values()),
        hole=0.4,
        marker_colors=["#27ae60", "#1a5276", "#2e86c1", "#5dade2", "#f39c12"],
        textinfo="percent+label",
        textposition="outside",
    )])
    fig_pie.update_layout(
        height=400,
        showlegend=True,
        legend=dict(orientation="h", y=1.02),
        margin=dict(t=40, b=40),
        template="plotly_white",
    )
    st.plotly_chart(fig_pie, use_container_width=True)
else:
    st.info("Adjust inputs to see breakdown.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Tax bracket visualization
# ---------------------------------------------------------------------------
st.markdown("## Tax Bracket Visualization")

brackets = BRACKETS[filing_status]
bracket_info = []
prev_t = 0
for i, (rate, thresh) in enumerate(brackets):
    in_this = prev_t < taxable_income <= thresh or (i == len(brackets) - 1 and taxable_income > thresh)
    range_str = f"${prev_t:,.0f} – ${thresh:,.0f}" if i < len(brackets) - 1 else f"${thresh:,.0f}+"
    bracket_info.append({
        "Bracket": f"{rate*100:.0f}%",
        "Income Range": range_str,
        "Your Income In": "✓ Yes" if in_this else "",
    })
    prev_t = thresh
bracket_df = pd.DataFrame(bracket_info)
st.dataframe(bracket_df, use_container_width=True, hide_index=True)

st.markdown("---")

# ---------------------------------------------------------------------------
# Quarterly estimated tax schedule
# ---------------------------------------------------------------------------
st.markdown("## Quarterly Estimated Tax Schedule")

quarterly_schedule = pd.DataFrame({
    "Quarter": ["Q1", "Q2", "Q3", "Q4"],
    "Due Date": ["Apr 15", "Jun 15", "Sep 15", "Jan 15 (next year)"],
    "Amount": [quarterly_payment] * 4,
})
st.dataframe(
    quarterly_schedule.style.format({"Amount": "${:,.0f}"}, subset=["Amount"]),
    use_container_width=True,
    hide_index=True,
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Real hourly rate calculator
# ---------------------------------------------------------------------------
st.markdown("## Real Hourly Rate Calculator")

hours_worked = st.number_input("Hours worked on side hustle", value=500, min_value=0, step=50, format="%d")
if hours_worked > 0:
    after_tax_hourly = side_take_home / hours_worked
    st.metric("After-Tax Hourly Rate", f"${after_tax_hourly:,.2f}", f"${side_take_home:,.0f} ÷ {hours_worked} hours")
    st.caption("Your side hustle pay after taxes and expenses.")

st.markdown("---")

# ---------------------------------------------------------------------------
# CTA — Paid products
# ---------------------------------------------------------------------------
st.markdown("""
<div class="cta-box">
    <h3 style="color: white; margin: 0 0 8px 0;">Want the Full Excel Spreadsheet?</h3>
    <p style="margin: 0 0 16px 0;">
        Get the <strong>ClearMetric Side Hustle Tax Estimator</strong> — a downloadable Excel template with:<br>
        ✓ All inputs + tax calculations in one place<br>
        ✓ Expense Tracker (12 months × categories)<br>
        ✓ Quarterly payment schedule<br>
        ✓ How To Use guide
    </p>
    <a href="https://clearmetric.gumroad.com" target="_blank">
        Get It on Gumroad — $12.99 →
    </a>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="cta-box">
    <h3 style="color: white; margin: 0 0 8px 0;">Need Deeper Tax Planning?</h3>
    <p style="margin: 0 0 16px 0;">
        <strong>Freelancer Tax Planner</strong> — $14.99 — Quarterly estimates, deductions, SE tax, full-year projection.
    </p>
    <a href="https://clearmetric.gumroad.com" target="_blank">
        Get Freelancer Tax Planner →
    </a>
</div>
""", unsafe_allow_html=True)

# Cross-sell
st.markdown("### More from ClearMetric")
cx1, cx2, cx3 = st.columns(3)
with cx1:
    st.markdown("""
    **📊 Budget Planner** — $13.99
    Track income, expenses, savings with the 50/30/20 framework.
    [Get it →](https://clearmetric.gumroad.com)
    """)
with cx2:
    st.markdown("""
    **🔥 FIRE Calculator** — $14.99
    Find your FIRE number, scenario comparison, year-by-year projection.
    [Get it →](https://clearmetric.gumroad.com)
    """)
with cx3:
    st.markdown("""
    **💰 Freelance Rate Calculator** — $11.99
    Hourly, day, and project rates. Know your true rate.
    [Get it →](https://clearmetric.gumroad.com)
    """)

# Footer
st.markdown("---")
st.caption("© 2026 ClearMetric | [clearmetric.gumroad.com](https://clearmetric.gumroad.com) | "
           "This tool is for educational purposes only. Not financial advice. Consult a qualified tax professional.")
