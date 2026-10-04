# Learning Futures Insight Hub

A Python desktop application for analysing learner feedback, exploring survey insights, and generating human-reviewed evaluation reports.

The application uses Tkinter and runs in its own desktop window. Imports, calculated metrics
and the survey overview work without an API key. Generated insights, answers and report
drafts use the configured Gemini service.

The app opens with an empty workspace and **PENDING** metric cards. Use **Import CSV / Excel**
to load survey data. A bold uppercase filename beside the import button shows the file
being processed and remains visible after loading. Startup does not automatically load
demo data or the configured `EVALUATION_DATA_PATH`.
The dashboard analyses all responses in the imported files together; there is no course-scope dropdown.

## Gemini insights and Excel imports

Import one or more `.csv`, `.xlsx` or `.xls` survey files with **Import CSV / Excel**.
Excel data is read from the first worksheet. Supported layouts are the canonical
survey schema and the Qualtrics exports with question-text and ImportId header rows,
including the supplied 2023–2025 course formats. Other layouts need column mapping.

**Explore data → Insights & suggestions** shows local evidence and suggested
next steps immediately. To enable Gemini interpretation:

1. Get an API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. For native Python, copy `ai-learning-evaluation/.env.example` to
   `ai-learning-evaluation/.env`; set `GEMINI_API_KEY`. For Docker, use the root `.env`.
3. Keep `GEMINI_MODEL=gemini-2.5-flash-lite`, or set another supported model.
4. Restart the app (Docker: `docker compose up -d --force-recreate`) and select **Get insights**.

Gemini powers **Get insights**, **Ask** and **Get draft**, without mode selectors
or repeated processing-approval prompts. Insights include
findings, suggested actions, supporting calculated evidence and limitations. Requests
run in the background; repeated insights reuse a session cache. Errors leave local
analysis available. Evidence IDs are validated, but AI interpretations still require
human review. In **Themes & evidence → Ask a question**, clicking Ask sends the question (with obvious contact details masked)
and the selected scope's calculated evidence to Gemini. Answers show their
scope and supporting evidence. Each question is independent; no chat history is sent.
Avoid personal details in questions.
Unavailable evidence is explained rather than guessed; errors are displayed without
silently substituting a local answer. Revision workflows remain separate.

Interface labels use product terms instead of provider/model branding. A separate
**Data use** link explains external processing and submitted information without interrupting
the workflow. Internal provider identifiers are retained. Reports retain an **Analysis method**
section and require human review before approval. Feedback revisions offer basic edits and
manual replacement; provider selections and the external-editor shortcut are removed.

Gemini receives calculated rating summaries and fixed-vocabulary theme counts, without
raw comments, learned keywords, learner IDs, course names or filenames. Source text is
treated as data, never instructions. The recommendation indicator from Qualtrics means
a score of 7 or above; it is **not NPS**. Theme frequencies count matching comments,
not unique learners. No course trends or causal effects are inferred automatically.

Google lists a [free tier for Gemini 2.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash-lite)
subject to project quotas and availability. This is not unlimited free usage: a project
with billing enabled can incur charges. Google says free-tier content may be used to
improve its products. Use only data approved for this processing and keep the key in
the ignored `.env` file. No key is bundled with the app.

## Docker quick start (recommended for teammates)

Install and start Docker Desktop, then run from your cloned repository root:

```sh
docker compose up --build -d --wait
```

Open [the local desktop demo](http://localhost:6080/vnc.html?autoconnect=true&resize=scale). Python and Tk run inside the container, so teammates do not need a host Python installation. See [DOCKER.md](DOCKER.md) for cloning, file exchange through `shared`, updates, optional Azure AI and troubleshooting.

**New: Feedback & revisions** in Report studio lets you enter feedback, preview a section revision, apply it and undo it. Offline edits cover shortening, bullet formatting and plain-language substitutions. Free-form AI revisions require the optional Azure configuration and explicit external-processing consent.

## Get the project on your PC (native Python alternative)

Install Git and Python 3.13 with Tkinter support. Open Command Prompt in the folder where you want to keep the project, then run:

```cmd
git clone https://github.com/heet579/learning-futures-insight-hub.git
cd learning-futures-insight-hub\ai-learning-evaluation
START_DEMO.cmd
```

The first launch creates a local Python environment and installs dependencies; internet access is required for setup. Later launches reuse that environment. Import a survey file to populate the dashboard.

Your folder path does not need to match Heet's PC. After cloning, all application files are inside `learning-futures-insight-hub/ai-learning-evaluation`.

If you do not want to install Git, download and extract the repository ZIP from GitHub, open `ai-learning-evaluation`, and double-click `START_DEMO.cmd`.

## What to try

- Review dashboard metrics and rating charts.
- Inspect searchable, masked survey responses from the imported files.
- Explore themes and their supporting comments.
- Generate and edit a facilitator or client report.
- Enter a reviewer name, confirm review, and export Word or Markdown.
- Ask questions about the imported survey data.

See the [teammate testing checklist](ai-learning-evaluation/TEAM_TESTING.md) and [application guide](ai-learning-evaluation/README.md).

## Get updates

Close the app. From your cloned repository folder:

```cmd
git pull --ff-only
cd ai-learning-evaluation
.venv\Scripts\python.exe -m pip install -r requirements.txt
START_DEMO.cmd
```

If you have local code changes, commit them on your own branch before updating. Do not discard changes just to make a pull succeed.

## Contribute changes

Public access allows everyone to clone and test. Heet must grant collaborator access for teammates to push branches to this repository. Without write access, fork the repository and submit a pull request from your fork.

For collaborators, from the repository root:

```cmd
git switch -c teammate/your-name-short-description
```

Make your changes, then run the tests:

```cmd
cd ai-learning-evaluation
.venv\Scripts\python.exe -m pytest -q
cd ..
```

Review and commit your changes:

```cmd
git status
git add ai-learning-evaluation
git commit -m "Describe your change"
git push -u origin teammate/your-name-short-description
```

Replace `your-name-short-description` with your own branch name. Open a pull request on GitHub for review before merging into `main`.

## Repository layout

```text
learning-futures-insight-hub/
  README.md
  .gitignore
  ai-learning-evaluation/
    app.py
    START_DEMO.cmd
    requirements.txt
    src/
    tests/
    data/
    TEAM_TESTING.md
```

## Data and test notes

Use the included synthetic data for shared testing. Do not commit real learner records, credentials, local environments or generated private reports. Local copies and exported reports do not synchronise automatically.

The desktop has been tested on Windows with Python 3.13.5, including 30 automated tests. Other operating systems require their own verification; see the application guide for setup.

## macOS teammates

After installing Python 3.13 from python.org, use a separate Mac environment from inside `ai-learning-evaluation`:

```sh
PYTHON=python3.13 DEMO_ENV=.venv-mac bash run_demo.sh
```

For blank-screen troubleshooting and diagnostics, see [TEAM_TESTING.md](ai-learning-evaluation/TEAM_TESTING.md#macos-blank-or-grey-window). The app checks the environment actually used, including when an older virtual environment already exists.
