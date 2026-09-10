#!/bin/bash
cd "$(dirname "$0")" || exit 1
bash run_demo.sh
result=$?
if [ "$result" -ne 0 ]; then
  echo "Startup failed. Copy the error above and share it with the team."
  read -r -p "Press Return to close..."
fi
exit "$result"
