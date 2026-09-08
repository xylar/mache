# Liveness fast-path testing tools

Branch-local tools for `avoid-per-process-liveness-query`. **They are committed only so that they can be fetched on another machine, and are removed before the pull request.**

## What is being tested

`get_parallel_system()` used to ask the Slurm controller whether the job was still live every time it was called. This branch skips that query when the process is running on one of the allocation's own nodes, on the argument that a process cannot still be running on a node of a finished allocation, because Slurm kills a job's processes before it releases its nodes.

That argument is reasoning, not measurement, and these tools are what measures it. Three things have to hold:

1. Slurm really does kill a job's processes before the nodes go back. `LIVE_JOB_STATES` deliberately excludes `COMPLETING`, so if a batch script can still be running while its job is `COMPLETING`, the fast path answers "live" for a job whose nodes are being taken away.
2. A shell that outlives its allocation is not sitting on one of that allocation's nodes. Chrysalis leaves an `salloc` shell on a login node; NERSC hands out a compute node. **If a shell can outlive its allocation while still on an allocated node, the fast path is unsound.** This is the question that decides the design.
3. The hostname the code reads is spelled the way Slurm spells the same node, or the difference is only the domain.

## What to run, on each machine

Everything needs is a Python 3.10 or newer on `PATH`; `probe.py` loads `mache.parallel` straight from this worktree and does not need the package's dependencies installed. Set `PROBE_PYTHON` if `python3` is older than 3.10.

### 1. Site facts, from a login node

```bash
./liveness_probe/site_facts.sh 2>&1 | tee liveness_probe/results/<machine>-site.txt
```

Ordinary client commands only. `KillWait` is the width of the window test 2 measures, and `LaunchParameters` says whether `salloc` puts the shell on a compute node.

### 2. The batch job

```bash
ACCOUNT=<your account> ./liveness_probe/submit_batch.sh
```

Two nodes for two minutes, so that the node list is a real hostlist expression and the job hits its wall time while the probe is still watching. Output lands in `liveness_probe/results/<machine>-batch-<jobid>.out`. Send that file back whole.

The last section is the one to look at: it prints the local verdict and the controller's state every two seconds through the end of the allocation. What matters is whether any line says `fast_path=True` alongside a state that is not `RUNNING`.

### 3. The `salloc` shell

```bash
salloc --nodes=1 --time=2 <the machine's account/partition flags>
# then, inside the shell it gives you:
./liveness_probe/salloc_watch.sh 2>&1 | tee liveness_probe/results/<machine>-salloc.txt
```

Let the two minutes run out rather than cancelling. Then follow whatever the script prints. Capture the whole terminal session including the `salloc` command itself, because where the shell lands is half the measurement.

On Chrysalis this is expected to end with the shell alive on `chrlogin*`, which is not in the node list, so the fast path misses and the controller is asked exactly as it is today. Perlmutter is the machine that could say otherwise.

## Sending results back

Commit whatever lands in `liveness_probe/results/` and push the branch. The trailing-whitespace hook will edit captured output, so commit those with `--no-verify`.
