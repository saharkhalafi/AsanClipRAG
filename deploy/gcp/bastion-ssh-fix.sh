#!/bin/bash
# Repair IAP SSH on Debian 13 bastion: ensure sshd listens on TCP/22 and metadata user exists.
set -euo pipefail
LOG=/var/log/asanclip-bastion-ssh-fix.log
exec >>"$LOG" 2>&1
echo "=== $(date -Is) bastion SSH repair start ==="

# Disable socket activation that can leave sshd off TCP/22 when AF_VSOCK generator fails.
systemctl stop ssh.socket sshd-unix-local.socket 2>/dev/null || true
systemctl disable ssh.socket sshd-unix-local.socket 2>/dev/null || true
systemctl mask ssh.socket sshd-unix-local.socket 2>/dev/null || true

# Ensure classic sshd service on port 22.
mkdir -p /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/99-asanclip-iap.conf <<'EOF'
Port 22
ListenAddress 0.0.0.0
ListenAddress ::
PubkeyAuthentication yes
PasswordAuthentication no
PermitRootLogin no
UsePAM yes
EOF

systemctl enable ssh.service
systemctl restart ssh.service

# Refresh guest agent so project metadata SSH keys create the Sahar account.
systemctl restart google-guest-agent-manager.service 2>/dev/null || true
systemctl restart google-guest-agent.service 2>/dev/null || true
sleep 5

echo "--- ssh service ---"
systemctl is-active ssh.service || true
ss -tlnp | grep ':22' || true

echo "--- user Sahar ---"
getent passwd Sahar || true
if [ -d /home/Sahar/.ssh ]; then
  ls -la /home/Sahar/.ssh/authorized_keys || true
fi

echo "=== $(date -Is) bastion SSH repair done ==="
