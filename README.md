# Walt's Wagers public viewer

Research-only NCAAB projections. No certified picks, verified sportsbook edge, or suggested stakes.
Top candidates rank upcoming games by model win probability and require a snapshot no older than 24 hours.
Snapshot time is the original publication time; packaging does not refresh it.

## Run

Use Python 3.13 with the pinned requirements, then `streamlit run app.py`.

## Streamlit Community Cloud

Upload these seven files, preserving folders, to a dedicated `walts-wagers-public` GitHub repository.
Select that repository, its branch, and `app.py` in Streamlit Community Cloud.
Select Python 3.13 in Advanced settings. No application secrets are required.

This repository has no connection to the private database, model, tracker, Sheets, or scheduled tasks.
Snapshot publication remains manual. To update, review and replace only the two public data files.
Do not upload the parent project, installer reports, backups, publisher, credentials, or private files.
