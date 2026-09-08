#!/bin/bash
# The salloc half of the liveness fast-path test. Run this INSIDE an
# interactive salloc shell, not from a login shell and not as salloc's
# command.
#
# This is the measurement the whole idea turns on. A salloc shell that
# outlives its allocation is what the scheduler query in #476 was added
# for. The local fast path can only make that case worse if the shell is
# still sitting on one of the allocation's own nodes when the allocation
# ends, because then the fast path would answer "live" for a job that is
# over. Where salloc puts the shell is site policy: Chrysalis leaves it on
# a login node, NERSC hands out a compute node.
#
# Three outcomes, and they lead to different designs:
#
#   * the shell dies with the allocation           -> the fast path is fine
#   * the shell survives, off the allocated nodes  -> the fast path is fine
#   * the shell survives, on an allocated node     -> the fast path is wrong
#
# How to run it, on each machine:
#
#   1. salloc --nodes=1 --time=2 <the machine's account/partition flags>
#   2. inside the shell you get:  ./liveness_probe/salloc_watch.sh
#   3. let the two minutes run out. Do not cancel the job yourself; the
#      point is what happens when the allocation ends on its own.
#   4. if you still have a prompt afterwards, run the last command this
#      script prints, and send back everything from step 1 onward.

set -u

PROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PROBE_PYTHON:-python3}"
LABEL="${PROBE_LABEL:-$(hostname -s)}"
WATCH_SECONDS="${PROBE_WATCH_SECONDS:-420}"
INTERVAL="${PROBE_INTERVAL:-2}"

echo "==== salloc liveness test: $LABEL ===="
echo "shell pid       $$"
echo "hostname        $(hostname)"
echo "hostname -s     $(hostname -s)"
echo "job id          ${SLURM_JOB_ID:-unset}"
echo "SLURMD_NODENAME ${SLURMD_NODENAME:-unset}"
echo "SLURM_JOB_NODELIST ${SLURM_JOB_NODELIST:-unset}"
echo "date            $(date --iso-8601=seconds)"
echo
echo "the two questions this answers: is this shell on one of the"
echo "allocation's nodes, and is it still there after the allocation ends"
echo

"$PYTHON" "$PROBE_DIR/probe.py" --json \
    --label "$LABEL-salloc" --watch "$WATCH_SECONDS" --interval "$INTERVAL"

echo
echo "==== the watch finished without being killed ===="
echo "if the allocation has already ended, this shell outlived it. Run"
echo "this now and send back what it says:"
echo
echo "    $PYTHON $PROBE_DIR/probe.py --label $LABEL-salloc-after --json"
