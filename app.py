import html
import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st

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
<div class="muted">RESEARCH ONLY · No verified betting edge · No suggested stakes</div></article>''', unsafe_allow_html=True)


def show_board():
    st.title("🏀 WALT'S WAGERS")
    st.markdown("### NCAAB model research")
    st.warning("RESEARCH ONLY — Model forecasts are not certified picks or verified sportsbook lines. Higher win probability does not establish betting value. No staking recommendations.")
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
        st.warning("Snapshot age is unknown, older than 24 hours, or future-dated. Top candidates are withheld until a current snapshot is published.")
    matches = build_matches(data)
    upcoming = [m for m in matches if pd.notna(m["start"]) and m["start"] > now]
    a, b, c = st.columns(3)
    a.metric("Upcoming matchups", len(upcoming))
    b.metric("Published forecast rows", len(data))
    c.metric("Certified picks", 0)
    st.header("Top Bets · Research candidates")
    st.write("Upcoming moneyline candidates ranked by highest model win probability, one per game. This is not an edge ranking. Fair odds are a model calculation, not an available sportsbook price.")
    candidates = sorted([m for m in upcoming if m["hp"] is not None and m["hp"] != m["ap"]], key=lambda m: (-max(m["hp"], m["ap"]), m["start"], m["home"], m["away"])) if fresh else []
    for rank, match in enumerate(candidates[:5], 1):
        render_card(match, rank)
    if not candidates:
        st.info("No eligible research candidates in the current snapshot.")
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
