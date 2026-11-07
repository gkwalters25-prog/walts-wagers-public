import html
import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st
from trial_policy import allocate, assess, UNIT_FRACTION
from moneyline_candidates import candidates as priced_candidates, in_range

BASE = Path(__file__).resolve().parent
st.set_page_config(page_title="Walt's Wagers · NCAAB", page_icon="🏀", layout="wide")
st.markdown('''<style>
.stApp {background:#0b1220;color:#f8fafc;color-scheme:dark}
.block-container {max-width:1400px;padding-top:2rem}
h1,h2,h3,p,label {color:#f8fafc}
[data-testid="stMarkdownContainer"] p {font-size:1.12rem;line-height:1.6}
[data-testid="stCaptionContainer"] p {color:#cbd5e1;font-size:1rem}
[data-testid="stWidgetLabel"] p {color:#f8fafc;font-size:1.1rem}
input {background:#17243a!important;color:#fff!important;font-size:1.1rem!important}
input::placeholder {color:#cbd5e1!important;opacity:1!important}
[data-testid="stMetric"] {background:#17243a;border:1px solid #64748b;border-radius:14px;padding:18px}
[data-testid="stMetricLabel"] * {color:#e2e8f0!important}
[data-testid="stMetricValue"] {color:#6ee7b7}
.ww-card {background:#17243a;border:1px solid #64748b;border-radius:16px;padding:24px;margin:16px 0;color:#f8fafc}
.ww-card h3 {font-size:1.5rem;margin:8px 0;color:#fff}
.ww-card .muted {color:#cbd5e1;font-size:1.05rem}
.ww-card .big {font-size:2rem;font-weight:750;color:#6ee7b7}
.ww-card .teams {display:grid;grid-template-columns:1fr 1fr;gap:24px;margin:20px 0}
.ww-card .team {font-size:1.25rem;font-weight:700}
.ww-badge {color:#0b1220;background:#fcd34d;padding:5px 10px;border-radius:6px;font-weight:750;display:inline-block}
@media(max-width:600px){.ww-card .teams{grid-template-columns:1fr}.ww-card{padding:18px}}
</style>''', unsafe_allow_html=True)


def esc(value):
    return html.escape(str(value), quote=True)


def number(value, digits=1):
    return f"{value:.{digits}f}" if value is not None else "Unavailable"


def first(group, field):
    if field not in group:
        return None
    values = pd.to_numeric(group[field], errors="coerce").dropna()
    if values.empty:
        return None
    unique = values.unique()
    if len(unique) != 1 or not math.isfinite(float(unique[0])):
        return None
    return float(unique[0])


def probability_pair(group):
    for field in ("home_win_probability", "away_win_probability"):
        if field in group:
            values = pd.to_numeric(group[field], errors="coerce")
            supplied = group[field].notna()
            if any(not math.isfinite(float(v)) or not 0 < v < 1 for v in values[supplied]) or len(values.dropna().unique()) > 1:
                return None, None
    hp, ap = first(group, "home_win_probability"), first(group, "away_win_probability")
    if hp is None and ap is not None:
        hp = 1 - ap
    if ap is None and hp is not None:
        ap = 1 - hp
    if hp is None or ap is None or not (0 < hp < 1 and 0 < ap < 1) or abs(hp + ap - 1) > .001:
        return None, None
    return hp, ap


def fair_odds(p):
    return f"{-100*p/(1-p):.0f}" if p >= .5 else f"+{100*(1-p)/p:.0f}"


def market(group, name):
    return first(group[group.market.eq(name)], "forecast_value")


def build_matches(data):
    matches = []
    for (start, away, home), group in data.groupby(["game_start_utc", "away_team", "home_team"], sort=True, dropna=False):
        dt = pd.to_datetime(start, utc=True, errors="coerce")
        hp, ap = probability_pair(group)
        matches.append(dict(start=dt, away=str(away), home=str(home), hp=hp, ap=ap, group=group))
    return matches


def when(match):
    dt = match["start"]
    return dt.tz_convert("America/New_York").strftime("%b %d, %Y · %I:%M %p ET") if pd.notna(dt) else "Time unavailable"


def render_card(match, rank=None):
    hp, ap, group = match["hp"], match["ap"], match["group"]
    total = market(group, "totals")
    if total is None:
        total = first(group, "projected_total")
    margin = first(group, "projected_home_margin")
    home_pts, away_pts = market(group, "team_totals_home"), market(group, "team_totals_away")
    if total is not None and margin is not None:
        home_pts = home_pts if home_pts is not None else (total + margin) / 2
        away_pts = away_pts if away_pts is not None else (total - margin) / 2
    lead = ""
    if rank is not None:
        p, team = (hp, match["home"]) if hp >= ap else (ap, match["away"])
        lead = f'<div class="ww-badge">RESEARCH CANDIDATE #{rank}</div><h3>{esc(team)}</h3><div class="big">{p:.1%} model win probability</div><p>Model fair moneyline: {fair_odds(p)} · Sportsbook odds: unavailable</p>'
    prob = lambda p: f"{p:.1%}" if p is not None else "Unavailable"
    spread = f"{-margin:+.1f}" if margin is not None else "Unavailable"
    st.markdown(f'''<article class="ww-card">{lead}
<h3>{esc(match['away'])} at {esc(match['home'])}</h3><div class="muted">{esc(when(match))}</div>
<div class="teams"><div><div class="muted">AWAY</div><div class="team">{esc(match['away'])}</div><div class="big">{number(away_pts)}</div>Projected points · Win probability {prob(ap)}</div>
<div><div class="muted">HOME</div><div class="team">{esc(match['home'])}</div><div class="big">{number(home_pts)}</div>Projected points · Win probability {prob(hp)}</div></div>
<p>Home projected spread: <strong>{spread}</strong> · Projected total: <strong>{number(total)}</strong></p>
<div class="muted">RESEARCH PROJECTION · No verified betting edge · No stake attached to this projection</div></article>''', unsafe_allow_html=True)


@st.fragment(run_every="60s")
def show_trial():
    st.header("Moneyline trial · graded stakes")
    st.warning("Owner-approved trial · Statistical certification pending. Grades reflect estimated price edge, not a validated confidence level. No bets are placed by this site.")
    st.markdown("**Grade 5: 1u · Grade 6: 1.5u · Grades 7–10: 2u maximum.** 1u = 0.25% of your fixed starting bankroll; 2u = 0.50%. There is no total open-exposure limit.")
    with st.expander("Grade bands and trial evidence"):
        st.table(pd.DataFrame({"Model edge above break-even":["5–<6 percentage points","6–<8 pp","8–<10 pp","10–<12 pp","12–<15 pp","15+ pp"],"Grade":[5,6,7,8,9,10],"Maximum stake":["1u","1.5u","2u","2u","2u","2u"]}), alt="Owner-defined edge grades and stakes capped at two units")
        st.caption("Examined early-season calibration study: 202 selections, +10.75% flat-stake paper ROI, adjusted interval −5.86% to +28.59%, selected calibration gap 8.02%. These do not establish a reliable betting advantage. Trial scope is the opening 27-day window, with games within 18 hours of the forecast and quote capture; other markets stay research-only.")
    bankroll = st.number_input("Starting trial bankroll ($, optional)", min_value=0.0, value=0.0, step=100.0, key="trial_bankroll", help="Used only for this viewer's stake calculation; not sent to a betting account or published into the snapshot.")
    if bankroll:
        st.caption(f"1u = ${bankroll*UNIT_FRACTION:,.2f} · 2u cap = ${bankroll*UNIT_FRACTION*2:,.2f}. Skip a bet if the bookmaker minimum exceeds your stake limit.")
    try:
        payload = json.loads((BASE / "data" / "trial.json").read_text(encoding="utf-8-sig"))
        rows = payload["rows"]
        if not isinstance(rows, list):
            raise ValueError("Invalid trial snapshot")
        rows = [r for r in rows if isinstance(r, dict) and in_range(r.get("odds"))]
    except (OSError, ValueError, KeyError, TypeError):
        st.info("Trial policy is ready. No reviewed price snapshot is published yet.")
        return
    current = pd.Timestamp.now(tz="UTC").to_pydatetime()
    st.caption(f"Odds captured: {payload.get('quote_captured_utc', 'Unavailable')} · Manual snapshot publication · Eligibility checked every minute")
    picks = allocate(rows, current)
    funded = [q for q in picks if q["suggested_units"] > 0]
    if funded:
        for q in funded:
            with st.container(border=True):
                st.subheader(f"{q['selection']} · Grade {q['grade']} · {q['suggested_units']:g}u")
                start = pd.Timestamp(q["game_start_utc"]).tz_convert("America/New_York").strftime("%b %d · %I:%M %p ET")
                st.markdown(f"**{q['away_team']} at {q['home_team']}** · {start}")
                st.markdown(f"{q['sportsbook']} **{float(q['odds']):+.0f}** · Trial-adjusted win probability **{q['probability']:.1%}** · Estimated edge **{q['edge_pp']:.1f} pp**")
                stake = f" · ${bankroll*UNIT_FRACTION*q['suggested_units']:,.2f}" if bankroll else ""
                st.caption(f"Suggested manual stake: {q['suggested_units']:g}u{stake} · Quote age {q['quote_age_seconds']/60:.0f} min · Recheck the offered price before betting")
    else:
        st.info("No stake-qualified moneylines at current prices. Missing, expired or started-game quotes receive no stake.")
    st.caption(f"Suggested across current qualifying games: {sum(q['suggested_units'] for q in picks):g}u · No aggregate exposure limit · Maximum 2u per bet")
    review = [q for r in rows if (q := assess(r, current, review=True)) is not None and q["review_only"]]
    if review:
        with st.expander(f"{len(review)} price checks needed · no current stake"):
            st.caption("Quotes remain visible for up to four hours for review. After 30 minutes a fresh price is required before any stake is suggested.")
            for q in review[:10]:
                st.markdown(f"**{q['selection']}** · {q['sportsbook']} {float(q['odds']):+.0f} · quote {q['quote_age_seconds']/3600:.1f}h old · **recheck odds**")


@st.fragment(run_every="60s")
def show_top_moneylines():
    st.header("Top Bets · Moneyline research candidates")
    st.markdown("**Sportsbook price range: −250 to +200 (inclusive).** Ranked by estimated model edge above the offered price’s break-even probability, one selection per game. These are research candidates, not statistically certified picks.")
    st.caption("Current candidates require a quote no older than 30 minutes, a forecast no older than 24 hours, and a game that has not started. Model fair odds are not sportsbook prices. Quote eligibility refreshes every minute; odds publication is manual.")
    try:
        payload = json.loads((BASE / "data" / "odds.json").read_text(encoding="utf-8-sig"))
        rows = payload["rows"]
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
            raise ValueError("Invalid odds snapshot")
    except (OSError, ValueError, KeyError, TypeError):
        st.info("No sportsbook odds snapshot is published. No moneyline candidates are shown without a price.")
        return
    now = pd.Timestamp.now(tz="UTC").to_pydatetime()
    captured = pd.to_datetime([r.get("quote_captured_utc") for r in rows], utc=True, errors="coerce")
    last_capture = captured.max() if len(captured) else pd.to_datetime(payload.get("last_source_quote_captured_utc"), utc=True, errors="coerce")
    st.caption(f"Latest sportsbook snapshot capture: {last_capture if pd.notna(last_capture) else 'Unknown'} · Source quote timestamps preserved")
    picks = priced_candidates(rows, now)
    if not picks:
        st.info("No current moneylines qualify between −250 and +200. Quotes may be missing, stale, outside your range, or lack a positive estimated edge.")
    for rank, q in enumerate(picks[:5], 1):
        p = q["probability"]
        start = pd.Timestamp(q["game_start_utc"]).tz_convert("America/New_York").strftime("%b %d · %I:%M %p ET")
        st.markdown(f'''<article class="ww-card"><div class="ww-badge">RESEARCH CANDIDATE #{rank}</div>
<h3>{esc(q['selection'])} · {q['odds']:+.0f}</h3><p><strong>{esc(q['sportsbook'])}</strong> · {esc(q['away_team'])} at {esc(q['home_team'])} · {esc(start)}</p>
<div class="big">{p:.1%} model win probability</div>
<p>Price break-even: <strong>{q['break_even']:.1%}</strong> · Estimated edge: <strong>{q['edge_pp']:+.1f} percentage points</strong> · Model fair moneyline: {fair_odds(p)}</p>
<p class="muted">Book updated: {esc(q['quote_updated_utc'])} · Captured: {esc(q['quote_captured_utc'])} · Quote age: {q['quote_age_minutes']:.0f} min</p>
<div class="muted">RESEARCH ONLY · Recheck the available price · No stake attached to this candidate</div></article>''', unsafe_allow_html=True)
    review = priced_candidates(rows, now, review=True)
    if review:
        with st.expander(f"{len(review)} older price checks · excluded from current Top Bets"):
            st.caption("These quotes are 30 minutes to four hours old. They are historical price checks, not current offers.")
            for q in review[:10]:
                st.write(f"{q['selection']} · {q['sportsbook']} {q['odds']:+.0f} · {q['quote_age_minutes']:.0f} min old · recheck price")


def show_board():
    st.title("🏀 WALT'S WAGERS")
    st.markdown("### NCAAB forecasts and owner-approved moneyline trial")
    show_top_moneylines()
    show_trial()
    try:
        data = pd.read_csv(BASE / "data" / "forecasts.csv", low_memory=False)
        required = {"game_start_utc", "away_team", "home_team", "market", "forecast_value"}
        if not required.issubset(data.columns):
            st.error("Published snapshot has an unsupported format.")
            return
    except (OSError, ValueError, pd.errors.ParserError):
        st.error("Published forecast snapshot is unavailable or unreadable.")
        return
    try:
        meta = json.loads((BASE / "data" / "status.json").read_text(encoding="utf-8-sig"))
        stamp = pd.to_datetime(meta.get("generated_utc"), utc=True, errors="coerce")
    except (OSError, ValueError, TypeError):
        stamp = pd.NaT
    now = pd.Timestamp.now(tz="UTC")
    fresh = pd.notna(stamp) and pd.Timedelta(0) <= now - stamp <= pd.Timedelta(hours=24)
    st.caption("Snapshot: " + (str(stamp) if pd.notna(stamp) else "Unknown") + " · Refresh publication is manual")
    if not fresh:
        st.warning("Forecast board snapshot age is unknown, older than 24 hours, or future-dated. Treat these projections as outdated; Top Bets validates its separate odds and forecast timestamps.")
    matches = build_matches(data)
    upcoming = [m for m in matches if pd.notna(m["start"]) and m["start"] > now]
    a, b, c = st.columns(3)
    a.metric("Upcoming matchups", len(upcoming))
    b.metric("Published forecast rows", len(data))
    c.metric("Statistically certified picks", 0)
    st.header("Matchup board")
    search = st.text_input("Search teams", placeholder="Kentucky, Louisville, Duke…")
    include_past = st.checkbox("Include started games and games with unknown start times", value=False)
    limit = st.select_slider("Matchups displayed", options=[10, 20, 40, 80, 160, 320], value=20)
    filtered = [m for m in (matches if include_past else upcoming) if search.casefold() in (m["away"] + " " + m["home"]).casefold()]
    st.caption(f"{len(filtered)} matching matchups · Search applies to this board; Top Bets ranks the whole upcoming slate.")
    for match in filtered[:limit]:
        render_card(match)


if __name__ == "__main__":
    show_board()



