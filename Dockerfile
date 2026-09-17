FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DISPLAY=:99 HOME=/home/app DEMO_SHARED_DIR=/workspace
RUN apt-get update && apt-get install -y --no-install-recommends \
    tk8.6 libtk8.6 xvfb x11vnc novnc websockify openbox x11-utils tini fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 app
RUN python -c "import tkinter; print(tkinter.TkVersion)"
WORKDIR /app/ai-learning-evaluation
COPY ai-learning-evaluation/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app ai-learning-evaluation/app.py ./app.py
COPY --chown=app:app ai-learning-evaluation/src ./src
COPY --chown=app:app ai-learning-evaluation/data ./data
COPY --chown=app:app ai-learning-evaluation/prompts ./prompts
COPY --chown=app:app ai-learning-evaluation/tests ./tests
COPY --chown=app:app docker /app/docker
RUN mkdir -p /workspace && chown app:app /workspace \
    && sed -i 's/\r$//' /app/docker/start.sh
USER app
EXPOSE 6080
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=3 CMD python /app/docker/healthcheck.py
ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/app/docker/start.sh"]
