# What the machines said

Evidence for the local liveness fast path on `avoid-per-process-liveness-query`. Every number here comes from a file in this directory; nothing is inferred.

## Chrysalis

Slurm 20.02.4. `KillWait = 90 sec`, `MinJobAge = 300 sec`, `LaunchParameters = (null)`, `SallocDefaultCommand = (null)`. See `chrysalis-site.txt`.

### Hostname forms differ by node type

| where | `socket.gethostname()` | short | what Slurm calls it |
| --- | --- | --- | --- |
| login node | `chrlogin1.lcrc.anl.gov` | `chrlogin1` | not in any node list |
| compute node | `chr-0500` | `chr-0500` | `SLURMD_NODENAME=chr-0500` |

The login node answers to an FQDN and the compute node to a bare short name. Comparing short names is what makes the two sides comparable; on this machine a raw comparison would have worked on the compute node by luck.

### In a batch job: the fast path answers, and nothing is asked

`chrysalis-batch-1283154.out`. On `chr-0506`, with `SLURM_JOB_NODELIST=chr-[0506-0507]` expanding to both names:

* the fast path said `True` from `SLURMD_NODENAME` alone, without expanding anything
* the controller said `RUNNING`, so the two agree
* `get_parallel_system()` issued **no liveness query**. The one `squeue` it still runs is `-o %D` for the node count, which is what #477 removes.

The same held from inside an `srun` step.

### A process can outlive its own SIGTERM while the job is COMPLETING

This is the case the design rests on not happening, and it does happen. In `chrysalis-batch-1283154.out` the batch script ignores `SIGTERM` on purpose. At the wall time:

* `06:56:16.7` -- slurmstepd reports the job cancelled for time limit, `SIGTERM` arrives
* `06:56:17.7` through `06:57:46.1` -- **45 consecutive samples, every one `fast_path=True state=COMPLETING`**, spanning 88.4 s
* `06:57:46` -- `SIGKILL`; `sacct` shows the batch step `CANCELLED` with `ExitCode 0:9`

The window is bounded by `KillWait`, and it closed at 89.4 s against a configured 90 s. `COMPLETING` is deliberately excluded from `LIVE_JOB_STATES`, so in that window the fast path says "live" for a job whose nodes are on their way back.

**What opens the window is surviving `SIGTERM`.** The first run of the same job, `chrysalis-batch-1283137-shell-dies-on-sigterm.out`, did not trap it: bash died, slurmstepd took the step down with it, and the watch stopped one second after the wall time having never seen `COMPLETING`. `sacct` shows that step `CANCELLED` with `ExitCode 0:15`.

### From an salloc shell: unchanged

`chrysalis-salloc.txt`, job 1283181. `salloc` runs the command on the login node here -- `hostname` is `chrlogin1.lcrc.anl.gov`, `SLURMD_NODENAME` is unset, and `SLURM_JOB_NODELIST` is `chr-0493`, a compute node the process is not on.

The process outlived its allocation, which is the failure #476 exists for, and the fast path declined to answer for the whole of it:

| elapsed | controller | fast path |
| --- | --- | --- |
| 0 s to 130.7 s | `RUNNING` | `False` |
| 140.7 s to 190.8 s | `COMPLETING` | `False` |
| 200.8 s onward | `TIMEOUT` | `False` |

`salloc` printed "has exceeded its time limit and its allocation has been revoked" and did not kill the command, exactly as #476 describes. Every one of the 22 samples said `fast_path=False`, so the controller is asked and the warning and demotion to the login system happen as they did before this branch.

### The #475 workflow is unaffected

Issue #475 is `polaris suite ...` run from a login-node shell carrying a stale `SLURM_JOB_ID`. The fast path can only fire for a process on one of the allocation's own compute nodes, and that shell is not on one. The salloc run above is that case measured directly: every sample said `fast_path=False`, so the controller is asked and #476's fix runs exactly as before.

The `COMPLETING` window is a different situation, and one #475 does not reach: it needs a process on a compute node that outlives its own `SIGTERM`.

## Perlmutter (pm-cpu)

Slurm 25.11.8. `KillWait = 30 sec`, `MinJobAge = 300 sec`, and `LaunchParameters` includes **`use_interactive_step`**, which is what puts an `salloc` shell on a compute node. See `pm-cpu-site.txt`.

### The salloc question, which is what Perlmutter was on the list for

`pm-cpu-salloc.txt`, job 58069209. The shell landed on `nid007043`, which is the allocation's only node, `SLURMD_NODENAME=nid007043`, and the fast path returned `True` -- so unlike Chrysalis, the fast path does fire for an `salloc` shell here.

It does not matter, because the shell does not outlive its allocation. The job went `COMPLETING` at 141.9 s and the process was killed at 168.0 s, 26.1 s later, against a configured `KillWait` of 30. The terminal, which the tee'd file does not capture, ended:

```
WATCH nid007043-salloc ... elapsed=  168.0 host=nid007043 fast_path=True state=COMPLETING
srun: error: nid007043: task 0: Killed
srun: Terminating StepId=58069209.interactive
(mache-dev) xylar@perlmutter:login36:~/e3sm_work/mache/avoid-per-process-liveness-query>
```

This is the first of the three outcomes the handoff set out: the shell dies with the allocation, so the fast path never sees the stale case. It is a little stronger than that. The shell carrying `SLURM_JOB_ID` was the interactive step on `nid007043` and went with the node; what the user is returned to is the original login shell, which never had the variable. So this workflow leaves no stale job id behind on Perlmutter at all -- there is no surviving process holding one. A job id exported by hand, or inherited into a detached process, is still possible and still falls through to the controller query.

`task 0: Killed` is also what explains a difference between the two machines. Chrysalis delivered a catchable `SIGTERM`, which the batch script had to ignore to stay alive long enough to measure anything. Neither Perlmutter run recorded a signal, because the step is killed outright. The window and its `KillWait` bound are the same; the way it is reached is not.

### In a batch job: the same as Chrysalis

`pm-cpu-batch-58069208.out`. On `nid005097` with `SLURM_JOB_NODELIST=nid[005097-005098]`: fast path `True` from `SLURMD_NODENAME`, controller `RUNNING`, no liveness query. The only `squeue` is the `-o %D` node count that #477 removes.

### The COMPLETING window tracks KillWait, and is not machine-specific

Measured at both sites and across two Slurm eras:

| machine | Slurm | `KillWait` | measured window |
| --- | --- | --- | --- |
| Chrysalis | 20.02.4 | 90 s | 88.4 s (batch) |
| Perlmutter | 25.11.8 | 30 s | 27.1 s (batch), 26.1 s (salloc) |

So it is a property of Slurm rather than of a site's policy, and its width is the site's `KillWait`.

One difference in how it is reached: the Chrysalis batch script recorded a catchable `SIGTERM` and had to ignore it to stay alive. Neither Perlmutter run recorded a signal, and the terminal shows why -- `task 0: Killed`, a bare `SIGKILL`. The observable behavior is the same; the signalling path is not.

### A near miss on hostname spelling

`nid005097` answers to three different names, and only one of them is usable:

| source | value |
| --- | --- |
| `socket.gethostname()` | `nid005097` |
| `socket.getfqdn()` | `nid005097-hsn0` |
| `hostname -f` | `x1105c0s0b0n1h0.chn.perlmutter.nersc.gov` |

Slurm calls the node `nid005097`. Splitting on `.` recovers that from `gethostname()` and from Chrysalis's `chrlogin1.lcrc.anl.gov`, but not from `nid005097-hsn0`, whose distinguishing suffix is joined with a hyphen. The code reads `socket.gethostname()`, which is correct, but the choice is load-bearing rather than incidental and there is now a comment saying so.
