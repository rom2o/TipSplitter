# TipSplitter

A restaurant tip splitting web app, deployed as a PWA on Railway.

## What it does — 3/10 complexity

- **Single-user web app** — one restaurant, one PIN, one database, no accounts to manage
- **Tip splitting logic** — cash and card tips split across staff per shift, 30% card deduction applied automatically
- **Weekly view** — Monday to Sunday, lunch/dinner shifts per day, staff selection per shift
- **CSV import** — detects columns automatically from any Square POS export, splits tips into lunch/dinner by transaction time (5 PM cutoff), saves directly into the right shifts
- **Summary & history** — weekly breakdown per staff member, past weeks stored and browsable
- **Export** — download the week as a CSV for your records
- **PWA setup** — installable on iPhone home screen, runs full-screen like a native app, custom branding throughout
- **PIN protection** — simple lock screen so only you can access it
- **Deployed on Railway** — live on the internet, auto-deploys every time a change is pushed to GitHub

## Stack

- **Backend**: Python / Flask + SQLite
- **Frontend**: Vanilla HTML/CSS/JavaScript (no framework)
- **Deployment**: Railway (auto-deploy from GitHub)

## Local development

```bash
pip install -r requirements.txt
python app.py
```
