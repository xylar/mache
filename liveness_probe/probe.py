#!/usr/bin/env python
"""
Record what the local liveness fast path sees, and whether it is right.

This is a branch-local diagnostic for ``avoid-per-process-liveness-query``.
It is committed only so that it can be fetched on another machine, and is
not part of the pull request.

It prints one human-readable block and, with ``--json``, one JSON object on
the last line, so that a run can be both read and diffed.

What it records, in the exact strings the code compares:

* every hostname form this host answers to
* the Slurm environment the fast path reads
* what ``scontrol show hostnames`` expands the node list to
* the fast path's verdict, ``running_on_allocated_node()``
* the controller's verdict, ``get_slurm_job_state()``, which is the ground
  truth the fast path is being checked against
* whether ``get_parallel_system()`` issued a batch-system query at all
"""

import argparse
import datetime
import json
import os
import pathlib
import platform
import signal
import socket
import subprocess
import sys
import time
import types
import warnings
from configparser import ConfigParser


def _import_mache_parallel() -> None:
    """
    Make ``mache.parallel`` importable with nothing but a Python 3.10+.

    The normal import is tried first and is what a developer environment
    will take. It fails on a bare machine Python because ``mache/__init__``
    imports ``lxml``, which the parallel code itself does not use: every
    module under ``mache/parallel`` is standard library only. So the
    fallback registers a ``mache`` package whose ``__path__`` is the source
    tree and whose ``__init__`` is never run, which leaves the modules
    under test exactly as they are on disk and only skips the unrelated
    imports above them. That is what lets this probe run on a compute node
    under whatever Python is on PATH.
    """
    root = pathlib.Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        import mache.parallel  # noqa: F401

        return
    except ImportError as exception:
        print(
            f'note: importing mache normally failed ({exception}); loading '
            f'mache.parallel from {root} without running mache/__init__.py',
            file=sys.stderr,
        )
    package = types.ModuleType('mache')
    package.__path__ = [str(root / 'mache')]
    sys.modules['mache'] = package


_import_mache_parallel()

from mache.parallel import get_parallel_system  # noqa: E402
from mache.parallel.slurm import (  # noqa: E402
    LIVE_JOB_STATES,
    _expand_job_nodelist,
    _short_hostname,
    get_slurm_job_state,
    get_slurm_version,
    running_on_allocated_node,
)

# Every Slurm variable that bears on where this process is running. Recorded
# verbatim so that a machine whose salloc behaves differently can be told
# apart from one whose variables are merely spelled differently.
SLURM_ENV_VARS = (
    'SLURM_JOB_ID',
    'SLURM_JOBID',
    'SLURM_JOB_NODELIST',
    'SLURM_NODELIST',
    'SLURMD_NODENAME',
    'SLURM_JOB_NUM_NODES',
    'SLURM_NNODES',
    'SLURM_JOB_PARTITION',
    'SLURM_JOB_QOS',
    'SLURM_STEP_ID',
    'SLURM_STEPID',
    'SLURM_PTY_PORT',
    'SLURM_SUBMIT_HOST',
    'SLURM_CLUSTER_NAME',
)


class _RecordingRun:
    """
    Stand-in for ``subprocess.run`` that records every squeue invocation.

    It still runs the command, because a run that suppressed the query
    would not be measuring what the real code path does. The point is the
    count, not the refusal.
    """

    def __init__(self, real):
        self.real = real
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):
        self.calls.append([str(arg) for arg in args])
        return self.real(args, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--label',
        default='',
        help='a name for this observation, echoed back in the output',
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='also print one JSON object on the last line',
    )
    parser.add_argument(
        '--watch',
        type=float,
        default=0.0,
        help=(
            'after the full report, keep printing a one-line verdict for '
            'this many seconds. The point of watching is to see what the '
            'two verdicts say while the allocation is being taken away, so '
            'run for longer than the wall time to catch it.'
        ),
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=2.0,
        help='seconds between the lines --watch prints',
    )
    args = parser.parse_args()

    record = _collect(args.label)
    _report(record)
    if args.json:
        print('JSON ' + json.dumps(record, sort_keys=True))
    if args.watch > 0:
        _watch(args.label, args.watch, args.interval)
    return 0


def _watch(label: str, duration: float, interval: float) -> None:
    """
    Print the two verdicts repeatedly, through whatever ends the job.

    SIGTERM is caught and noted rather than obeyed, because the window this
    is measuring is exactly the one between Slurm asking a job's processes
    to stop and killing them: if the local fast path says "live" during
    that window while the controller has moved the job to COMPLETING, the
    fast path is answering for an allocation that is already going away.
    Every line is flushed, since the process is expected to be killed.
    """
    signal.signal(signal.SIGTERM, _note_signal)
    signal.signal(signal.SIGINT, _note_signal)
    job_id = os.environ.get('SLURM_JOB_ID', '')
    start = time.monotonic()
    print(f'-- watching for {duration:g}s every {interval:g}s --', flush=True)
    while time.monotonic() - start < duration:
        elapsed = time.monotonic() - start
        fast_path = _try(running_on_allocated_node)
        state = _try(lambda: get_slurm_job_state(job_id))
        print(
            f'WATCH {label} '
            f'{datetime.datetime.now().astimezone().isoformat()} '
            f'elapsed={elapsed:7.1f} '
            f'host={_short_hostname(socket.gethostname())} '
            f'fast_path={_flat(fast_path)} '
            f'state={_flat(state)}',
            flush=True,
        )
        time.sleep(interval)
    print(f'-- watch finished after {duration:g}s --', flush=True)


def _note_signal(signum, frame) -> None:
    """Record a signal and keep going, so the window can be measured."""
    name = signal.Signals(signum).name
    print(
        f'SIGNAL {name} at '
        f'{datetime.datetime.now().astimezone().isoformat()} -- ignored so '
        f'that the watch can see what happens next',
        flush=True,
    )


def _flat(result: dict) -> str:
    """One-line form of a recorded result, for the watch lines."""
    if 'error' in result:
        return f'<{result["error"]}>'
    return str(result['value'])


def _collect(label: str) -> dict:
    """Gather every observation, catching failures rather than exiting."""
    job_id = os.environ.get('SLURM_JOB_ID', '')

    record: dict = {
        'label': label,
        'when': datetime.datetime.now().astimezone().isoformat(),
        'pid': os.getpid(),
        'ppid': os.getppid(),
        'hostnames': {
            'socket.gethostname': socket.gethostname(),
            'platform.node': platform.node(),
            'os.uname().nodename': os.uname().nodename,
            'socket.getfqdn': socket.getfqdn(),
            'short': _short_hostname(socket.gethostname()),
        },
        'env': {name: os.environ.get(name) for name in SLURM_ENV_VARS},
        'slurm_version': list(get_slurm_version() or ()),
        'live_job_states': sorted(LIVE_JOB_STATES),
    }

    record['expanded_nodelist'] = _try(_expand_job_nodelist)
    record['fast_path'] = _try(running_on_allocated_node)
    record['job_state'] = _try(lambda: get_slurm_job_state(job_id))
    record['parallel_system'] = _try(_build_parallel_system)

    fast_path = record['fast_path'].get('value')
    state = record['job_state'].get('value')
    if fast_path is True and state is not None:
        record['agrees'] = state in LIVE_JOB_STATES
    else:
        # the fast path only ever claims "live", so there is nothing to
        # disagree about when it declines to answer
        record['agrees'] = None
    return record


def _build_parallel_system() -> dict:
    """
    Build a parallel system, counting the batch-system queries it makes.

    An empty ``squeue_calls`` is the result this branch is after: the node
    count comes from the environment on #477, and the liveness check is
    skipped entirely when the fast path answers.
    """
    # subprocess.check_output() calls subprocess.run(), and every module
    # here shares the one subprocess module object, so patching run() once
    # catches every command the code under test issues -- including the
    # check_output() calls that _get_subprocess_int() and
    # _get_subprocess_str() are built on.
    real_run = subprocess.run
    recorder = _RecordingRun(real_run)
    subprocess.run = recorder  # type: ignore[assignment]
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            system = get_parallel_system(_get_config())
        warned = [str(warning.message) for warning in caught]
    finally:
        subprocess.run = real_run  # type: ignore[assignment]

    calls = recorder.calls
    return {
        'class': type(system).__name__,
        'nodes': getattr(system, 'nodes', None),
        'mpi_allowed': system.mpi_allowed,
        'warnings': warned,
        'subprocess_calls': calls,
        'squeue_calls': [
            call for call in calls if call and 'squeue' in call[0]
        ],
    }


def _get_config() -> ConfigParser:
    """
    A minimal slurm config, so the probe does not need a mache machine.

    Reading the real machine config would drag in machine discovery, which
    is not what is under test here and would fail on a node that cannot see
    the shared filesystem the config lives on.
    """
    config = ConfigParser()
    config.add_section('parallel')
    config.set('parallel', 'system', 'slurm')
    config.set('parallel', 'parallel_executable', 'srun')
    config.set('parallel', 'cores_per_node', '128')
    config.set('parallel', 'login_cores', '4')
    return config


def _try(func) -> dict:
    """Call something, keeping the exception if there is one."""
    try:
        return {'value': func()}
    except Exception as exception:  # noqa: BLE001 -- a probe records anything
        return {
            'error': f'{type(exception).__name__}: {exception}',
        }


def _report(record: dict) -> None:
    label = record['label'] or '(unlabeled)'
    print(f'==== liveness probe: {label} ====')
    print(f'when                {record["when"]}')
    print(f'pid/ppid            {record["pid"]}/{record["ppid"]}')
    print('')
    print('-- hostname, as each source spells it --')
    for name, value in record['hostnames'].items():
        print(f'{name:<24} {value!r}')
    print('')
    print('-- Slurm environment --')
    for name, value in record['env'].items():
        if value is not None:
            print(f'{name:<24} {value!r}')
    unset = [name for name, value in record['env'].items() if value is None]
    print(f'{"(unset)":<24} {" ".join(unset)}')
    version = record['slurm_version']
    print(f'{"slurm version":<24} {".".join(str(part) for part in version)}')
    print('')
    print('-- expanded node list --')
    _print_result(record['expanded_nodelist'])
    print('')
    print('-- the two verdicts --')
    print(f'{"fast path (local)":<24} ', end='')
    _print_result(record['fast_path'])
    print(f'{"job state (controller)":<24} ', end='')
    _print_result(record['job_state'])
    print(f'{"fast path agrees":<24} {record["agrees"]}')
    print('')
    print('-- get_parallel_system() --')
    system = record['parallel_system']
    if 'error' in system:
        _print_result(system)
    else:
        value = system['value']
        print(f'{"system":<24} {value["class"]}')
        print(f'{"nodes":<24} {value["nodes"]}')
        print(f'{"mpi_allowed":<24} {value["mpi_allowed"]}')
        print(f'{"squeue calls":<24} {len(value["squeue_calls"])}')
        for call in value['subprocess_calls']:
            print(f'{"":<24} ran: {" ".join(call)}')
        if value['squeue_calls']:
            # This branch is off main, so the node count still comes from
            # squeue. #477 is what removes that one, reading the count from
            # SLURM_JOB_NUM_NODES instead. A `-o %D` call here is that one
            # and not the liveness check, which asks with `-t all -o %T`.
            print(
                f'{"":<24} note: a `-o %D` call is the node count, which '
                f'#477 removes; the liveness query is `-t all -o %T`'
            )
        for message in value['warnings']:
            print(f'{"":<24} warned: {message}')
    print('')


def _print_result(result: dict) -> None:
    if 'error' in result:
        print(f'ERROR {result["error"]}')
    else:
        print(result['value'])


if __name__ == '__main__':
    sys.exit(main())
