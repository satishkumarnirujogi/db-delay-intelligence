# DB Delay Intelligence

Live Deutsche Bahn delay pipeline for 15 stations: DB Timetables API + Open-Meteo → GitHub Actions → Supabase → dbt → LightGBM → Power BI. €0/month.

Full build guide: [docs/DB_Delay_Intelligence_Workflow_Guide.md](docs/DB_Delay_Intelligence_Workflow_Guide.md) · Status: [docs/PROGRESS.md](docs/PROGRESS.md)

## Local setup

```bash
python -m venv .venv          # Python 3.11
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # then fill in values
python -m ingestion.explore   # Step 1
```

Data: Deutsche Bahn (CC BY 4.0) · Weather data by Open-Meteo.com
