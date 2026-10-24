# Insight Hub in the browser

The same workflow as the desktop app, in a browser, served by the API server (`server/`).
Reports are saved in the same format, so a draft started in the browser can be continued in the
desktop app and the other way round.

## Run it on your computer

From `ai-learning-evaluation`:

```sh
pip install -r server/requirements.txt
python web.py
```

Your browser opens `http://127.0.0.1:8000`. With `DATABASE_URL` in `.env` it uses the shared Neon
database, so you sign in with your normal account and see the same reports as the desktop app.
`GEMINI_API_KEY` in `.env` enables Gemini drafts, insights, questions and section rewrites; without
it drafts use fixed local wording. Press **Ctrl+C** in the terminal to stop it.

Use the full-screen button at the top right (or F11) for a distraction-free review.

## The journey

1. **Start a new report**: drop one or more survey exports (CSV or Excel).
2. **Data**: headline numbers, ratings, Gemini insights, ask a question, browse masked responses.
3. **Themes**: read the comments behind each theme, keep it (fix its category) or leave it out.
4. **Draft**: choose facilitator or client, create the draft, edit it or improve a section
   (Gemini, quick edit or your own wording) with a before/after preview.
5. **Check**: one statement or quote at a time. *Looks right* (A) or *Remove it* (R); arrows move
   between statements. Numbers are matched against the data; anything that doesn't match can only
   be removed or fixed.
6. **Send**: a checklist shows what is left; then *Send for review*.
7. **Review (administrators)**: read the report with the author's decisions alongside, then approve
   or send it back with notes. The author sees the notes on their report and in their list.
8. **Download** the approved report as Word or Markdown, with its review record page.

Administrators also get **Accounts** (approve sign-ups, roles, disable, reset passwords). Everyone has
**Profile and password** in the avatar menu.

## Google sign-in in the browser

Browsers need a Google OAuth client of type **Web application** (the desktop app's client type does not
work in a browser). In Google Cloud → Clients → Create client → *Web application*, add these
**Authorised JavaScript origins**: `http://127.0.0.1:8000`, `http://localhost:8000` and, when
deployed, `https://learning-futures-insight-hub.onrender.com`. Put its client ID in `.env` (and in
Render) as `GOOGLE_WEB_CLIENT_ID`. The Google button appears on the sign-in page once it is set.

## Privacy

Uploaded survey files are analysed on the server and stored with the report (including the comments
needed to reopen it), exactly like reports saved from the desktop app in shared mode. Use synthetic data
until Learning Futures approves storing real survey data in the hosted database.
