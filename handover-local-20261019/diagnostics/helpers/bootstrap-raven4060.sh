#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
exec > >(tee -a /mnt/d/RAVEN-4060/logs/bootstrap.log) 2>&1
date -Is
if ! id raven >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash raven
fi
cat > /etc/wsl.conf <<'EOF'
[boot]
systemd=true

[user]
default=raven

[automount]
enabled=true
options="metadata,umask=22,fmask=11"

[interop]
enabled=true
appendWindowsPath=false
EOF
apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 update
apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 install -y --no-install-recommends ca-certificates curl git python3-venv python3-pip vulkan-tools
install -d -o raven -g raven /home/raven/work /home/raven/.venvs
runuser -u raven -- python3 -m venv /home/raven/.venvs/raven-scene1
/usr/lib/wsl/lib/nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
vulkaninfo --summary > /mnt/d/RAVEN-4060/logs/vulkan-summary.log 2>&1 || true
cat /mnt/d/RAVEN-4060/logs/vulkan-summary.log
date -Is
echo RAVEN_BOOTSTRAP_FINISHED
