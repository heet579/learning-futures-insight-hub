#!/bin/bash
set -euo pipefail
pids=()
cleanup() {
  if [ "${#pids[@]}" -gt 0 ]; then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 0' TERM INT
Xvfb :99 -screen 0 1440x1000x24 -nolisten tcp &
pids+=($!)
ready=0
for attempt in {1..100}; do
  if xdpyinfo -display :99 >/dev/null 2>&1; then ready=1; break; fi
  sleep 0.1
done
if [ "$ready" -ne 1 ]; then echo 'Virtual display failed to start.' >&2; exit 1; fi
openbox --sm-disable &
pids+=($!)
x11vnc -display :99 -localhost -rfbport 5900 -forever -shared -nopw -noxdamage &
pids+=($!)
/usr/bin/websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
pids+=($!)
python app.py &
app_pid=$!
pids+=($app_pid)
printf '%s\n' "$app_pid" >/tmp/insight-hub.pid
echo 'Open http://localhost:6080/vnc.html?autoconnect=true&resize=scale'
echo 'Put CSVs in the host shared folder; open/export them under /workspace in the app.'
# A failed desktop process must not leave a healthy-looking browser server behind.
set +e
wait -n "${pids[@]}"
result=$?
exit "$result"
