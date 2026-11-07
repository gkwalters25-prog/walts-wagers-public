"""Public, price-aware owner trial sizing. Never places or records bets."""
import datetime as dt,math
UNIT_FRACTION=.0025
MAX_UNITS=2.
MAX_OPEN_UNITS=4.
def stamp(value):
 t=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
 if t.tzinfo is None:raise ValueError('Timezone required')
 return t.astimezone(dt.timezone.utc)
def implied(odds):
 if not math.isfinite(odds) or abs(odds)<100:raise ValueError('Invalid odds')
 return 100/(100+odds) if odds>0 else -odds/(100-odds)
def edge_grade(edge_pp):
 if not math.isfinite(edge_pp) or edge_pp<5:return None
 for upper,grade in [(6,5),(8,6),(10,7),(12,8),(15,9)]:
  if edge_pp<upper:return grade
 return 10
def grade_units(grade):
 if grade is None or not math.isfinite(grade) or grade<5:return 0.
 return min(MAX_UNITS,1.+.5*(int(grade)-5))
def assess(row,now,review=False):
 try:
  if row.get('market')!='h2h' or row.get('owner_approved') is not True or row.get('certified') is not False or row.get('lineage_verified') is not True:return None
  p=float(row['probability']);odds=float(row['odds']);opposite=float(row['opposite_odds']);be=implied(odds);other=implied(opposite)
  if not math.isfinite(p) or not .6<=p<1 or not -200<=odds<=200 or not .98<=be+other<=1.20:return None
  edge=100*(p-be);ev=p/be-1
  if edge<5 or ev<=0:return None
  updated=stamp(row['quote_updated_utc']);captured=stamp(row['quote_captured_utc']);forecast=stamp(row['prediction_timestamp']);parent=stamp(row.get('parent_prediction_timestamp',row['prediction_timestamp']));start=stamp(row['game_start_utc']);scope_a=stamp(row['scope_start_utc']);scope_z=stamp(row['scope_end_utc'])
  if not scope_a<=start<scope_z or not parent<=forecast<=now or not parent<=captured<=now or updated>captured or forecast>=start or start<=now:return None
  if not 0<(start-parent).total_seconds()<=64800 or not 0<(start-captured).total_seconds()<=64800:return None
  age=(now-updated).total_seconds()
  if not 0<=age<=(14400 if review else 1800) or not 0<=(now-parent).total_seconds()<=14400:return None
  grade=edge_grade(edge);return {**row,'edge_pp':edge,'expected_roi':ev,'grade':grade,'grade_units':grade_units(grade),'quote_age_seconds':age,'review_only':age>1800,'certified':False}
 except (KeyError,TypeError,ValueError,OverflowError):return None
def allocate(rows,now,open_units=0.):
 if not math.isfinite(open_units) or not 0<=open_units<=MAX_OPEN_UNITS:raise ValueError('Open exposure must be0–4u')
 valid=[q for r in rows if (q:=assess(r,now)) is not None];valid.sort(key=lambda q:(-q['grade'],-q['expected_roi'],stamp(q['game_start_utc']),str(q['event_id']),q['sportsbook']))
 seen=set();result=[];remaining=MAX_OPEN_UNITS-open_units
 for q in valid:
  if q['event_id'] in seen:continue
  seen.add(q['event_id']);stake=min(q['grade_units'],remaining);remaining=max(0.,remaining-stake);result.append({**q,'suggested_units':stake,'budget_limited':stake<q['grade_units']})
 return result
