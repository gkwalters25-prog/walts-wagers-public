"""Owner-approved manual TT suggestions; never an automated bet instruction."""
import datetime as dt,math
CANDIDATE_SHA256='70fccfe03d5735ab42676e57dc55d9d82294e011207198126ed12f1b71d1a538'
UNIT_FRACTION=.0025
def units(probability,edge):
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in [probability,edge]):return 0.
    if not .56<=probability<=1 or edge<.04-1e-12:return 0.
    return 3. if probability>=.65 else 2. if probability>=.60 else 1.
def stamp(value):
    t=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if t.tzinfo is None:raise ValueError('Timezone required')
    return t.astimezone(dt.timezone.utc)
def assess(row,now):
    """Withhold unsupported current inputs. Historical replay uses units only."""
    out={'owner_trial_approved':True,'scientifically_certified':False,'suggested_units':0.,'automated_bet_placement':False,'status':'WITHHELD'}
    try:
        if row['candidate_sha256']!=CANDIDATE_SHA256:return out
        if row.get('input_lineage_verified') is not True:return out
        counts=[row.get('history_games_home',0),row.get('history_games_away',0)]
        if any(isinstance(n,bool) or not isinstance(n,int) or n<0 for n in counts):return out
        if min(counts)<5:
            if row.get('history_mode')!='KENPOM_PRIOR_ASSISTED_V1' or row.get('prior_assisted') is not True or row.get('prior_source_verified') is not True:return out
            pin=row.get('prior_source_sha256','')
            if len(pin)!=64 or any(c not in '0123456789abcdef' for c in pin):return out
            if stamp(row['prior_captured_utc'])>stamp(row['parent_forecast_utc']):return out
        if row['market']!='team_totals' or row['side'] not in ('over','under') or row['selection_team']!=row['matched_team']:return out
        p=float(row['selection_probability']);odds=float(row['odds']);other=float(row['opposite_odds']);line=float(row['line']);otherline=float(row['opposite_line'])
        if not all(math.isfinite(v) for v in [p,odds,other,line,otherline]) or min(abs(odds),abs(other))<100 or line!=otherline or abs(line*2-round(line*2))>1e-8 or round(line*2)%2!=1:return out
        implied=lambda o:100/(o+100) if o>0 else -o/(100-o)
        be=implied(odds)
        if not .98<=be+implied(other)<=1.20:return out
        updated=stamp(row['quote_updated_utc']);captured=stamp(row['quote_captured_utc']);forecast=stamp(row['parent_forecast_utc']);start=stamp(row['game_start_utc'])
        if not updated<=captured<=now<start or not forecast<=captured or not 0<=(now-updated).total_seconds()<=1800 or not 0<=(now-forecast).total_seconds()<=14400:return out
        if not 0<(start-forecast).total_seconds()<=64800 or not 0<(start-captured).total_seconds()<=64800:return out
        amount=units(p,p-be)
        if amount:out.update(suggested_units=amount,status='OWNER_APPROVED_MANUAL_TRIAL',probability=p,edge=p-be)
    except (KeyError,TypeError,ValueError,OverflowError):pass
    return out
def allocate(rows,now):
    """No aggregate exposure cap; at most one position per team/game."""
    qualified=[]
    for row in rows:
        decision=assess(row,now)
        if decision['suggested_units']>0:qualified.append({**row,**decision})
    qualified.sort(key=lambda r:(-r['edge'],-r['probability'],str(r.get('sportsbook','')),str(r.get('event_id',''))))
    seen=set();out=[]
    for row in qualified:
        key=(row['event_id'],row['matched_team'])
        if key not in seen:seen.add(key);out.append(row)
    return out
