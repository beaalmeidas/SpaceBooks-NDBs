#!/bin/bash
set -eu
keyfile=/data/configdb/spacebooks-keyfile
if [ ! -s "$keyfile" ]; then
    umask 077
    openssl rand -base64 756 > "$keyfile"
fi
chown mongodb:mongodb "$keyfile"
chmod 400 "$keyfile"
exec /usr/local/bin/docker-entrypoint.sh mongod --bind_ip_all --replSet rs0 --keyFile "$keyfile"
