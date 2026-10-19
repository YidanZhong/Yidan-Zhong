#!/usr/bin/env bash
set -euo pipefail
exec > >(tee -a /mnt/d/RAVEN-4060/logs/project-offline-prepare.log) 2>&1
if test -f /proc/596/cmdline; then
  current=$(tr '\0' ' ' < /proc/596/cmdline)
  if [[ "$current" == '/home/raven/.venvs/raven-scene1/bin/python -m pip install '* ]]; then
    kill -TERM 596
    for attempt in 1 2 3 4 5; do
      test ! -e /proc/596 && break
      sleep 1
    done
    test ! -e /proc/596
  fi
fi
cd /home/raven/work/RAVEN-AirGround
export PIP_NO_INDEX=1
export PIP_FIND_LINKS=/mnt/d/RAVEN-4060/setup/raven4060-wheels
/home/raven/.venvs/raven-scene1/bin/python -m pip install -e '.[test]'
/home/raven/.venvs/raven-scene1/bin/python -m pip check
/home/raven/.venvs/raven-scene1/bin/airground doctor
/home/raven/.venvs/raven-scene1/bin/airground assets check --simulator-version 4.5.0 --cache assets/cache
/home/raven/.venvs/raven-scene1/bin/python AirStack/simulation/isaac-sim/utils/scene_audit.py AirStack/scenes/RetroNeighborhood/RetroNeighborhood_Export.usd
sha256sum AirStack/scenes/RetroNeighborhood/RetroNeighborhood_Export.usd
date -Is
echo RAVEN_PROJECT_PREPARE_FINISHED
