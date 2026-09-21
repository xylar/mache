# Chrysalis testing of mache's Spack 1.x branch

Written for an agent on Chrysalis. Dense on purpose. Read `handoff.md`
(sections 1–2 for facts, 10–12 for what has been verified) and, for the
spec, `spack_v1_design.md`. Both live only on this throwaway branch
(`spack-v1-design-notes`); the code under test is branch `spack-v1-design`
of `xylar/mache`, PR https://github.com/E3SM-Project/mache/pull/492.

## Ground rules

- Do not commit to `spack-v1-design` unless something is a real bug in
  mache or the overlay; then commit with a clear message, run
  `pixi run pytest` + pre-commit, and push to `xylar/mache` (it is the PR
  branch). Overlay fixes go to `E3SM-Project/e3sm-spack-packages@main` and
  the new commit SHA into `mache/spack/pins.yaml`.
- Record everything else (outcomes, logs worth keeping, open questions) in
  `chrysalis_results.md` on this notes branch and push it; the laptop
  session will fold it into the PR's `Testing` comment.
- Use a fresh `spack_path` for every test; never a path that holds a Spack
  0.x instance. Suggested root: `/lcrc/group/e3sm/<user>/spack-v1-test/`.
- Downstream repositories: clone `E3SM-Project/polaris`,
  `E3SM-Project/e3sm-unified` and `MPAS-Dev/compass` at `main`. Do not push
  anything to them. Their `deploy.py` takes
  `--mache-fork xylar/mache --mache-branch spack-v1-design` (note:
  `owner/repo`), which downloads `mache/deploy/bootstrap.py` from that
  branch and installs mache 5.0.0rc1 from it; `--spack-path` overrides the
  Spack instance location; `--deploy-spack` forces the Spack build;
  `--recreate` rebuilds the pixi env too.
- Builds are long (E3SM-Unified's ESMF/MOAB/NCO stack takes hours). Run
  under `nohup`/`screen` with a log file, and prefer a compute-node
  allocation for the `spack install` phase if the login nodes throttle.

## What the branch does (one paragraph)

`mache` clones `spack/spack@v1.2.2`, `spack/spack-packages@v2026.06.0`
(`builtin`) and `E3SM-Project/e3sm-spack-packages` (`e3sm`, pinned by
commit, searched first) into `spack_path`, writes `etc/spack/repos.yaml`,
runs `spack isolate --self`, builds the environment from the rendered
template, then captures `spack env activate --sh` into
`var/spack/environments/<env>/activate.sh` and `.csh`; load scripts source
that file. Templates use compiler externals + a `mache` toolchain
(`packages:all:require: ["%mache"]`), no `%compiler` on specs. Hooks still
get the dynamic activation string.

## Tests, in order

### 1. polaris, gnu/openmpi (the default path)

```bash
git clone https://github.com/E3SM-Project/polaris.git polaris && cd polaris
./deploy.py --machine chrysalis --compiler gnu --mpi openmpi --deploy-spack \
    --spack-path /lcrc/group/e3sm/$USER/spack-v1-test/polaris \
    --mache-fork xylar/mache --mache-branch spack-v1-design 2>&1 | tee deploy.log
```
polaris's default compiler on Chrysalis is intel; `--compiler gnu` picks
`chrysalis_gnu_openmpi.yaml` (library env `spack_env_gnu_openmpi`) while
the "software" env uses `[deploy] software_compiler = intel`, i.e.
`chrysalis_intel_openmpi.yaml`. So this one run exercises both templates.
If the intel one fails, note it and rerun with `--no-spack`-free but
`spack.software.supported` disabled via a temporary edit of
`deploy/config.yaml.j2` (do not commit) to still get the gnu library env.

Check:
- `deploy_tmp/spack/build_spack_env_gnu_openmpi.bash` and its log: the three
  clones, `etc/spack/repos.yaml` with `e3sm` then `builtin`, `spack repo
  list` showing both `[+]`, `spack isolate --self` once (no "already
  exists" error), `spack install` completes.
- `deploy_tmp/spack/spack_env_gnu_openmpi.provenance.yaml` has the three
  commits; `*.spack.lock` copied.
- `<spack_path>/var/spack/environments/spack_env_gnu_openmpi/activate.sh`:
  only `export X="…${X:+:$X}"` prepends for path-like variables (`PATH`,
  `CMAKE_PREFIX_PATH`, `PKG_CONFIG_PATH`, `ACLOCAL_PATH`, `MANPATH`, maybe
  `LD_LIBRARY_PATH`) plus literal `export`s (`SPACK_ENV`, `SPACK_ENV_VIEW`,
  `MPICC`…, `HDF5_PLUGIN_PATH`, `ESMFMKFILE` in the software env). Nothing
  that assigns the capturing shell's full `PATH`.
- Compare with dynamic activation in a fresh login shell:
  `source <spack_path>/share/spack/setup-env.sh; spack env activate
  spack_env_gnu_openmpi; env | sort > dyn.txt` versus `source
  load_polaris_chrysalis_gnu_openmpi.sh; env | sort > cap.txt` (the load
  script also loads modules from `config_machines.xml`, so compare the
  view-related entries, not the whole file).
- In that sourced shell: `which nc-config` → the view; `echo $PIO` → the
  view; `which python` → the pixi env (not a Spack python); `spack find`
  works (plain executable; `spack env activate` is not expected to work).
- Module loads from `config_machines.xml` (gcc/11.2.0-bgddrif,
  openmpi/4.1.6-ggebj5o…) still appear in the load script after the
  `source …/activate.sh` line.
- Rerun the same `./deploy.py` command without `--recreate`: the existing
  instance is fetched/reset, `spack isolate --self` runs again without
  error and the bootstrap store under `etc/spack/isolate/bootstrap` is
  reused (no re-download of clingo).

### 2. E3SM-Unified, gnu (overlay subclasses + the mpi4py hook)

```bash
git clone https://github.com/E3SM-Project/e3sm-unified.git && cd e3sm-unified
./deploy.py --machine chrysalis --compiler gnu --mpi openmpi --deploy-spack \
    --spack-path /lcrc/group/e3sm/$USER/spack-v1-test/e3sm-unified \
    --mache-fork xylar/mache --mache-branch spack-v1-design 2>&1 | tee deploy.log
```
(Check `./deploy.py --help` for the exact flags; E3SM-Unified may want a
`--prefix`.) This builds `esmf@8.9.1` (overlay subclass: no Spack python
in the view), `moab@5.6.0` (overlay: eigen 3.x), `nco@5.3.9`,
`tempestremap@2.2.0` (overlay: patch), `tempestextremes@2.4.2` (overlay:
new version). Check the view has no `bin/python`; `ESMFMKFILE` is a
literal `export` in `activate.sh`; the `post_spack` hook that appends
`spack_result['activation']` and builds `mpi4py` against the view's
`mpicc` succeeds (it must see the *dynamic* form: `source setup-env.sh` +
`spack env activate`).

### 3. compass, gnu with Albany

```bash
git clone https://github.com/MPAS-Dev/compass.git && cd compass
./deploy.py --machine chrysalis --compiler gnu --mpi openmpi --deploy-spack \
    --with-albany --spack-path /lcrc/group/e3sm/$USER/spack-v1-test/compass \
    --mache-fork xylar/mache --mache-branch spack-v1-design 2>&1 | tee deploy.log
```
On 2026-09-21 compass `main`'s pixi solve failed on the laptop
(`mpas_tools 1.5.1` needs `libnetcdf 4.10.0`; conda-forge `esmf 8.9.1`
wants an older one). If it fails the same way here, stop and report; that
is compass's problem, not this branch's. Otherwise this exercises
`trilinos-for-albany@compass-2026-02-06` and `albany@compass-2026-03-21`
(the E3SM-only overlay packages) and compass's `post_spack` hook, which
adds `LD_LIBRARY_PATH` to `modules:prefix_inspections`; the captured
`activate.sh` must then prepend the view's `lib` and `lib64` to
`LD_LIBRARY_PATH`.

### 4. Only if time allows: chrysalis intel/openmpi as a library env

`chrysalis_intel_openmpi.yaml` was migrated mechanically: compiler
`intel-oneapi-compilers@2025.2.0` with absolute `icx/icpx/ifx` paths, and
a secondary `gcc@11.3.0` external with `extra_attributes.compilers` (the
0.x template listed both under `packages:all:compiler`; the 1.x toolchain
requires oneapi for everything). Deploy polaris with `--compiler intel`
and note whether any package refuses to build with oneapi and would have
needed the gcc fallback.

## What to report

Per test: pass/fail, the log path, deviations from the checks above, and
any error text. Anything that looks like a template problem (wrong prefix,
missing module, external not found) is worth fixing on the PR branch with
the mache tests updated; anything that looks like a recipe problem goes to
the overlay.
