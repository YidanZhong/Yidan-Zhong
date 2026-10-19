#!/usr/bin/env bash
set -euo pipefail
exec > >(tee -a /mnt/d/RAVEN-4060/logs/project-prepare.log) 2>&1
date -Is
cd /home/raven/work
test ! -e RAVEN-AirGround
echo '118b3a85da1b670d097fb8e045326f53a312f0b1e05b879680979c521ebe46a1  /mnt/d/RAVEN-4060/setup/raven-source-scene1.tar.gz' | sha256sum --check
mkdir RAVEN-AirGround
tar -xzf /mnt/d/RAVEN-4060/setup/raven-source-scene1.tar.gz -C RAVEN-AirGround
cd RAVEN-AirGround
/home/raven/.venvs/raven-scene1/bin/python -m pip install --timeout 30 --retries 2 -e '.[test]'
/home/raven/.venvs/raven-scene1/bin/python -m pip check
/home/raven/.venvs/raven-scene1/bin/airground doctor
/home/raven/.venvs/raven-scene1/bin/airground assets check --simulator-version 4.5.0 --cache assets/cache
/home/raven/.venvs/raven-scene1/bin/python AirStack/simulation/isaac-sim/utils/scene_audit.py AirStack/scenes/RetroNeighborhood/RetroNeighborhood_Export.usd
sha256sum AirStack/scenes/RetroNeighborhood/RetroNeighborhood_Export.usd
date -Is
echo RAVEN_PROJECT_PREPARE_FINISHED
