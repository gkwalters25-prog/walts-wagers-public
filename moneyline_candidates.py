"""Price-aware research only. No staking, account access, or network calls."""
import math
from datetime import datetime, timezone

MIN_ODDS = -250
MAX_ODDS = 200
MAX_QUOTE_SECONDS = 1800
MAX_FORECAST_SECONDS = 86400


def in_range(value):
    try:
        odds = float(value)
        return math.isfinite(odds) and (MIN_ODDS <= odds <= -100 or 100 <= odds <= MAX_ODDS)
    except (TypeError, ValueError):
        return False


def stamp(value):
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return parsed.astimezone(timezone.utc)


def implied(odds):
    return -odds / (100 - odds) if odds < 0 else 100 / (100 + odds)


def candidates(rows, now, review=False):
    valid = []
    for row in rows:
        try:
            if row.get('market') != 'h2h' or not in_range(row.get('odds')):
                continue
            odds, p = float(row['odds']), float(row['probability'])
            if not math.isfinite(p) or not 0 < p < 1:
                continue
            side = row['selection_side']
            if side not in ('home', 'away') or row['selection'] != row[side + '_team']:
                continue
            if not all(isinstance(row[k], str) and 0 < len(row[k].strip()) <= 160 for k in ('event_id', 'selection', 'home_team', 'away_team', 'sportsbook')):
                continue
            start, forecast, updated, captured = (stamp(row[k]) for k in ('game_start_utc', 'prediction_timestamp', 'quote_updated_utc', 'quote_captured_utc'))
            age = (now - updated).total_seconds()
            if start <= now or not forecast < start or not updated <= captured <= now or not 0 <= (now - forecast).total_seconds() <= MAX_FORECAST_SECONDS:
                continue
            if not 0 <= age <= (14400 if review else MAX_QUOTE_SECONDS):
                continue
            if review and age <= MAX_QUOTE_SECONDS:
                continue
            be = implied(odds)
            edge = 100 * (p - be)
            if edge <= 0:
                continue
            valid.append({**row, 'odds': odds, 'probability': p, 'break_even': be, 'edge_pp': edge, 'expected_roi': p / be - 1, 'quote_age_minutes': age / 60, 'review_only': review})
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    valid.sort(key=lambda q: (-q['edge_pp'], -q['expected_roi'], q['game_start_utc'], q['event_id'], q['sportsbook']))
    seen = set()
    result = []
    for row in valid:
        # IDs and exact matchup keys protect against repeated bookmaker rows.
        key = (row['game_start_utc'], row['away_team'], row['home_team'])
        if row['event_id'] in seen or key in seen:
            continue
        seen.update((row['event_id'], key))
        result.append(row)
    return result
