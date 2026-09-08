#!/bin/bash
# Batch half of the liveness fast-path test. Submit it with submit_batch.sh.
#
# Three things are recorded here, in this order:
#
# 1. what the fast path sees from the batch script itself, which is where a
#    caller that runs a process per unit of work runs them;
# 2. what it sees from inside an srun step, since a step carries a different
#    Slurm environment and may sit on a different node;
# 3. what both verdicts say while the allocation is being taken away. The
#    job is submitted with a short wall time on purpose. At the wall time
#    Slurm signals the job's processes and then kills them KillWait seconds
#    later, and the probe catches the signal rather than obeying it so that
#    the whole window is visible. If the local verdict still says "live"
#    while the controller has moved the job to COMPLETING, the fast path is
#    answering for an allocation that is already going away, and that is the
#    result that would sink it.
#
# Everything is written to the job's output file. Send that file back whole.

set -u

PROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PROBE_PYTHON:-python3}"
LABEL="${PROBE_LABEL:-$(hostname -s)}"
WATCH_SECONDS="${PROBE_WATCH_SECONDS:-420}"

probe() {
    "$PYTHON" "$PROBE_DIR/probe.py" --json "$@"
}

echo "==== batch liveness test: $LABEL ===="
echo "submitted from  ${SLURM_SUBMIT_HOST:-unknown}"
echo "job id          ${SLURM_JOB_ID:-unset}"
echo "python          $PYTHON ($("$PYTHON" --version 2>&1))"
echo "date            $(date --iso-8601=seconds)"
echo

echo "==== the shell's own view of the node names ===="
echo "hostname        $(hostname)"
echo "hostname -s     $(hostname -s)"
echo "hostname -f     $(hostname -f)"
echo "SLURMD_NODENAME ${SLURMD_NODENAME:-unset}"
echo "SLURM_JOB_NODELIST ${SLURM_JOB_NODELIST:-unset}"
echo "scontrol show hostnames:"
scontrol show hostnames "${SLURM_JOB_NODELIST:-}" | sed 's/^/    /'
echo

echo "==== 1. from the batch script ===="
probe --label "$LABEL-batch-script"

echo "==== 2. from inside a one-task srun step ===="
srun --nodes=1 --ntasks=1 "$PYTHON" "$PROBE_DIR/probe.py" --json \
    --label "$LABEL-srun-step"

echo "==== 3. from a task on every node ===="
srun --ntasks-per-node=1 bash -c \
    'echo "step task on $(hostname) SLURMD_NODENAME=${SLURMD_NODENAME:-unset}"'
echo

echo "==== 4. watching through the end of the allocation ===="
echo "the wall time is deliberately shorter than this watch, so the last"
echo "lines below are what the two verdicts said as the job was ending"
probe --label "$LABEL-expiry" --watch "$WATCH_SECONDS" --interval 2

echo "==== the watch ran to completion, so the allocation outlived it ===="
echo "that means the wall time was longer than PROBE_WATCH_SECONDS and the"
echo "expiry window was not observed; rerun with a shorter wall time"
