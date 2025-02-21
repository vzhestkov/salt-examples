#!/usr/bin/bash

if [ $# -lt 1 -o $# -gt 2 ]; then
    echo "Error: Wrong number of arguments!" >&2
    echo "Usage: $0 <PROXY-FQDN> [MASTER-FQDN]"
    echo "If 'MASTER-FQDN' is not specified 'PROXY-FQDN' will be used to connect to the same host."
    exit 1
fi

PROXY_FQDN="$1"
MASTER_FQDN="$2"

cat <<"EOL" > salto-secure.service
[Unit]
Description=The service makes wrapped Salt connections passing to the proxy via HTTPS
Before=venv-salt-minion.service

[Service]
Type=simple
User=daemon
EnvironmentFile=/etc/sysconfig/salto
ExecStart=socat TCP4-LISTEN:8888,bind=127.0.0.1,reuseaddr,fork OPENSSL:${PROXY_FQDN}:443
Restart=on-failure
RestartSec=3
SuccessExitStatus=143

[Install]
WantedBy=salto@.service
EOL

cat <<"EOL" > salto@.service
[Unit]
Description=The service makes wrapped Salt connections to port %I passing to the proxy with HTTP CONNECT
After=salto-secure.service
Requires=salto-secure.service

[Service]
Type=simple
User=daemon
EnvironmentFile=/etc/sysconfig/salto
ExecStart=bash -c '. /etc/sysconfig/salto; if [ -z "$MASTER_FQDN" ]; then MASTER_FQDN="$PROXY_FQDN"; fi; exec socat TCP4-LISTEN:%I,bind=127.0.0.1,reuseaddr,fork PROXY:127.0.0.1:$MASTER_FQDN:%I,proxyport=8888'
Restart=on-failure
RestartSec=3
SuccessExitStatus=143

[Install]
WantedBy=venv-salt-minion.service
EOL

cat <<"EOL" | sed "s/###PROXY_FQDN###/${PROXY_FQDN}/; s/###MASTER_FQDN###/${MASTER_FQDN}/" > salto-conf
#
# `PROXY_FQDN` should point to real FQDN of the MLM Proxy to connect to
# IMPORTANT!: This FQDN can't be assigned to localhost, but to the real FQDN of the Proxy
#
# MANDATORY!
#
PROXY_FQDN="###PROXY_FQDN###"

#
# `MASTER_FQDN` could point to the host running `salt-broker` (MLM Proxy)
# (MLM Proxy is preferred here) or `salt-master` (MLM Server)
# It's used inside the wrapped connection for CONNECT method,
# so it's resolving on the side of the host specified as `PROXY_FQDN`.
#
# In case if `MASTER_FQDN` is not specified the value from `PROXY_FQDN` is used,
# so that HTTP CONNECT will be called to connect to `salt-broker` or `salt-master`
# on the same host specified with `PROXY_FQDN`
#
# OPTIONAL
#
MASTER_FQDN="###MASTER_FQDN###"
EOL
