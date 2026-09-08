#!/bin/bash
# Submit batch_job.sh with the flags the current machine needs.
#
# Usage:
#     ACCOUNT=<account> ./liveness_probe/submit_batch.sh
#
# The wall time is two minutes on purpose: the job is meant to hit it while
# the probe is still watching. Nothing here runs work on a login node.

set -eu

PROBE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="$(hostname -s)"

case "$HOST" in
    chrlogin*|chr-*)
        MACHINE=chrysalis
        SBATCH_ARGS=(--partition=debug)
        ;;
    login*|nid*|perlmutter*)
        MACHINE=pm-cpu
        SBATCH_ARGS=(--constraint=cpu --qos=debug)
        : "${ACCOUNT:=e3sm}"
        ;;
    *)
        echo "Unrecognized machine '$HOST'. Pass the sbatch flags yourself:"
        echo "    sbatch -N 2 -t 2 <flags> $PROBE_DIR/batch_job.sh"
        exit 1
        ;;
esac

if [ -n "${ACCOUNT:-}" ]; then
    SBATCH_ARGS+=(--account="$ACCOUNT")
fi

set -x
sbatch \
    --job-name=mache-liveness \
    --nodes=2 \
    --time=2 \
    --output="$PROBE_DIR/results/${MACHINE}-batch-%j.out" \
    "${SBATCH_ARGS[@]}" \
    --export=ALL,PROBE_DIR="$PROBE_DIR",PROBE_LABEL="$MACHINE",PROBE_PYTHON="${PROBE_PYTHON:-python3}" \
    "$PROBE_DIR/batch_job.sh"
