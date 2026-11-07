# Walt's Wagers public viewer

NCAAB projections and an owner-approved early-season moneyline trial.
Statistical certification remains pending; grades are owner-defined estimated-price-edge bands, not a validated confidence scale.

## Trial sizing

- Grade5:1u; grade6:1.5u; grade7–10:2u maximum.
- 1u=0.25% of a fixed starting dedicated bankroll; no aggregate open-exposure limit.
- Each qualifying game receives its full graded stake up to2u, regardless of other open positions. This viewer does not track accounts or place bets.
- One position per game, within18hours of the original forecast and quote capture. Original selection filters remain probability60%+, edge5pp+, positive estimatedEV and moneyline−200to+200.
- Quotes must be at most30minutes old for stake suggestions; up to4hours old may be shown only for price review, without a current stake. Started games and unsupported forecasts are withheld.

The trial uses a separately fitted earlier-season calibration and is restricted to the opening27-day season window. It does not change the private production model or its statistical certification status.

## Deployment

Python3.13 with pinned requirements; Streamlit entrypoint `app.py`.
Snapshot publication is manual. Eligibility refreshes once per minute while a session is active; that does not fetch new sportsbook odds.
Public data contains only allowlisted derived forecasts and reviewed quote cards. No private database, model parameters, training features, bankroll, tracker, credentials or licensed raw response archives belong in this repository.
No cloud credentials or connections to betting accounts are required.




## Owner-approved team-total manual trial

4pp minimum edge, no EV filter; 56–under60% =1u,60–under65%=2u,65%+=3u. Exactly65% is3u. No aggregate exposure cap; one position/team/game. Scientific certification remains pending. The public snapshot currently contains no team-total picks because latest reviewed source inputs have0–2games/team, below required5, and a verified direct feature context is not yet published. Eligibility refresh is not an odds fetch or new model run. Private estimator parameters, licensed feature vectors and API keys are not published.
