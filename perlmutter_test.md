# Perlmutter testing of mache's Spack 1.x branch

Written for an agent on Perlmutter. Dense on purpose. Read
`chrysalis_test.md` (ground rules, the per-test check list),
`chrysalis_results.md` and `aurora_results.md` (what broke there, how it
was fixed, the traps) first; `handoff.md` §§1–2, 10–12 and
`spack_v1_design.md` for the spec. All on this throwaway branch
(`spack-v1-design-notes`); the code under test is branch `spack-v1-design`
of `xylar/mache`, PR https://github.com/E3SM-Project/mache/pull/492, now
rebased on `main` (4.0.1rc1).

Perlmutter is the last machine worth testing before 5.0.0: the only heavily
used one whose compiler model differs from everything tested so far (Cray
PE wrappers, modules-only compiler externals, `nvhpc`, `cray-libsci` as
lapack).

## Ground rules (differences from Chrysalis and Aurora)

- Same rules: mache fixes on the PR branch with tests and pre-commit, pushed
  to `xylar/mache`; overlay fixes to `E3SM-Project/e3sm-spack-packages@main`
  with the SHA into `mache/spack/pins.yaml`; everything else into
  `perlmutter_results.md` on this notes branch. Fresh `spack_path` per test.
- Suggested root: `$CFS/e3sm/$USER/spack-v1-test/` (`$SCRATCH` is purged
  after eight weeks; fine for the deploys but not for anything you want to
  show Xylar later). Never the shared
  `/global/cfs/cdirs/e3sm/software/polaris/pm-{cpu,gpu}/` or
  `/global/common/software/e3sm/anaconda_envs`.
- Slurm: `-A e3sm -C cpu -q debug` (30 min) or `-q regular`; `-C gpu` for
  pm-gpu jobs, though every Spack build here is a host build and the
  deploys can run on a login node under `nohup`. Perlmutter compute nodes
  reach the internet without a proxy; check once with `curl -sI
  https://github.com`. Compute-node `/tmp` is RAM-backed: pass
  `--spack-tmpdir` (E3SM-Unified) and put `PIXI_CACHE_DIR` under the test
  root, not `$HOME` (small quota).
- Deploys wipe `deploy_tmp` themselves; a rerun always re-clones mache. (An
  earlier note claiming otherwise was wrong; mache #494.)
- E3SM-Unified `main` before PR 157 writes into the production login env
  with `--prefix` (e3sm-unified#156). Check out PR 157 first
  (`git fetch origin pull/157/head:pr-157 && git checkout pr-157`) or skip
  test 2.
- polaris's `pm-cpu.cfg` and `pm-gpu.cfg` already use mache's compiler
  names (`gnu`, `gnugpu`, `intel`, ...), so no cfg edit is needed here.

## What is expected to be wrong or untested in the pm templates

None of `pm-cpu_*` / `pm-gpu_*` has been run under Spack 1.x. Compared to
Chrysalis/Aurora:

1. **Compiler paths are the Cray wrappers, as bare names.**
   `pm-cpu_gnu_mpich.yaml`, `pm-gpu_gnugpu_mpich.yaml` and
   `pm-gpu_gnu_mpich.yaml` have `c: cc`, `cxx: CC`, `fortran: ftn` in the
   `gcc` external's `extra_attributes.compilers` (the design chose the
   wrappers on purpose; `docs/developers_guide/spack.md` says so). The
   wrappers only resolve once the external's `modules:` (`PrgEnv-gnu/8.6.0`,
   `gcc-native/14`, `cray-libsci/25.09.0`, `craype-accel-host`,
   `craype/2.7.35`) are loaded, which the prologue does. Things to watch,
   in order of likelihood: Spack rejecting a non-absolute compiler path at
   concretization or when it builds `compiler-wrapper`; `gcc-runtime`
   detection failing through the wrapper (Spack runs the compiler to find
   `libstdc++` etc.); linking against the wrong libsci. Fallbacks, to try in
   this order and record which one works: (a) absolute wrapper paths
   (`/opt/cray/pe/craype/2.7.35/bin/cc`, `CC`, `ftn`); (b) the underlying
   gcc-native binaries (`module show gcc-native/14` gives the prefix;
   probably `/opt/cray/pe/gcc-native/14/bin/gcc`, `g++`, `gfortran`) while
   keeping the same `modules:` list so `cray-mpich` and `cray-libsci` still
   come from the PE. If (b) is what works, the template comment and the
   developer docs sentence about wrappers change too.
2. **The compiler external is modules-only** (no `prefix:`), and so are
   `cray-mpich` (`libfabric/1.22.0`, `cray-mpich/9.0.1`) and `cray-libsci`.
   For `gcc` Spack takes the compiler paths from `extra_attributes`, so the
   inferred prefix should not matter the way it did for oneAPI; if it does
   (errors mentioning the gcc prefix), add `prefix:` from `module show
   gcc-native/14`. The already-loaded-module regression is covered by the
   `spack-52752` patch; confirm the build script prints the patch step and
   the provenance yaml lists `spack: patches:`.
3. **`PKG_CONFIG_PATH` in the compiler external's `environment:`**
   (`prepend_path: PKG_CONFIG_PATH: /opt/cray/xpmem/.../pkgconfig`, the
   design's "moved `PKG_CONFIG_PATH` prepend"): it must reach the build
   environment (`spack build-env e3sm-scorpio -- printenv PKG_CONFIG_PATH`
   in the activated env shows the xpmem dir) and must *not* appear in the
   captured `activate.sh` (build-time only).
4. `concretizer: unify: when_possible` on pm-cpu (Chrysalis/Aurora use
   `true`). If concretization produces two versions of something, or the
   view complains about conflicts, note it; do not change it without
   checking why it was set (git log of the template).
5. `lapack`/`blas` providers are `cray-libsci@25.09.0`; the software env's
   ESMF and MOAB link against it. Check `ldd` of `ESMF_RegridWeightGen`
   for `libsci`.
6. The `pm-cpu.sh` / `pm-gpu.sh` template overrides
   (`export NERSC_HOST=perlmutter` when unset) must appear in the load
   script after the captured activation is sourced.
7. **pm-gpu with `gnugpu`** (polaris's library compiler on pm-gpu; the
   software env uses `gnu`): same wrappers, `craype-accel-nvidia80`
   instead of `-host`. `nvhpc@25.9`/`cuda@12.9` (`pm-gpu_nvidiagpu_mpich`,
   `pm-cpu_nvidia_mpich`) are not used by any downstream deploy today;
   test only if time allows (`--compiler nvidiagpu` needs a template
   override in polaris, so do it with `make_spack_env` or a hand-written
   `spack.yaml` instead). `pm-cpu_intel_mpich` uses
   `intel-oneapi-compilers@2025.3` with `modules: [PrgEnv-intel/8.6.0]`
   and no `prefix:`, the pattern that broke on Chrysalis and Aurora; it is
   also unused downstream, so note it and fix it only if you get to it
   (oneAPI root from `module show intel/2025.3` or `echo $ONEAPI_ROOT`).

## Tests, in order

### 1. polaris, pm-cpu gnu/mpich

```bash
git clone https://github.com/E3SM-Project/polaris.git polaris && cd polaris
export PIXI_CACHE_DIR=$CFS/e3sm/$USER/spack-v1-test/pixi-cache
./deploy.py --machine pm-cpu --compiler gnu --mpi mpich --deploy-spack \
    --spack-path $CFS/e3sm/$USER/spack-v1-test/polaris_pm-cpu_spack \
    --mache-fork xylar/mache --mache-branch spack-v1-design 2>&1 | tee deploy.log
```
Both envs use `pm-cpu_gnu_mpich.yaml` (`software_compiler = gnu`). If
concretization or `compiler-wrapper`/`gcc-runtime` fails on the compiler
(item 1), verify the fallback by editing the env's `spack.yaml` under
`<spack_path>/var/spack/environments/<env>/` and running `spack concretize
-f` / `spack install` by hand in an `env -i bash -l` shell that sourced the
rendered `deploy_tmp/spack/<env>.prologue.sh` and
`<spack_path>/share/spack/setup-env.sh`; then commit the template change
(`tests/test_spack_templates.py` must pass). Then the check list from
`chrysalis_test.md` test 1 plus items 3–6 above, and a rerun on the
existing instance.

### 2. E3SM-Unified, pm-cpu gnu/mpich (PR 157 checked out)

```bash
git clone https://github.com/E3SM-Project/e3sm-unified.git && cd e3sm-unified
git fetch origin pull/157/head:pr-157 && git checkout pr-157
./deploy.py --machine pm-cpu --deploy-spack \
    --prefix $CFS/e3sm/$USER/spack-v1-test/e3sm-unified-pixi \
    --spack-tmpdir $CFS/e3sm/$USER/spack-v1-test/spack-tmp \
    --mache-fork xylar/mache --mache-branch spack-v1-design 2>&1 | tee deploy.log
```
Confirm every `Running from:` path is under the test root before it gets
far. Builds esmf, moab, nco, tempestremap, tempestextremes against Cray's
hdf5/netcdf modules (`use_e3sm_hdf5_netcdf = True`). Checks from
`chrysalis_test.md` test 2 (no `bin/python` in the view, `ESMFMKFILE`
literal, the mpi4py hook against `cray-mpich`'s `cc`; `python -c 'import
mpi4py.MPI'` on a compute node).

### 3. polaris, pm-gpu gnugpu/mpich

Same as test 1 with `--machine pm-gpu --compiler gnugpu --mpi mpich` and a
new `--spack-path` (`polaris_pm-gpu_spack`). Library env from
`pm-gpu_gnugpu_mpich.yaml`, software env from `pm-gpu_gnu_mpich.yaml`.
Runs fine from a login node. Check `craype-accel-nvidia80` appears in the
load script's modules and the software env is `gnu`, not `gnugpu`.

### 4. MPAS-Ocean `pr` suite and Omega `omega_pr` on pm-cpu gnu

The end-to-end check of the library env (PIO, metis, parmetis, the Cray
hdf5/netcdf modules) through a model build. In a fresh shell:

```bash
source load_polaris_pm-cpu_gnu_mpich.sh
polaris suite -c ocean -t pr --clean_build --model mpas-ocean \
    -w $SCRATCH/spack-v1-test/mpaso_pr_gnu_mpich
cd $SCRATCH/spack-v1-test/mpaso_pr_gnu_mpich && sbatch job_script_pr.sh
```
and the same with `-t omega_pr --model omega` into `omega_pr_gnu_mpich`
(Omega `develop` is fine on Perlmutter; the compiler rename only affected
Aurora). Compare against the most recent polaris testing on pm-cpu
(polaris PR 793's Testing comment, or ask Xylar); a build failure that
mentions the compiler, a module, `PIO`, `METIS_ROOT` or `PARMETIS_ROOT` is
a mache problem, a task that also fails in the baseline is not.

### 5. Only if time allows

`pm-cpu_intel_mpich` (oneAPI prefix, item 7) via polaris `--compiler
intel`; `pm-gpu_nvidiagpu_mpich` via `make_spack_env`.

## What to report

Per test: pass/fail, log path, deviations, error text, the final template
diff, and specifically which compiler-path form (wrappers, absolute
wrappers, gcc-native binaries) worked, since that decides the wording in
`docs/developers_guide/spack.md`.
