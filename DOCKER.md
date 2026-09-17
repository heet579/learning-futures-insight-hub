# Docker team demo

## Run from Git (Windows, macOS or Linux)

Install and start Docker Desktop (or Docker Engine with Compose on Linux), using Linux containers. Then:

```sh
git clone https://github.com/heet579/learning-futures-insight-hub.git
cd learning-futures-insight-hub
docker compose up --build -d --wait
```

Open http://localhost:6080/vnc.html?autoconnect=true&resize=scale in your browser. The first build downloads Python, desktop libraries and application dependencies. The browser displays the existing Python desktop application using noVNC; this is not Streamlit or a rewrite of the application as a website.

If Docker reports that it cannot connect to its daemon, open Docker Desktop and wait until its Linux engine is running. This is a host setup issue, before any application code runs.

For an existing clone, close/save any draft, run `git pull --ff-only` in the repository root, then `docker compose up --build -d --wait`.

## Open files and keep exported reports

1. Put a CSV in the `shared` folder next to `compose.yaml` on your computer.
2. In the app, click Open CSV and choose it from `/workspace`.
3. Save exports to `/workspace` as well. They will appear in the same host `shared` folder.

Files saved elsewhere inside the container may disappear when it is replaced. Pending draft text and revision history are held in memory, so save/export before stopping or updating. Each teammate has an independent desktop; browser tabs connected to the same container share that one desktop session.

The service binds only to `127.0.0.1:6080`. It is a local demonstration, not an authenticated public multi-user service. Do not change the binding to expose it on the public internet. Git shares the source and Docker build recipe, not each teammate's survey data or running session.

On Linux the image runs as UID 1000. If your shared folder is not writable by that user, adjust the shared folder's ownership for your setup or run Compose with a matching user override. Windows/macOS Docker Desktop normally handles bind-mount access.

## Feedback and revisions

1. Generate a report and open **Feedback & revisions** in Report studio.
2. Choose Executive Summary, Recommendations or Learner Feedback Summary.
3. Enter feedback. **Offline edits** supports shortening, bullet formatting and plain-language substitutions. These are deterministic edits, not generative AI.
4. Click **Preview revision** and compare the original and proposed section.
5. Click **Apply** to update the report. Review approval is cleared. **Undo revision** restores the previous draft after confirmation.

The original draft is unchanged until Apply. Editing the draft or feedback invalidates an earlier preview. Changing the dataset or generating a new report clears the revision history.

## Optional free-form AI revision

For instructions beyond the offline options, use **Azure AI** with an approved Azure OpenAI deployment. Copy `.env.example` to `.env` in the repository root and supply the endpoint, key and deployment. Compose passes these at runtime; they are not copied into the image. Recreate the container with `docker compose up -d --force-recreate` after changing settings.

For native Python launches, put the settings in `ai-learning-evaluation/.env` instead.

The UI requires explicit consent before sending the selected masked section, feedback and minimised metrics/theme metadata to Azure. It does not send source rows. Basic pattern masking is not complete anonymisation; inspect the section and feedback before approving external processing. Every returned revision remains a draft, and its accuracy requires human review. Revision exports disclose when Azure was used. Without credentials, the offline workflow still works.

## Stop, restart and troubleshoot

```sh
docker compose ps
docker compose logs --tail=100
docker compose restart
docker compose down
```

Closing the application window ends the container session; use `docker compose up -d` to start it again. `docker compose down` does not delete host files in `shared`.

Run tests inside a running container:

```sh
docker compose exec -T insight-hub python -m pytest -q -p no:cacheprovider
```

The GitHub Actions workflow builds the image, starts the desktop, checks its health and HTTP endpoint, and runs tests inside the Linux container. Check its actual result in the repository Actions tab; the existence of the workflow does not by itself mean the build has passed.

References: [noVNC](https://novnc.com/info.html), [Docker bind mounts](https://docs.docker.com/engine/storage/bind-mounts/).
