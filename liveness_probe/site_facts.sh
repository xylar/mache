#!/bin/bash
# Record the site settings that bear on when a job's processes are killed.
#
# These are controller queries, so this is run once per machine and not per
# probe. KillWait is the window between Slurm asking a job's processes to
# stop and killing them, which is the window the batch watch measures.
# LaunchParameters says whether salloc puts the user's shell on a compute
# node, which is the question Perlmutter is on the test list for.

set -u

echo "==== site facts: $(hostname) $(date --iso-8601=seconds) ===="
echo "-- srun --version --"
srun --version
echo
echo "-- scontrol show config, the settings that matter here --"
scontrol show config | grep -E \
    '^(KillWait|MinJobAge|UnkillableStepTimeout|EpilogSlurmctld|Epilog|Prolog|LaunchParameters|SallocDefaultCommand|InteractiveStepOptions|ClusterName|SlurmctldHost|SchedulerParameters)\b'
echo
echo "-- login hostname forms --"
echo "hostname       $(hostname)"
echo "hostname -s    $(hostname -s)"
echo "hostname -f    $(hostname -f)"
