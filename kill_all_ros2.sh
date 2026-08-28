#!/usr/bin/env bash

set +e

SELF=$$
PARENT_PIDS=()
p=$PPID
while [ -n "$p" ] && [ "$p" != "1" ] && [ "$p" != "0" ]; do
    PARENT_PIDS+=("$p")
    p=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
done
SAFE_PIDS=("$SELF" "${PARENT_PIDS[@]}")

is_safe() {
    local pid="$1" s
    for s in "${SAFE_PIDS[@]}"; do
        [ "$pid" = "$s" ] && return 0
    done
    return 1
}

sig_pids() {
    local sig="$1" pids="$2" pid
    [ -z "$pids" ] && return
    for pid in $pids; do
        is_safe "$pid" && continue
        kill "$sig" "$pid" 2>/dev/null
    done
}

collect_node_pids() {
    local nodes node name pids
    nodes=$(ros2 node list 2>/dev/null)
    for node in $nodes; do
        name=${node##*/}
        case "$name" in
            transform_listener_impl_*) continue ;;
        esac
        pids=$(pgrep -f -- "__node:=${name}\\b" 2>/dev/null)
        [ -z "$pids" ] && pids=$(pgrep -f -- "/opt/ros/.*${name}\\b" 2>/dev/null)
        [ -n "$pids" ] && echo "$pids"
    done
}

echo "=== Killing all ROS2 nodes/processes ==="

NODE_PIDS=$(collect_node_pids | sort -u | tr '\n' ' ')
if [ -n "${NODE_PIDS// /}" ]; then
    echo "Node PIDs: $NODE_PIDS"
    echo "SIGINT (graceful)..."
    sig_pids -INT "$NODE_PIDS"
    sleep 2
    sig_pids -KILL "$NODE_PIDS"
fi

echo "Broad cleanup (tools, /opt/ros/, gazebo)..."
for PAT in 'rviz2' 'rqt' 'rosbag2' 'gzserver' 'gzclient' 'ign gazebo' 'gz sim'; do
    sig_pids -KILL "$(pgrep -f -- "$PAT" 2>/dev/null)"
done
sig_pids -KILL "$(pgrep -f -- '/opt/ros/' 2>/dev/null)"

rm -f /dev/shm/fastrtps_* /dev/shm/sem.fastrtps_* 2>/dev/null
ros2 daemon stop 2>/dev/null
sig_pids -KILL "$(pgrep -f -- '(_ros2_daemon|ros2-daemon)' 2>/dev/null)"

sleep 1

echo
echo "=== Verification ==="
ros2 daemon stop 2>/dev/null
sleep 1
REMAINING=$(ros2 node list 2>/dev/null)
if [ -z "$REMAINING" ]; then
    echo "All ROS2 nodes killed"
    exit 0
fi

echo "Remaining nodes, retrying..."
echo "$REMAINING"
sig_pids -KILL "$(collect_node_pids | sort -u | tr '\n' ' ')"
sig_pids -KILL "$(pgrep -f -- '/opt/ros/' 2>/dev/null)"
rm -f /dev/shm/fastrtps_* /dev/shm/sem.fastrtps_* 2>/dev/null
ros2 daemon stop 2>/dev/null
sleep 1

FINAL=$(ros2 node list 2>/dev/null)
if [ -z "$FINAL" ]; then
    echo "All ROS2 nodes killed (after retry)"
    exit 0
else
    echo "Still remaining (manual intervention needed):"
    echo "$FINAL"
    exit 1
fi
