# Chrysalis results for mache's Spack 1.x branch

Recorded by Claude Code on Chrysalis, 2026-09-21, following
`chrysalis_test.md`. Test root: `/lcrc/group/e3sm/ac.xylar/spack-v1-test/`
(downstream clones `polaris/`, `e3sm-unified/`, `compass/`; Spack instances
`polaris_spack/`, `e3sm-unified_spack/`, `compass_spack/`). Per Xylar's
request the polaris test uses intel/openmpi (compass and E3SM-Unified are
gnu anyway); polaris gnu/openmpi is the "if time allows" item instead.

## Fixes committed to the PR branch

- `3554cfb1` Drop gcc-runtime externals from the oneAPI templates.
  `chrysalis_intel_openmpi.yaml` (and the Aurora oneAPI template) listed
  `gcc-runtime` as a `buildable: false` external, carried over from the
  0.x template. Spack 1.2.2's solver has `:- concrete(node(X,
  "gcc-runtime")), will_build_packages().` ("gcc-runtime is always built"),
  and `intel-oneapi-runtime` depends on `gcc-runtime`, so the first polaris
  intel deploy failed at concretization with `Cannot build gcc-runtime,
  since it is configured buildable:false and no externals satisfy the
  request.` Log:
  `/lcrc/group/e3sm/ac.xylar/spack-v1-test/polaris/deploy_attempt1_gcc-runtime.log`.
  Verified by editing the env's `spack.yaml` in place and running `spack
  concretize -f`: `gcc-runtime@11.3.0` is built from the `gcc@11.3.0`
  external and all built packages get `%c,cxx,fortran=oneapi@2025.2.0`.
  `pixi run pytest`: 592 passed, 6 skipped; pre-commit clean.

- `60298238` Give the Chrysalis oneAPI compiler external an explicit
  prefix. Attempt 3 concretized but `intel-oneapi-runtime` failed at once:
  `RuntimeError: Trying to source non-existing file:
  .../intel-oneapi-compilers-2025.2.0-f3alqc4/compiler/2025.2/compiler/2025.2/env/vars.sh`.
  The external had only `modules:`, so Spack inferred the prefix from the
  module (`.../compiler/2025.2`) and the oneAPI build system appended
  `compiler/2025.2` again. The site's own `packages.yaml` uses the oneAPI
  root as the prefix; the template now does too. Verified by patching the
  env's `spack.yaml` and running `spack install`: `intel-oneapi-runtime`,
  `metis`, `parmetis` and `e3sm-scorpio` built with oneAPI. Log:
  `deploy_attempt3_oneapi_prefix.log`. Template tests pass; pre-commit
  clean.

- `d6f91d7f` Give the Chrysalis oneAPI MKL external an explicit prefix.
  Same shape of failure as above, this time from the `intel-oneapi-mkl`
  external (modules only) when polaris's software env built `tempestremap`
  (MKL is its lapack provider): `.../intel-oneapi-mkl-2025.2.0-bcimxay/mkl/2025.2/mkl/2025.2/env/vars.sh`.
  Log: `deploy_attempt4_mkl_prefix.log`. Verified by patching the env's
  `spack.yaml` and building `tempestremap` (48 s, overlay patch applied).
  The gnu template already had the root prefix for MKL 2022.1.0. MKL was the
  last modules-only external in the intel template.

- `ccd7a842` Compare captured activation against normalized old path
  elements. The captured `activate.sh` for the polaris library env prepended
  `.` to `MANPATH` and the rewrite warned that the empty element was "lost".
  Cause: Spack's `PruneDuplicatePaths` runs `normpath` over every element of
  the variable (the capturing shell's `MANPATH` from lmod ends in `::`, and
  `normpath('') == '.'`). The dynamic activation has the same `.`, but the
  capture baked it in for everyone. The rewrite now compares against the
  normalized old elements in both directions; unit test added. Full suite:
  593 passed, 6 skipped. Polaris was later recaptured with the fix (attempt 6).

- `3e376126` + `30f97891` Patch Spack so an already-loaded external module
  is not an error. compass's gnu env failed at once on every package with a
  modules-only external in its DAG: `ModuleLoadError: Module
  'parallel-netcdf/1.11.0-d7h4ysd' could not be loaded.` Spack v1.2.0
  (spack/spack#51957) made `load_module` raise unless `module load`
  changed `LOADEDMODULES`; the prologue had already loaded that module
  *last*, and lmod makes re-loading it a no-op (exit 0, `module is-loaded`
  true), whereas re-loading an earlier module "works" only because lmod
  moves it to the end. Verified on the login node with `spack python`
  (`modtest.py`). Upstream fixed it in spack/spack#52752 (2026-07-22, two
  days after v1.2.2, labelled v1.2.3). mache now has
  `mache/spack/patches/*.patch`, applied with `git apply` right after the
  Spack checkout is reset and listed under `spack: patches:` in the
  provenance file; the one patch is the upstream commit (source + its
  test). Tests: the script applies patches between checkout and `spack
  isolate`; every patch applies to the pinned tag (files fetched from
  GitHub). The trailing-whitespace hook excludes `*.patch`. Verified by
  hand-patching `compass_spack` and re-running `spack install`:
  e3sm-scorpio 1.8.2 built, trilinos-for-albany in progress. Polaris intel
  and E3SM-Unified gnu were not affected because their externals with
  `modules:` are never last in the prologue's list (luck, not design).

- Overlay `266bc2c6` (pinned by `98838c1f`): trilinos-for-albany exposes
  `kokkos_cxx` as a property. With the module-load fix in place, compass's
  env built cmake 3.31.11, boost, e3sm-scorpio 1.8.2 and
  trilinos-for-albany (33 min), then albany failed in 3 s:
  `trilinos_for_albany/package.py:384 ... NameError: name 'spack_cxx' is not
  defined` (the 0.x `setup_dependent_package` assignment; in 1.x the build
  globals exist only for the package being built). Same change upstream
  trilinos made; nothing in the overlay reads `spec.kokkos_cxx`. Verified by
  editing the instance's overlay checkout: albany built in 10 min
  (`spack_install_only2.log`).

## Observations not tied to a test

- The Aurora oneAPI template (`aurora_intel_mpich.yaml`) has the same
  shape as the Chrysalis one had (`intel-oneapi-compilers` external with
  `modules:` only, no `prefix:`), so it probably needs the equivalent
  fix with the oneAPI root on Aurora. Not changed here: cannot be verified
  from Chrysalis.

- The Aurora template's `gcc` external says `gcc@13.3.0` but its
  `extra_attributes.compilers` paths point at `gcc-13.4.0-hgnyg4p`
  (pre-existing on `main`; not changed here).
- `spack isolate --self` prints a warning ("adding repos without an explicit
  destination will default to $SPACK_USER_CACHE_PATH or ~/.spack ... fixed
  with shared spack in v1.3"). Harmless: `repos.yaml` is written at the
  instance scope before the first spack command and `spack repo list` shows
  `[+] e3sm` then `[+] builtin`, both `v2.2`, at the expected paths.

## 1. polaris, intel/openmpi

Attempt 1 (before `3554cfb1`): pixi env, JIGSAW and the three clones fine;
`spack install` failed at concretization (see above).

Attempt 2 (`deploy_attempt2_stale_mache.log`): same failure, because
`bootstrap.py::_clone_mache_repo` keeps an existing
`deploy_tmp/build_mache/mache` clone unless `--recreate`, so the rerun
still installed mache at `f2a43396`. Worth knowing for anyone iterating on
a mache branch with `--mache-fork/--mache-branch`: remove
`deploy_tmp/build_mache` between runs (pre-existing behaviour on `main`,
not this branch's).

Attempt 3 (fresh `polaris_spack`, `deploy_tmp/build_mache` removed, mache at
`3554cfb1`; `deploy_attempt3_oneapi_prefix.log`): three clones, `spack
isolate --self`, `spack repo list` and concretization fine (9 specs;
`gcc-runtime@11.3.0` built from the `gcc@11.3.0` external, compiler-wrapper
built); `intel-oneapi-runtime` failed on the oneAPI prefix (see above).

Attempt 4 (fresh `polaris_spack`, mache at `60298238`;
`deploy_attempt4_mkl_prefix.log`): library env `spack_env_intel_openmpi`
built completely (compiler-wrapper, gcc-runtime 11.3.0, intel-oneapi-runtime,
metis, parmetis, e3sm-scorpio 2.0.3; hdf5/netcdf/pnetcdf/openmpi/cmake
external); provenance yaml has the three commits and `spack.lock` was
copied. The second build script (software env) exercised the
existing-instance path: `git fetch`, `checkout --detach`, `reset --hard`
(reverting the `include.yaml` that `spack isolate` rewrote), isolate
directory set aside and restored with no "already exists" error, both repos
`[+]`. Software env: eigen 3.4.1, zoltan, esmf 8.9.1 (19 min, oneAPI) built;
`tempestremap` failed on the MKL prefix (see above), so moab was skipped.

Attempt 5 (existing instance, mache at `d6f91d7f`; `deploy.log`): **pass**.
Doubles as the "rerun without --recreate" check: fetch/reset of the three
checkouts, `spack isolate --self` with the bootstrap store preserved (no
clingo re-download; the concretizer ran immediately), both envs
"recreating environment", every previously installed package reused
(`[+]`, same hashes, including the hand-built tempestremap), moab 5.6.0
built (2 min), activation captured, polaris installed, load script written.

Checks (fresh `env -i bash -l` shells):
- `deploy_tmp/spack/spack_env_intel_openmpi.{yaml,provenance.yaml,spack.lock,raw_activate.sh,env_before}`
  all present; provenance has spack `3e19345b`, e3sm `fada9f58`, builtin
  `d4f7c711`.
- `etc/spack/repos.yaml`: `e3sm` then `builtin`, path-based; `spack repo
  list` shows both `[+] ... v2.2`.
- `spack_env_intel_openmpi/activate.sh`: `SPACK_ROOT`, `PATH` (spack bin),
  `SPACK_ENV`, `SPACK_ENV_VIEW` literal; `ACLOCAL_PATH`, `CMAKE_PREFIX_PATH`,
  `MANPATH`, `PATH`, `PKG_CONFIG_PATH` prepends only (`${X:+:$X}` form,
  `${MANPATH:-}` for MANPATH). No `LD_LIBRARY_PATH` (polaris does not ask
  for it). Nothing assigns the capturing shell's full PATH. `polaris_software`
  has no `activate.sh` (by design; the load script only adds its view `bin`).
- Dynamic vs captured: `spack env activate spack_env_intel_openmpi` in a
  fresh shell vs sourcing `load_polaris_chrysalis_intel_openmpi.sh`: the
  view-related entries of `PATH`, `CMAKE_PREFIX_PATH`, `PKG_CONFIG_PATH` (3),
  `ACLOCAL_PATH`, `MANPATH` (2) and `SPACK_ENV` are identical and in the same
  order. Only difference: the `.` in MANPATH (fixed by `ccd7a842`).
- After sourcing the load script: `$PIO` -> view; `which python` -> pixi env;
  `spack find` works (plain executable); `ESMF_RegridWeightGen` and
  `mbtempest` -> `polaris_software` view; `which nc-config` -> the
  `netcdf-c/4.9.3-mekqsor` module (correct: polaris uses
  `use_e3sm_hdf5_netcdf = True` on Chrysalis, so netcdf is an external, not
  in the view). `ESMFMKFILE` is pixi's (esmpy), as before.
- Load script order: software view `bin` on PATH, `source .../activate.sh`,
  then the `config_machines.xml` modules (intel-oneapi-compilers, openmpi
  4.1.8, mkl, cmake, hdf5, netcdf-c/fortran, parallel-netcdf) and
  `OMPI_MCA_*`/`UCX_*` exports.
- Nothing built with the `gcc@11.3.0` fallback: every built package is
  `%c,cxx,fortran=oneapi@2025.2.0` (gcc-runtime is the only gcc-derived
  node). So the design-test-4 question ("does anything refuse oneapi?") is
  answered for polaris's specs: no.

Attempt 6 (existing instance, mache `98838c1f`, the final PR head;
`deploy.log`): **pass**. Everything reused; the build script applied the
Spack backport (recorded under `spack: patches:` in the provenance);
the recaptured `activate.sh` has no `.` in MANPATH and no "lost elements"
warning; load script checks unchanged.

## 2. E3SM-Unified, gnu/openmpi

Run as a Slurm job on a compute node (`deploy_chrysalis.sbatch` in the
clone: `-p compute`, `PIXI_CACHE_DIR` and `--spack-tmpdir` under the test
root, `--prefix .../e3sm-unified-pixi`, `--spack-path .../e3sm-unified_spack`).
Compute nodes have network access; their `/tmp` is a 15 GB tmpfs, hence
`--spack-tmpdir`.

Attempt 1 (job 1292020, `deploy_attempt1_login_prefix_bug.log`, mache
`60298238`): the Spack part **passed** on the first try. Fresh instance;
env `e3sm_unified_gnu_openmpi` concretized 10 specs with `hdf5@1.14.6`,
`netcdf-c@4.10.0`, `netcdf-fortran@4.6.2`, `parallel-netcdf@1.14.1` built
(the hdf5/netcdf externals were filtered out and the root specs kept: the
`9fe2d65a` fix, in the deploy path), `esmf@8.9.1~python` (overlay), `moab@5.6.0`
with `eigen@3.4.1` (overlay), `nco@5.3.9`, `tempestremap@2.2.0` (overlay
patch), `tempestextremes@2.4.2` (overlay-only version), `gcc-runtime@11.2.0`
from the `gcc@11.2.0` external. Build time about 50 min on one node (ESMF 16
min). The `post_spack` hook (`deploy_tmp/post_spack_hpc.sh`) got the dynamic
activation (`source .../setup-env.sh` + `spack env activate ...`) and built
`mpi4py` 4.1.1 against the view's `mpicc`; the activation was captured
afterwards.

**Incident, E3SM-Unified's own bug, not mache's.** The deploy then ran
`pixi install` and pip-installed mache 5.0.0rc1 into the *production* login
env `/lcrc/soft/climate/e3sm-unified/e3smu_1_13_0/chrysalis/pixi_login`,
wrote `test_e3sm_unified_1.13.0_chrysalis.sh` to
`/lcrc/soft/climate/e3sm-unified/` and recursed a permission update over
`e3smu_1_13_0`. Cause: `deploy/hooks.py::_get_pixi_prefixes` reads
`ctx.args.prefix`, but mache renamed the option to `--pixi-path` with dest
`pixi_path` in `56ccbd31` (3.10.0, 2026-03), so `--prefix` is ignored for
the login env and `_get_prefix_root` falls back to `[e3sm_unified] base_path`.
Any non-release deploy with `--prefix` on a supported machine has done this
since mache 3.10. I cancelled the job at the permission step and restored
the production login env with Xylar's OK: manifest rewritten to its
original form (python 3.13, pip, setuptools, git, `mache ==3.6.1`,
`e3sm-unified ==1.13.0 nompi_*`), the 32 added dev-tool packages pruned
by `pixi install`, `mache 3.6.1` re-linked with `pixi reinstall mache`
(792 conda records, identical to the pre-incident set), the stray load
script deleted. Backup of the modified manifest/lock and package lists:
`spack-v1-test/pixi_login_backup_0708/`. `source
load_latest_e3sm_unified_chrysalis.sh` then gives `mache 3.6.1` and a
working `ncremap`. Only visible trace: today's mtimes on
`pixi_login/pixi.toml`, `pixi.lock` and the re-linked mache files. Reported as
https://github.com/E3SM-Project/e3sm-unified/issues/156.

Attempt 2 (job 1292066, `deploy.log`, mache `ccd7a842`, hooks patched
locally and uncommitted: `pixi_path` honoured, prefix root redirected to
`.../e3sm-unified-shared`): **pass**. Existing instance reused (fetch/reset,
isolate preserved, every package `[+]`), mpi4py hook, capture, load script;
nothing written under `/lcrc/soft`.

Checks:
- View has no `bin/python`; `ESMF_RegridWeightGen`, `mbtempest`,
  `GenerateOfflineMap`, `DetectNodes`, `ncremap`, `ncks` in the view.
- `activate.sh`: literal exports for `SPACK_ENV`, `SPACK_ENV_VIEW`,
  `ESMFMKFILE` (view's `lib/esmf.mk`), `GSL_ROOT_DIR`, `HDF5_PLUGIN_PATH`,
  `MPIFC`, `UDUNITS2_XML_PATH`; prepends only for `PATH`, `CMAKE_PREFIX_PATH`,
  `CPATH`, `ACLOCAL_PATH`, `MANPATH`, `PKG_CONFIG_PATH`. `/usr`-prefixed
  externals contribute `/usr/share/man`, `/usr/share/aclocal`,
  `/usr/share/pkgconfig`, `/usr/lib64/pkgconfig`, as expected. No `.` in
  MANPATH (captured with `ccd7a842`). `activate.csh` has the `setenv` forms.
- Load script on a compute node (`srun`): compute pixi env active,
  `ncremap`/`ESMF_RegridWeightGen`/`mbtempest`/`GenerateOfflineMap` from the
  view, `import mpi4py.MPI` reports Open MPI 4.1.6, `spack find` works.
  `ESMFMKFILE` is pixi's `esmf.mk`: E3SM-Unified's own `load.sh` snippet
  overrides it on purpose ("for e3sm_diags"), same as production 1.13.0.
- Load script on the login node: login pixi env, `ncremap` from pixi.

### E3SM-Unified PRs tested on request

- PR 157 (`0f509b9`, fix for #156): **pass**. Job 1292122, `--prefix` only
  (no `--spack-path`), mache `30f97891`. Compute/login/Spack at `<prefix>`,
  `<prefix>_login`, `<prefix>_spack`; no `/lcrc/soft` path in the log;
  "Skipping shared load-script aliases" logged; full hpc build from a fresh
  instance (the build script applied the Spack backport, listed under
  `spack: patches:` in the provenance); load script on a compute node OK.
  Comment: https://github.com/E3SM-Project/e3sm-unified/pull/157#issuecomment-5761467157
- PR 152 (`453733a`, group-writable `e3smu_latest_for_nco`): **cannot be
  deployed yet**. Tested in a worktree with `--release --package-mpi nompi`
  and `[deploy] prefix_root` redirected to the test root via a local
  `machines.path` override (works; nothing under `/lcrc/soft`). The conda
  package `e3sm-unified 1.13.0` (newest on conda-forge) pins `mache
  ==3.6.1`, the PR pins 3.7.0, and mache requires `pins.cfg` and
  `cli_spec.json` to agree, so the pixi solve fails. Needs an e3sm-unified
  package built against mache >= 3.7.0.
  Comment: https://github.com/E3SM-Project/e3sm-unified/pull/152#issuecomment-5761281922

## 3. compass, gnu/openmpi with Albany

Run as Slurm jobs on compute nodes (`deploy_chrysalis.sbatch` in the
clone). compass `main` at `653af434`.

Attempt 1 (job 1292059, `deploy_attempt1_jigsaw_solve.log`): compass's own
pixi problem, as predicted in the notes but one step later than on the
laptop: `pixi install` succeeded, then `pixi add jigsawpy=1.1.0.*` (the
locally built package, which needs `libnetcdf 4.10.1`) could not be
solved. Not this branch's problem. To keep testing, `jigsaw.enabled` was
set to `false` in the clone's `deploy/config.yaml.j2` (local edit, not
committed).

Attempt 2 (job 1292068, `deploy_attempt2_module_load.log`, mache
`ccd7a842`): pixi env built; env `compass_albany_gnu_openmpi` concretized
(9 specs: `albany@compass-2026-03-21+mpas~py+unit_tests`,
`trilinos-for-albany@compass-2026-02-06`, `e3sm-scorpio@1.8.2`,
`cmake@3.31.11` built because compass asks for `cmake@3.27.0:`; hdf5,
netcdf-c, netcdf-fortran, parallel-netcdf and openmpi 4.1.6 external from
the E3SM modules); boost and cmake built; then every package with a
modules-only external in its DAG failed in `load_external_modules` (the
Spack 1.2 regression, see the fixes section). Diagnosed and fixed by hand
on the instance; `spack install` continued in jobs 1292086 and 1292115
(`spack_install_only*.log`): trilinos-for-albany 33 min, then the
`spack_cxx` recipe failure, then albany 10 min after the overlay fix.

Attempt 3 (job 1292126, `deploy.log`, mache `98838c1f`, existing instance):
**pass**. `git reset --hard` discarded the hand edits, the build script
applied `spack-52752-load-module-already-loaded.patch`, the overlay was
fetched and reset to the new pin `266bc2c6`; trilinos-for-albany rebuilt
(new hash from the recipe change, 18 min), albany built (8.5 min); the
software env `compass_software` used the *intel* template (compass's
`software_compiler = intel` on Chrysalis): esmf 12.5 min and moab built
with oneAPI in a fresh instance, a second confirmation of the three intel
template fixes. compass's `post_spack` hook ran (`spack config add
modules:prefix_inspections:...` landed in the env's `spack.yaml`), the
activation was captured afterwards, load script written.

Checks (fresh `env -i bash -l` shell on the login node):
- `compass_albany_gnu_openmpi/activate.sh` (16 lines) prepends the view's
  `lib` and `lib64` to `LD_LIBRARY_PATH` (plus the curl and zlib
  externals' `lib`), the usual path-likes, literals for `SPACK_ENV` etc.;
  no `.` in MANPATH; no "lost elements" warning.
- After sourcing `load_compass_chrysalis_gnu_openmpi.sh`: `Albany` and
  `AlbanyAnalysis` from the view; `Albany` runs (prints its banner, exit
  0) with the captured `LD_LIBRARY_PATH`; `$PIO` -> view (`libpioc.a`,
  `libpiof.a`); `python` -> pixi env; `spack find` works;
  `ESMF_RegridWeightGen` and `mbtempest` -> `compass_software` view.
- Provenance yaml lists the three commits and `spack: patches:`.

## 4. polaris gnu/openmpi as a library env (the "if time allows" item)

Not run. gnu/openmpi on Chrysalis was exercised by E3SM-Unified (hdf5/netcdf
built, externals filtered) and compass (hdf5/netcdf as modules-only
externals, the harder case), and intel/openmpi by polaris (both envs) and
compass's software env, so a polaris gnu run would add nothing new.
