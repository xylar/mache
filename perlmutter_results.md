# Perlmutter results for mache's Spack 1.x branch

Recorded by Claude Code on Perlmutter, 2026-09-22, following
`perlmutter_test.md`. Test root: `/global/cfs/cdirs/e3sm/xylar/spack-v1-test/`
(downstream clones `polaris/`, `e3sm-unified/`; Spack instances
`polaris_pm-cpu_spack/`, `e3sm-unified-pixi_spack/`). Deploys run on a login
node under `nohup`; compute nodes are only used for the suites.

## Facts worth recording

- The CPE has moved on since the pm templates were written: the default is
  now `cpe/26.03` (PrgEnv-gnu/8.7.0, craype/2.7.36, cray-mpich/9.1.0,
  cray-libsci/26.03.0, libfabric/2.3.1). Everything E3SM's
  `config_machines.xml` pins for pm-cpu still exists (PrgEnv-gnu/8.6.0,
  gcc-native/14, cray-libsci/25.09.0, craype-accel-host, craype/2.7.35,
  cray-mpich/9.0.1, cray-hdf5-parallel/1.14.3.7,
  cray-netcdf-hdf5parallel/4.9.2.1, cray-parallel-netcdf/1.12.3.19,
  cmake/3.30.2) and loads cleanly.
- `libfabric/1.22.0` does not: `module avail libfabric` gives `1.20.1` (a
  NERSC hotfix), `2.3.1` and `temp-workaround`. libfabric 2.3.1 still
  provides `libfabric.so.1` with the `FABRIC_1.x` symbol versions
  cray-mpich 9.0.1 needs, and it is loaded in every login shell.
- Two other prefixes in the pm templates are stale but inert, see
  "Still open".
- Login nodes reach GitHub without a proxy. `/tmp` is a 353 GB tmpfs, so
  `--spack-tmpdir` is unnecessary for login-node deploys.
- `env -i bash -l` needs `HOME` passed through (`env -i HOME=$HOME
  USER=$USER bash -l`); without it pixi cannot activate and the load
  script's version probe fails.

## Fixes committed to the PR branch

- `40579f2c` Fix libfabric for the Perlmutter templates. Two changes to
  every `pm-cpu_*`/`pm-gpu_*` template: the module is `libfabric/2.3.1`,
  and the compiler external's build environment prepends
  `/opt/cray/libfabric/2.3.1/lib64` to `LD_LIBRARY_PATH`.

  The first is what attempt 1 failed on, right after `spack env create`:
  `==> Error: Module 'libfabric/1.22.0' could not be loaded.`

  The second is the interesting half. With the version corrected, every
  package still failed its compiler check with
  `ld: warning: libfabric.so.1, needed by .../libmpichf90.so, not found`
  and undefined `fi_*@FABRIC_*` references. `clean_environment()` unsets
  `LD_LIBRARY_PATH` for builds, and because libfabric is already in
  `LOADEDMODULES` (it is loaded by default), Spack's `module load` of it
  is a no-op that restores nothing: `spack build-env metis -- printenv
  LD_LIBRARY_PATH` was empty while `LOADEDMODULES` listed
  `libfabric/2.3.1`. The Cray wrappers link MPI into every executable, so
  the link fails even for packages that have nothing to do with MPI
  (metis). Before, this worked because `libfabric/1.22.0` was not the
  loaded default, so its module load really did contribute the directory.

  Checked by hand on the instance before committing: with the prepend,
  `spack build-env e3sm-scorpio -- printenv LD_LIBRARY_PATH` is exactly
  the libfabric directory and the library env builds. `extra_rpaths:` on
  the compiler external works equally well; the prepend was chosen because
  it is what the module load used to do and it bakes nothing into the
  installed binaries. A plain `-L` does not work (`ld` does not use it for
  a transitive shared-library dependency); `CRAY_ADD_RPATH=yes` breaks the
  link in other ways (`cannot find -lpmi`).

  `pixi run pytest`: 621 passed, 6 skipped; pre-commit clean.

## 1. polaris, pm-cpu gnu/mpich

Attempt 1 (`deploy_attempt1.log`, mache `11b683be`): pixi env, JIGSAW and
the three clones fine; the Spack build script failed on the libfabric
module (above).

Attempt 2 (`deploy_attempt2.log`, mache `40579f2c`, same instance):
**pass**. Library env `spack_env_gnu_mpich` concretized 10 specs and built
`compiler-wrapper`, `gcc-runtime@14`, `metis`, `parmetis`,
`e3sm-scorpio@2.0.3` (cmake, cray-libsci, cray-mpich, hdf5, netcdf-c,
netcdf-fortran and parallel-netcdf external). Software env
`polaris_software` built eigen 3.4.1, autoconf, automake, zoltan,
tempestremap 2.2.0 (overlay patch), moab 5.6.0 and esmf 8.9.1 (38 min on a
busy login node). Everything is `%c,cxx,fortran=gcc@14`, or the subset each
package needs; nothing fell back to anything else.

**The compiler paths are the bare Cray wrappers** (`c: cc`, `cxx: CC`,
`fortran: ftn`), exactly as the template has them. Spack accepted them at
concretization, built `compiler-wrapper` and `gcc-runtime@14` from the
`gcc@14` external through them, and CMake identified the compiler as
`GNU 14.3.0` / `Cray Programming Environment 2.7.35 C`. Neither fallback
from the test plan (absolute wrapper paths, gcc-native binaries) was
needed, so the sentence in `docs/developers_guide/spack.md` stands.

Checks (fresh `env -i HOME=$HOME USER=$USER bash -l` shells):
- `deploy_tmp/spack/spack_env_gnu_mpich.{yaml,provenance.yaml,spack.lock,raw_activate.sh,env_before,prologue.sh}`
  present; provenance has spack `3e19345b` with `patches:
  spack-52752-load-module-already-loaded.patch`, e3sm `a23a0a22`, builtin
  `d4f7c711`.
- `etc/spack/repos.yaml`: `e3sm` then `builtin`, path-based; `spack repo
  list` shows both `[+] ... v2.2`.
- `spack_env_gnu_mpich/activate.sh`: literals for `SPACK_ROOT`,
  `SPACK_ENV`, `SPACK_ENV_VIEW`, `HDF5_PLUGIN_PATH` and the four `MPI*`
  compilers; prepends only (`${X:+:$X}`, `${MANPATH:-}`) for `PATH`,
  `ACLOCAL_PATH`, `CMAKE_PREFIX_PATH`, `MANPATH`, `PKG_CONFIG_PATH`. No
  `.` in `MANPATH`, no "lost elements" warning. `polaris_software` has no
  `activate.sh` (by design).
- Neither of the compiler external's build-time variables leaks into the
  captured activation: no `LD_LIBRARY_PATH` at all, and no xpmem entry in
  `PKG_CONFIG_PATH`. Both do reach the build environment (`spack build-env
  e3sm-scorpio -- printenv`), which is the point of moving them into
  `extra_attributes`.
- Dynamic vs captured: `SPACK_ENV`, `HDF5_PLUGIN_PATH` and `MPICC` are
  identical. `PATH`, `CMAKE_PREFIX_PATH`, `PKG_CONFIG_PATH` and
  `ACLOCAL_PATH` differ only in the external prefixes' own directories
  (cmake, mpich, hdf5, netcdf, pnetcdf), which the capturing shell already
  had from the prologue's modules and which the load script's own module
  loads restore. `MANPATH` differs only by the empty element the dynamic
  form carries (the `ccd7a842` fix).
- Load script order: software view `bin` on `PATH`, `source
  .../activate.sh`, then the `config_machines.xml` modules and exports,
  then the `pm-cpu.sh` override, so `NERSC_HOST=perlmutter` is set after
  the activation is sourced, as item 6 asks.
- After sourcing `load_polaris_pm-cpu_gnu_mpich.sh`: `$PIO`, `METIS_ROOT`
  and `PARMETIS_ROOT` point at the library view; `POLARIS_COMPILER=gnu`;
  `python` is the pixi env's; `nc-config` is the
  `cray-netcdf-hdf5parallel/4.9.2.1` module's (correct:
  `use_e3sm_hdf5_netcdf = True`); `ESMF_RegridWeightGen` and `mbtempest`
  are the `polaris_software` view's; `spack find` works.
- lapack/blas: `mbtempest` links `libsci_gnu.so.6` and
  `libsci_gnu_mpi.so.6` from `/opt/cray/pe/libsci/25.09.0`, so
  `cray-libsci` is the provider it should be. `ESMF_RegridWeightGen` does
  not link lapack at all (`esmf ~external-lapack`); it links cray-mpich
  9.0.1 and `libfabric.so.1` from 2.3.1, as expected.
- `concretizer: unify: when_possible` produced no duplicates: `spack find`
  in both envs lists one version of everything and the views built without
  conflicts.

Rerun on the existing instance (`deploy_rerun.log`, no `--recreate`):
**pass**. The three checkouts fetched and reset, the Spack patch
reapplied, `spack isolate --self` with the bootstrap store preserved (no
"already exists", no clingo download, the concretizer ran at once), both
envs "recreating environment" with all 18 packages `[+]` and nothing
rebuilt, activation recaptured, load script rewritten.

## 2. E3SM-Unified, pm-cpu gnu/mpich (PR 157 checked out, `0f509b9`)

`deploy.log`, mache `40579f2c`, `--prefix .../e3sm-unified-pixi
--spack-tmpdir .../spack-tmp`, fresh instance: **pass** on the first
attempt, about 75 min on a login node. Every `Running from:` path is under
the test root, "Skipping shared load-script aliases" is logged and nothing
was written under `/global/common/software/e3sm` or
`/global/cfs/cdirs/e3sm/software`. The Spack tmpdir was created and used
(the `c282988c` fix).

Env `e3sm_unified_gnu_mpich` concretized 50 specs and built esmf 8.9.1
`~python`, moab 5.6.0 with eigen 3.4.1, nco 5.3.9, tempestremap 2.2.0,
tempestextremes 2.4.2, gsl, udunits, zoltan, antlr, flex, bison and the
rest; hdf5, netcdf-c, netcdf-fortran, parallel-netcdf, cray-mpich and
cray-libsci are external (`use_e3sm_hdf5_netcdf = True`). Provenance lists
the three commits and `spack: patches:`.

Checks:
- The view has no `bin/python`; `ESMF_RegridWeightGen`, `mbtempest`,
  `GenerateOfflineMap`, `DetectNodes`, `ncremap` and `ncks` are all in it.
- `activate.sh`: literals for `SPACK_ROOT`, `SPACK_ENV`, `SPACK_ENV_VIEW`,
  `ESMFMKFILE` (the view's `lib/esmf.mk`), `GSL_ROOT_DIR`,
  `HDF5_PLUGIN_PATH`, `UDUNITS2_XML_PATH` and the four `MPI*` compilers;
  prepends only for `PATH`, `ACLOCAL_PATH`, `CMAKE_PREFIX_PATH`, `CPATH`,
  `MANPATH` and `PKG_CONFIG_PATH`.
- The `post_spack` hook (`deploy_tmp/post_spack_hpc.sh`) got the dynamic
  activation (`source .../setup-env.sh` + `spack env activate
  e3sm_unified_gnu_mpich`) and built mpi4py 4.1.1 against the view's
  `mpicc`; the activation was captured afterwards.
- Compute node (job 58747652, `check_compute.log`): the compute pixi env
  and the spack env both activate; `python` is the pixi env's and reports
  `mache 5.0.0rc1`; `ncremap`, `ESMF_RegridWeightGen`, `mbtempest` and
  `GenerateOfflineMap` come from the view; `import mpi4py.MPI` reports
  `CRAY MPICH version 9.0.1.498` and `srun -n 2` with mpi4py works;
  `spack find` works; `ncremap --version` is 5.3.9.

## 3. polaris, pm-gpu gnugpu/mpich

`polaris_pm-gpu/deploy.log`, mache `40579f2c`, fresh instance
`polaris_pm-gpu_spack` and a separate polaris clone so the pm-cpu
deployment stayed intact: **pass** on the first attempt, no deviations.

- Library env `spack_env_gnugpu_mpich` from `pm-gpu_gnugpu_mpich.yaml`,
  software env `polaris_software` from `pm-gpu_gnu_mpich.yaml` (a symlink
  to the pm-cpu gnu template), as intended. The software env's packages
  have the same hashes as the pm-cpu instance's (`esmf` `7m3g7sc`, `moab`
  `sntljqj`, `eigen` `nkry6kn`, ...) while the library env's differ, which
  is exactly the `craype-accel-nvidia80` versus `craype-accel-host`
  difference.
- `cudatoolkit/12.9` and `craype-accel-nvidia80` appear in the build
  script's and the load script's module loads.
- After sourcing `load_polaris_pm-gpu_gnugpu_mpich.sh`:
  `POLARIS_COMPILER=gnugpu`, `$PIO` is the gnugpu library view,
  `ESMF_RegridWeightGen` is the `polaris_software` view's, `python` is the
  pixi env's, `craype-accel-nvidia80` is loaded and `spack find` works.

## 5. pm-cpu intel and the nvidia templates

`pm-cpu_intel_mpich.yaml` needed two fixes (`84c6a8e2`, above): a `gcc`
external, without which the environment does not concretize at all, and
the oneAPI root as `prefix:`, the failure already seen on Chrysalis and
Aurora. Both were found by deploying polaris with `--compiler intel` into
`polaris_intel_spack` and reproduced and fixed by hand on the instance
before committing. The deploy was then rerun with the fixed template
(`polaris_intel/deploy_attempt2.log`, mache `84c6a8e2`): **pass**. The
library env is all `%oneapi@2025.3` (`intel-oneapi-runtime@2025.3` and
`gcc-runtime@14.3.0` from the two externals, then metis, parmetis,
e3sm-scorpio) and the software env builds with gnu, as `software_compiler
= gnu` asks. Sourcing `load_polaris_pm-cpu_intel_mpich.sh` gives
`POLARIS_COMPILER=intel`, `$PIO` in the intel library view,
`ESMF_RegridWeightGen` from `polaris_software`, python from pixi and a
working `spack find`; the captured activation again has no
`LD_LIBRARY_PATH` and no xpmem entry.

The nvidia templates do **not** need the same gcc external: `nvhpc`
declares the same run dependency on gcc, but nothing in these
environments pulls in an `nvhpc-runtime` the way `intel-oneapi-runtime`
pulls in `gcc-runtime`, so the solver never has to satisfy it. Checked
with `pm-gpu_nvidiagpu_mpich.yaml` rendered through mache and concretized
by hand in the pm-gpu instance: 10 specs, `nvhpc@25.9` external, no gcc
node. `metis` and `parmetis` then build with nvhpc, but
`e3sm-scorpio@2.0.3` fails in configure with `Could not find a Fortran
type for passing PIO Offsets from Fortran to C`
(`cmake/SPIOTypeUtils.cmake:172`). That is a SCORPIO/nvhpc problem rather
than a template one, and no downstream deploy uses these templates today,
so it is recorded and left alone. All of `PrgEnv-nvidia`, `nvidia/25.9`,
`cudatoolkit/12.9` and `gcc-native-mixed/14` do exist on Perlmutter.

## 4. MPAS-Ocean and Omega suites on pm-cpu gnu

Both suites were set up from the test-1 deployment with `--clean_build`
and run on two nodes in the `debug` queue. The suite that the test plan
calls `pr` is `mpaso_pr` in polaris `ca3dfa8e0`.

- MPAS-Ocean (`polaris suite -c ocean -t mpaso_pr --model mpas-ocean`, job
  58747263): the model built with `cc`/`ftn` against the library view's
  PIO and the Cray netcdf/pnetcdf modules, and the suite is **PASS: All
  passed successfully**, 21 tasks in 9:49.
- Omega (`-t omega_pr --model omega`, job 58747401): `omega.exe` built
  with `-DOMEGA_CIME_COMPILER=gnu` and `OMEGA_METIS_ROOT`/
  `OMEGA_PARMETIS_ROOT` from the library view; the suite is **PASS: All
  passed successfully**, 9:40.

So nothing in the library env, the load script or the captured activation
gets in the way of a model build or a run.

## Still open

- Both stale paths are gone (`5c9dd9fe`, on Xylar's call): the compiler
  external's xpmem `PKG_CONFIG_PATH` prepend, whose directory no longer
  exists now that `cray-xpmem.pc` lives in `/usr/lib64/pkgconfig`, and the
  `python` external, whose prefix and `python/3.9-anaconda-2021.11` module
  are both gone. Removing the external means Spack would build a python if
  something ever needed one; nothing in these environments does.
  Concretization is otherwise unchanged, though the built packages' hashes
  move, because the compiler external's `extra_attributes` are part of the
  spec. Confirmed with a full polaris pm-cpu deploy on the cleaned
  templates (`deploy_after_cleanup.log`): both envs rebuilt from the new
  hashes, exit 0, and the load-script checks above are unchanged.
- `e3sm-scorpio@2.0.3` does not configure with `nvhpc@25.9` (see test 5).
  Nothing deploys the nvidia templates today, so this is recorded rather
  than chased.
- The existing-instance rerun was exercised with polaris only, as on the
  other two machines; E3SM-Unified and the pm-gpu, intel instances were
  each built once.
