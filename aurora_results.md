# Aurora results for mache's Spack 1.x branch

Recorded by Claude Code on Aurora, 2026-09-21, following `aurora_test.md`.
Test root: `/lus/flare/projects/E3SM_Dec/xylar/spack-v1-test/` (downstream
clones `polaris/`, `e3sm-unified/`; Spack instances `polaris_spack/`,
`polaris_intelgpu_spack/`, `e3sm-unified-pixi_spack/`).

## Facts worth recording

- oneAPI root: `/opt/aurora/26.26.0/oneapi`; `compiler/2025.3/env/vars.sh`
  exists and `compiler/latest -> 2025.3`. The `oneapi/release/2025.3.1`
  module sets `ONEAPI_ROOT` to that root and `depends_on("gcc/13.4.0")`.
- gcc: there is no `gcc/13.3.0` module (`module avail gcc`: 12.5.0 and
  13.4.0, the latter loaded by default). The install the template already
  pointed at, `/opt/aurora/26.26.0/spack/unified/1.1.1/install/linux-x86_64/gcc-13.4.0-hgnyg4p`,
  reports `gcc (Spack GCC) 13.4.0`.
- All other external prefixes in `aurora_intel_mpich.yaml` exist (the
  `25.190.0` paths for gmake, libxml2 and python 3.10.14 included) and the
  `/usr` versions match (bison 3.0.4, curl 7.79.1, openssl 1.1.1l, xz 5.2.3,
  perl 5.26.1).
- Compute nodes reach GitHub, conda-forge and prefix.dev only through the
  ALCF proxy (`HTTP_PROXY=HTTPS_PROXY=http://proxy.alcf.anl.gov:3128`);
  without it every `curl` fails. Their `/tmp` is a 504 GB tmpfs.
- Queues: `debug` and `debug-scaling` allow one hour; every other queue a
  single-node job could use needs 256 nodes or is disabled (`tiny`). So a
  compute-node deploy has one hour per job and relies on the
  existing-instance path to continue.
- SUSE's `/etc/profile.d/profile.sh` unsets the lowercase `*_proxy`
  variables and `NO_PROXY` in every login shell because
  `/etc/sysconfig/proxy` has `PROXY_ENABLED=no`. `HTTP_PROXY` and
  `HTTPS_PROXY` (uppercase) survive.

## Fixes committed to the PR branch

- `51ec1d18` Fix the oneAPI and gcc externals in the Aurora template:
  `prefix: /opt/aurora/26.26.0/oneapi` on `intel-oneapi-compilers`; the
  `gcc` external is `gcc@13.4.0`, module `gcc/13.4.0`, with the install
  above as `prefix`. Applied before the first deploy rather than after a
  failed attempt: the oneAPI failure was already demonstrated twice on
  Chrysalis and the gcc module simply does not exist. Template tests and
  `tests/` (594 passed, 6 skipped); pre-commit clean.

- `37dbba45` Export the caller's proxy variables in the Spack build script.
  Xylar asked for deploys to work on compute nodes. The build script runs
  under `env -i bash -l`, which drops the proxy variables a job script
  exports, and passing them on the `env -i` command line is not enough
  because of the SUSE profile above. `render_install_script` now emits
  `export` lines for `http_proxy`, `https_proxy`, `ftp_proxy`, `no_proxy`
  and their uppercase forms (those set in the calling environment) right
  after the prologue. Unit tests for the export list and its position;
  users guide notes it.

- `ab945662` Clone the mache fork over https in the bootstrap. Attempt 1 of
  the polaris deploy (job 8846564, `deploy_attempt1_ssh_clone.log`) hung on
  `git clone ... git@github.com:xylar/mache.git`: ssh does not go through
  the http proxy. Pre-existing on `main` (first bootstrap draft), but it
  blocks every `--mache-fork` deploy on a compute node here. Test added.

## Observations not tied to a test

- polaris's submodules use ssh URLs (`.gitmodules`: `git@github.com:...`),
  so `mache.jigsaw` failed on a compute node at `git submodule update --init
  jigsaw-python` (attempt 2, job 8846594, `deploy_attempt2_jigsaw_ssh.log`:
  `ssh: connect to host github.com port 22: Connection timed out`). polaris's
  problem, not mache's; worked around by initialising the submodule from the
  login node before the deploy.

- Overlay `a23a0a2` (pushed to `E3SM-Project/e3sm-spack-packages@main` with
  Xylar's OK; pinned by `b8074fd0`): esmf queries the
  oneAPI GCC toolchain with Spack's `Executable`. Attempt 3 (job 8846622,
  `deploy_attempt3_esmf_py36.log`) built the whole library env and most of
  the software env, then `esmf@8.9.1` failed in `setup_build_environment`:
  `TypeError: __init__() got an unexpected keyword argument
  'capture_output'` from `/usr/lib64/python3.6`. Spack runs under the login
  shell's `python3`, which on Aurora is 3.6.15; `subprocess.run(...,
  capture_output=True, text=True)` needs 3.7. The `.cfg` fast path did not
  apply because Aurora's `icpx.cfg` says `--gcc-install-dir=`, not
  `--gcc-toolchain=`. Verified with `spack python` on the login node: the
  fixed helper returns `.../gcc-13.4.0-hgnyg4p/lib64` and `None` for a
  missing compiler; `spack audit packages esmf` passes.

## 1. polaris, intel/mpich

Run as PBS jobs on one compute node (`deploy_aurora.pbs` in the clone:
`debug` queue, one hour, the ALCF proxy exported, `PIXI_CACHE_DIR` under
the test root). polaris `main` at `ca3dfa8e0`; `polaris/machines/aurora.cfg`
edited locally (not committed) to `compiler = intel`,
`software_compiler = intel`, `mpi_intel = mpich`, `mpi_intelgpu = mpich`;
`--compiler intel --mpi mpich` passed explicitly. Without the cfg edit the
software env would look for `aurora_oneapi-ifx_mpich.yaml`.

Attempt 1 (job 8846564, mache `37dbba45`): hung on the ssh clone of the
mache fork (see `ab945662`). Attempt 2 (job 8846594, mache `ab945662`):
mache cloned over https through the proxy and installed; failed on
polaris's ssh submodule URL (see observations). Attempt 3 (job 8846622,
`deploy_attempt3_esmf_py36.log`, fresh `polaris_spack`): pixi env, JIGSAW,
the three clones through the proxy (`export HTTP_PROXY=...` lines present
in `build_spack_env_intel_mpich.bash`), `spack isolate --self`, the Spack
patch applied, `spack repo list` with `[+] e3sm` then `[+] builtin`;
library env `spack_env_intel_mpich` concretized 9 specs and built
`compiler-wrapper`, `gcc-runtime@13.4.0` (from the `gcc@13.4.0` external),
`intel-oneapi-runtime@2025.3.1`, `metis`, `parmetis`, `e3sm-scorpio@2.0.3`
in under a minute (hdf5/netcdf/pnetcdf/mpich/cmake external). So both
template fixes work on the first try. Software env `polaris_software`:
existing-instance path (fetch/reset, isolate preserved), built zstd,
libsigsegv, eigen 3.4.1, file, m4, autoconf, automake, libtool, zoltan,
openblas 0.3.33 (3.5 min), tempestremap 2.2.0 (overlay patch), moab 5.6.0
(3 min); `esmf@8.9.1` failed on the overlay's Python 3.7 call (see
`a23a0a2`). 19 min of walltime.

Attempt 4 (job 8846676, `deploy.log`, existing instance, overlay pinned to
`a23a0a2` through a local `spack.pins` override in polaris's
`deploy/config.yaml.j2`): **pass**, 27 min. Doubles as the "rerun without
--recreate" check: the three checkouts fetched/reset (the log's first
`HEAD is now at 266bc2c` is `git checkout --detach` printing the old head
before `reset --hard a23a0a2`), the patch reapplied, no clingo download
(the bootstrap store was reused; attempt 3 had fetched it), both envs
"recreating environment" with every package `[+]`, esmf 8.9.1 built with
oneAPI in 13 min, activation captured, polaris installed, load script
written.

Checks (fresh `env -i bash -l` shells on the login node):
- `deploy_tmp/spack/spack_env_intel_mpich.{yaml,provenance.yaml,spack.lock,raw_activate.sh,env_before,prologue.sh}`
  present; provenance has spack `3e19345b`, `patches:
  spack-52752-load-module-already-loaded.patch`, e3sm `a23a0a22`, builtin
  `d4f7c711`.
- `etc/spack/repos.yaml`: `e3sm` then `builtin`, path-based.
- `spack_env_intel_mpich/activate.sh`: literals `SPACK_ROOT`, `SPACK_ENV`,
  `SPACK_ENV_VIEW`; prepends only (`${X:+:$X}`, `${MANPATH:-}`) for `PATH`
  (spack bin, then view bin), `ACLOCAL_PATH`, `CMAKE_PREFIX_PATH`, `MANPATH`,
  `PKG_CONFIG_PATH`; `/usr` externals contribute `/usr/share/aclocal` and the
  three `/usr` pkgconfig dirs. No "lost elements" warning.
  `polaris_software` has no `activate.sh` (by design).
- Dynamic vs captured: identical elements and order for `PATH`,
  `CMAKE_PREFIX_PATH`, `PKG_CONFIG_PATH`, `ACLOCAL_PATH`, `SPACK_ENV`. Only
  difference: `MANPATH` has `/usr/share/man` first in the dynamic form and
  last in the captured one, because it was already in the login shell's
  `MANPATH` and the rewrite only prepends new elements. Harmless.
- After sourcing `load_polaris_aurora_intel_mpich.sh`: `$PIO`, `METIS_ROOT`,
  `PARMETIS_ROOT` -> the library view; `POLARIS_COMPILER=intel`; `python`
  -> pixi env; `nc-config` -> the `netcdf-c/4.9.3` module (Aurora uses
  E3SM's netcdf); `ESMF_RegridWeightGen` -> `polaris_software` view;
  `spack find` works (23 specs). `mbtempest` -> `/lus/flare/projects/E3SMinput/soft/moab/bin`:
  the `moab/5.6.0` module from `config_machines.xml` is loaded after the
  software view goes on `PATH`, same as production polaris on Aurora.
  `ESMFMKFILE` is pixi's, as before.
- Load script order: software view `bin`, `source .../activate.sh`, then
  `module use /lus/flare/projects/E3SMinput/soft/modulefiles` and the
  `config_machines.xml` loads (oneapi/release/2025.3.1, moab/5.6.0,
  mpich-config/collective-tuning/1024, cmake/3.31.11, netcdf-c/4.9.3,
  netcdf-fortran/4.6.2) and the `FI_*`/`PALS_*` exports.
- Every built package in both envs is `%oneapi@2025.3.1` (`c`, `cxx` and/or
  `fortran` as each package needs); nothing fell back to gcc, nothing
  refused oneAPI. Builds with `%c=oneapi` only: automake, file, libsigsegv,
  libtool.

## 2. polaris, intelgpu/mpich

Job 8846766 (`deploy_intelgpu.log`, fresh `polaris_intelgpu_spack`, no
`--recreate`, overlay from the local clone at `a23a0a2`): **pass**, 50 min
of the hour (esmf took 20 min this time). Env names
`spack_env_intelgpu_mpich` and `polaris_software`; same 9 + 8 specs and
the same hashes as the intel instance (esmf `wjqojrj`, moab `foetsog`),
everything `%oneapi@2025.3.1`. `load_polaris_aurora_intelgpu_mpich.sh`
differs from the intel one only in the `intelgpu` names and paths and in
the `compiler="intelgpu"` block from `config_machines.xml`
(`MPIR_CVAR_ENABLE_GPU=1`, `romio_cb_*`, `GATOR_*`, the `CPU_BIND`/
`GPU_BIND`/`MEM_BIND` lists, `ZES_ENABLE_SYSMAN=1`, instead of
`LIBOMPTARGET_DEBUG`, `MPIR_CVAR_ENABLE_GPU=0`, `CPU_BIND=core`...).
Sourced: `$PIO` -> the intelgpu view, `POLARIS_COMPILER=intelgpu`,
`ESMF_RegridWeightGen` -> its software view, python from pixi, `spack
find` works.
- E3SM-Unified has the same ssh submodule problem
  (`recipes/e3sm-unified/e3sm-unified-feedstock`, attempt 1 of test 3, job
  8846790, `deploy_attempt1_feedstock_ssh.log`); worked around the same
  way. Both downstream repos would need https submodule URLs (or a
  `url.<https>.insteadOf` git config) for compute-node deploys at ALCF.

## 4. Omega and the `omega_pr` suite (intel and intelgpu)

Omega from `/home/xylar/e3sm_work/omega/test_merge_e3sm_master`
(`c3d40f027a`, E3SM `master` merged into Omega `develop`), fetched into
the polaris clone's `e3sm_submodules/Omega`. Builds on the login node
(`build_omega.sh` in the clone; nested submodules use ssh):
- intel: `omega_build_intel.log`, cmake with `-DOMEGA_CIME_COMPILER=intel`,
  `METIS_ROOT`/`PARMETIS_ROOT` from the captured activation's view;
  `omega.exe` built. `polaris suite -c ocean -t omega_pr` set up 24 tasks
  in `omega_pr_intel_mpich/` (target 800 cores).
- intelgpu: `omega_build_intelgpu.log`, `-DOMEGA_CIME_COMPILER=intelgpu`,
  roots from the intelgpu view; `omega.exe` built; suite in
  `omega_pr_intelgpu_mpich/` (24 tasks, minimum 24 GPUs).

- `c282988c` Create the Spack tmpdir before the deploy build. E3SM-Unified
  attempt 2 (job 8846984, `deploy_attempt2_tmpdir.log`) built
  compiler-wrapper, gcc-runtime, intel-oneapi-runtime, zstd, antlr, eigen,
  tempestextremes 2.4.2, openblas and more, but gsl, libsigsegv, libmd and
  file failed within seconds: `config.guess: cannot create a temporary
  directory in .../spack-tmp`. `--spack-tmpdir` named a directory that did
  not exist; the deploy path only exported `TMPDIR` (pre-existing on
  `main`; `make_spack_env` creates it). Spack's stages went to `/tmp`
  meanwhile, since `$tempdir` skips a missing `TMPDIR`. Test added.

Suite, intel (job 8846997, `omega_pr_intel_mpich/polaris_omega_pr.o8846997`,
2 nodes, 8.5 min): **19 of 24 pass**, the same five fail as in the
2026-09-21 baseline with mache 4.0.0: `baroclinic_channel/10km/{decomp,
restart,threads}`, `overflow/linear/zstar/smoke_test_horiz_adv_order_2_del4`,
`realistic_global/QU.240km/analysis_members_test`, each with `omega.exe`
exiting 143 at execution as in the baseline's `case_outputs`. Nothing
mentions a compiler name, a module or `PIO`/`METIS_ROOT`, so no mache
problem.

## 3. E3SM-Unified, intel/mpich (PR 157 checked out, `0f509b9`)

PBS jobs on one compute node (`deploy_aurora.pbs` in the clone: proxy
exported, `--prefix .../e3sm-unified-pixi`, `--spack-tmpdir .../spack-tmp`,
no `--spack-path`, so Spack went to `e3sm-unified-pixi_spack`). The same
local `spack.pins` override as polaris. Attempt 1 (job 8846790): the ssh
submodule (observations). Attempt 2 (job 8846984,
`deploy_attempt2_tmpdir.log`, mache `ab945662`): every `Running from:` path
under the test root (`e3sm-unified-pixi`, `_login`, `_spack`; "Skipping
shared load-script aliases" logged; nothing under
`/lus/flare/projects/E3SMinput`); fresh instance; env
`e3sm_unified_intel_mpich` concretized 10 specs: esmf 8.9.1 `~python`,
moab 5.6.0 with eigen 3.4.1, nco 5.3.9, tempestremap 2.2.0,
tempestextremes 2.4.2, plus hdf5/netcdf/pnetcdf/mpich external
(`use_e3sm_hdf5_netcdf = True` on Aurora); built compiler-wrapper,
gcc-runtime, intel-oneapi-runtime, zstd, antlr, eigen, tempestextremes,
openblas, esmf (20 min) and others; gsl, libsigsegv, libmd and file failed
on the missing tmpdir (see `c282988c`).

Attempt 3 (job 8847091, `deploy.log`, mache `c282988c`, existing instance):
**pass**, 24 min, exit 0. Fetch/reset/re-patch, isolate preserved, every
built package `[+]`; `spack-tmp` created and used (oneAPI temp files land
there); gsl, libsigsegv, libmd, file, m4, autoconf, automake, libtool,
udunits, nco (1.4 min), tempestremap, moab (2 min) built; the `post_spack`
hook (`deploy_tmp/post_spack_hpc.sh`, dynamic activation: `source
.../setup-env.sh` + `spack env activate e3sm_unified_intel_mpich`) built
mpi4py 4.1.1 against the view's mpicc; activation captured afterwards;
login env built; `load_e3sm-unified_aurora_intel_mpich.sh` written;
permissions updated under the test root only.

Checks:
- View has no `bin/python`; `ESMF_RegridWeightGen`, `mbtempest`,
  `GenerateOfflineMap`, `DetectNodes`, `ncremap`, `ncks` in the view.
- `activate.sh`: literals `SPACK_ROOT`, `SPACK_ENV`, `SPACK_ENV_VIEW`,
  `ESMFMKFILE` (view's `lib/esmf.mk`), `GSL_ROOT_DIR`, `UDUNITS2_XML_PATH`;
  prepends only for `PATH`, `ACLOCAL_PATH`, `CMAKE_PREFIX_PATH`, `CPATH`
  (eigen3), `MANPATH`, `PKG_CONFIG_PATH`. No `HDF5_PLUGIN_PATH` or `MPIFC`
  (netcdf and mpich are externals here). `activate.csh` has the `setenv`
  forms. Provenance lists the three commits and `spack: patches:` (the
  `e3sm` git is the local overlay clone because of the override).
- Login node: `source` works, python and `ncremap` from
  `e3sm-unified-pixi_login`, `mache 5.0.0rc1`.

Suite, intelgpu (job 8847116, `omega_pr_intelgpu_mpich/polaris_omega_pr.o8847116`,
2 nodes, 7.7 min): **19 of 24 pass**, the same five failures as intel and
the baseline. So the renamed compilers work end to end through the load
scripts' modules, `POLARIS_COMPILER`, the captured library env and Omega's
vendored CIME config on both toolchains.
- Compute node (job 8847176, `check_compute.log`): compute pixi env
  active; `ncremap`, `ESMF_RegridWeightGen`, `GenerateOfflineMap` from the
  view; `import mpi4py.MPI` reports MPICH 5.0.0 and `mpiexec -n 2` with
  mpi4py works; `spack find` works. `mbtempest` from the `moab/5.6.0`
  module and `ESMFMKFILE` pixi's, as for polaris and as on Chrysalis.

## Still open

- The final PR head `b8074fd0` (the pin) was not deployed again; the
  deploys above used the same overlay commit through a local `spack.pins`
  override, since removed from both clones.
- The downstream ssh submodule URLs (polaris, E3SM-Unified) for
  compute-node deploys at ALCF; not mache's.
