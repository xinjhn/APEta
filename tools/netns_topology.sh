#!/usr/bin/env bash
# tools/netns_topology.sh
# =========================
# Fixes the netem-on-loopback validity threat documented in tools/netem.sh:
# applying tc/netem to `lo` delays BOTH the client<->edge hop AND the
# edge<->backend hop, so a cache MISS through Varnish pays the network delay
# TWICE (measured ~2x direct latency on MISS vs ~1x on HIT under
# `constrained`). That doesn't match a real CDN/edge-cache topology, where
# the edge sits close to the client and only the edge<->origin leg crosses
# the slow network (or, in our case, the edge and origin are co-located and
# that leg has effectively no delay at all).
#
# Topology:
#   root netns (k6 client)                 ape-origin netns
#   --------------------------             -------------------------------
#   veth-host  10.200.0.1/24  <==veth==>   veth-ns  10.200.0.2/24
#   (netem delay applied HERE,             uvicorn binds 10.200.0.2:8000
#    on veth-host only)                    varnish  binds 10.200.0.2:8080,
#                                             proxies to 127.0.0.1:8000
#                                             (ape-origin's OWN loopback --
#                                              never touches the veth, so
#                                              this hop is never delayed)
#
# Client always crosses the veth exactly ONCE, whether it hits the backend
# directly (caching=off, port 8000) or through Varnish (caching=on, port
# 8080 -> internal 127.0.0.1:8000, undelayed). No more double-counting.
#
# Usage:
#   sudo tools/netns_topology.sh up
#   sudo tools/netns_topology.sh apply-netem constrained   # or lan / clear
#   sudo tools/netns_topology.sh down
#
# Parallel runs: every name/IP below is overridable via env var (defaults
# match the original single-namespace values for backward compatibility).
# A second concurrent orchestrator session must override ALL of these to a
# disjoint namespace/veth-name/IP-subnet, e.g.:
#   sudo NETNS=ape-origin-2 VETH_HOST=veth-ape-h2 VETH_NS=veth-ape-n2 \
#        IP_HOST=10.201.0.1 IP_NS=10.201.0.2 tools/netns_topology.sh up
# Two sessions sharing ANY of these (most importantly NETNS or VETH_HOST)
# collide: `up()` tears down any existing namespace of the SAME NAME before
# creating it, so an unparameterized second `up` would destroy the first
# session's live namespace mid-run. Linux veth names are capped at 15 chars
# (IFNAMSIZ) -- keep suffixes short.
set -euo pipefail

NETNS="${NETNS:-ape-origin}"
VETH_HOST="${VETH_HOST:-veth-ape-h}"
VETH_NS="${VETH_NS:-veth-ape-n}"
IP_HOST="${IP_HOST:-10.200.0.1}"
IP_NS="${IP_NS:-10.200.0.2}"
PREFIX="${PREFIX:-24}"

up() {
    if ip netns list | grep -q "^${NETNS}\b"; then
        echo "[info] netns ${NETNS} already exists -- tearing down first for a clean state"
        down || true
    fi
    ip netns add "$NETNS"
    ip link add "$VETH_HOST" type veth peer name "$VETH_NS"
    ip link set "$VETH_NS" netns "$NETNS"
    ip addr add "${IP_HOST}/${PREFIX}" dev "$VETH_HOST"
    ip link set "$VETH_HOST" up
    ip netns exec "$NETNS" ip addr add "${IP_NS}/${PREFIX}" dev "$VETH_NS"
    ip netns exec "$NETNS" ip link set "$VETH_NS" up
    ip netns exec "$NETNS" ip link set lo up
    echo "[done] topology up: root(${IP_HOST}) <-> ${NETNS}(${IP_NS})"
}

down() {
    # Kill anything still running inside the namespace FIRST -- `ip netns
    # del` only removes the named handle, processes that were spawned via
    # `ip netns exec` keep running (detached, holding their own reference to
    # the network namespace) unless killed explicitly. Caught manually
    # during topology verification: varnishd/uvicorn survived a `down`.
    if ip netns list 2>/dev/null | grep -q "^${NETNS}\b"; then
        for pid in $(ip netns pids "$NETNS" 2>/dev/null || true); do
            kill -9 "$pid" 2>/dev/null || true
        done
    fi
    ip link del "$VETH_HOST" 2>/dev/null || true
    ip netns del "$NETNS" 2>/dev/null || true
    echo "[done] topology removed"
}

apply_netem() {
    local profile="$1"
    ip netns exec "$NETNS" true 2>/dev/null || { echo "[error] netns ${NETNS} not up -- run 'up' first" >&2; exit 1; }
    tc qdisc del dev "$VETH_HOST" root 2>/dev/null || true
    case "$profile" in
        lan)
            tc qdisc add dev "$VETH_HOST" root netem delay 5ms 1ms distribution normal rate 100mbit
            ;;
        constrained)
            # Same numbers as tools/netem.sh's constrained profile (25ms/dir
            # -> RTT~50ms, 10mbit) -- now applied to the SINGLE client<->edge
            # hop instead of the whole loopback.
            tc qdisc add dev "$VETH_HOST" root netem delay 25ms 5ms distribution normal rate 10mbit
            ;;
        clear)
            echo "[done] netem cleared on ${VETH_HOST}"
            return
            ;;
        *)
            echo "[error] unknown profile: ${profile} (lan|constrained|clear)" >&2
            exit 1
            ;;
    esac
    echo "[done] applied '${profile}' on ${VETH_HOST}:"
    tc qdisc show dev "$VETH_HOST"
}

show() {
    echo "--- netns ---"
    ip netns list | grep "$NETNS" || echo "(not up)"
    echo "--- veth-host qdisc ---"
    tc qdisc show dev "$VETH_HOST" 2>/dev/null || echo "(veth not up)"
}

case "${1:-}" in
    up) up ;;
    down) down ;;
    apply-netem) apply_netem "${2:-}" ;;
    show) show ;;
    *)
        echo "Usage: $0 {up|down|apply-netem <lan|constrained|clear>|show}" >&2
        exit 1
        ;;
esac
