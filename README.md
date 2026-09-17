# Learning Futures Insight Hub

A Python desktop application for analysing learner feedback, exploring survey insights, and generating human-reviewed evaluation reports.

The application uses Tkinter and runs in its own desktop window. It includes synthetic demonstration data and works locally without API keys or external AI services.

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

The first launch creates a local Python environment and installs dependencies; internet access is required for setup. Later launches reuse that environment. The demo data loads automatically.

Your folder path does not need to match Heet's PC. After cloning, all application files are inside `learning-futures-insight-hub/ai-learning-evaluation`.

If you do not want to install Git, download and extract the repository ZIP from GitHub, open `ai-learning-evaluation`, and double-click `START_DEMO.cmd`.

## What to try

- Review dashboard metrics and rating charts.
- Select a course and inspect searchable, masked survey responses.
- Explore themes and their supporting comments.
- Generate and edit a facilitator or client report.
- Enter a reviewer name, confirm review, and export Word or Markdown.
- Ask the local data assistant about the selected scope.

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
