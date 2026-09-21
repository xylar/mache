# Aurora testing of mache's Spack 1.x branch

Written for an agent on Aurora. Dense on purpose. Read `chrysalis_test.md`
(ground rules, the check list per test) and `chrysalis_results.md` (what
went wrong on Chrysalis and how it was fixed) first; `handoff.md` §§1–2,
10–12 and `spack_v1_design.md` for the spec. All on this throwaway branch
(`spack-v1-design-notes`); the code under test is branch `spack-v1-design`
of `xylar/mache`, PR https://github.com/E3SM-Project/mache/pull/492.

## Ground rules (differences from Chrysalis)

- Same rules as `chrysalis_test.md`: fixes to mache go on the PR branch
  with tests and pre-commit, pushed to `xylar/mache`; overlay fixes to
  `E3SM-Project/e3sm-spack-packages@main` and the SHA into
  `mache/spack/pins.yaml`; everything else into `aurora_results.md` on this
  notes branch. Fresh `spack_path` per test.
- Suggested root: `/lus/flare/projects/E3SM_Dec/$USER/spack-v1-test/`
  (polaris's Aurora data lives under `E3SM_Dec`); never the shared
  `/lus/flare/projects/E3SM_Dec/soft/polaris/aurora/...` or
  `/lus/flare/projects/E3SMinput/soft/e3sm-unified`.
- Aurora is PBS, not Slurm. Long builds (ESMF, MOAB) go in a `qsub -I` or
  batch job; check first whether compute nodes reach GitHub and conda-forge
  (`curl -sI https://github.com`; ALCF documents `HTTP_PROXY`/`HTTPS_PROXY`
  for compute nodes). If they do not, build on the login node under
  `nohup`.
- Deploys reuse `deploy_tmp/build_mache/mache` unless `--recreate`: delete
  that directory between runs so a new mache commit is picked up.
- The build script runs under `env -i bash -l`, so `TMPDIR` exported in a
  job script is lost; E3SM-Unified has `--spack-tmpdir`, polaris does not
  (its stages go to Spack's `$tempdir`, i.e. `/tmp`).
- E3SM-Unified `main` before PR 157 writes into the production login env
  and `base_path` when given `--prefix` (e3sm-unified#156). Check out PR
  157 (`git fetch origin pull/157/head:pr-157`) before any E3SM-Unified
  deploy, or skip test 3.

## What is expected to be wrong in `aurora_intel_mpich.yaml`

The template was migrated mechanically and never run.
`aurora_intelgpu_mpich.yaml` is a symlink to it, so one run covers both.
The Chrysalis intel template needed three fixes; two of them apply here.

1. `intel-oneapi-compilers` external has `modules: [oneapi/release/2025.3.1]`
   and no `prefix:`. Spack infers the prefix from the module, which lands
   inside `compiler/<version>/`, and the oneAPI build system then appends
   `compiler/2025.3` again and fails to source `env/vars.sh` (first seen
   when `intel-oneapi-runtime` installs, which every oneAPI-built package
   needs). Add `prefix:` = the oneAPI root, the directory that holds
   `compiler/2025.3/` (from the compiler paths in the template that is
   probably `/opt/aurora/26.26.0/oneapi`; confirm with
   `ls <root>/compiler/2025.3/env/vars.sh`, noting the v2 layout uses the
   two-component version `2025.3`, not `2025.3.1`, so `compiler/2025.3`
   must exist, possibly via the `latest` symlink). Same for any other
   oneAPI external you find (there is no `intel-oneapi-mkl` in this
   template). See `60298238`, `d6f91d7f` on the PR branch.
2. `gcc` external says `gcc@13.3.0` with module `gcc/13.3.0`, but its
   `extra_attributes.compilers` point at
   `.../install/linux-x86_64/gcc-13.4.0-hgnyg4p/bin/`. Find out which
   version the module actually provides (`module show gcc/13.3.0`;
   `<path>/bin/gcc --version`) and make the spec, the module and the paths
   agree; add `prefix:`. It matters because `intel-oneapi-runtime` links
   against `gcc-runtime`, which Spack builds from this external (the
   `gcc-runtime` external was already removed in `3554cfb1`; do not add it
   back).
3. Both are modules-only externals. Spack 1.2's `load_module` bug (raises
   when the module was already loaded and is last in `LOADEDMODULES`) is
   patched by mache (`mache/spack/patches/`), so the prologue's module
   order should not matter; confirm the build script prints the patch
   step and the provenance yaml lists `spack: patches:`.

Compiler naming: mache calls Aurora's compilers `intel` and `intelgpu`
(`354a3d3f`), but polaris's `polaris/machines/aurora.cfg` still says
`compiler = oneapi-ifx`, `software_compiler = oneapi-ifx`, `mpi_oneapi_ifx
= mpich`. Pass `--compiler intel --mpi mpich` explicitly; if the software
env still resolves `oneapi-ifx`, edit the cfg locally (do not commit; it
is polaris's job when it moves to mache 5.0.0) and note it.

## Tests, in order

### 1. polaris, intel/mpich

```bash
git clone https://github.com/E3SM-Project/polaris.git polaris && cd polaris
./deploy.py --machine aurora --compiler intel --mpi mpich --deploy-spack \
    --spack-path /lus/flare/projects/E3SM_Dec/$USER/spack-v1-test/polaris_spack \
    --mache-fork xylar/mache --mache-branch spack-v1-design 2>&1 | tee deploy.log
```
Expect the first attempt to fail on items 1–2 above; verify each fix by
editing the env's `spack.yaml` under
`<spack_path>/var/spack/environments/<env>/` and running
`spack concretize -f` / `spack install` by hand (source the rendered
`deploy_tmp/spack/<env>.prologue.sh` and `<spack_path>/share/spack/setup-env.sh`
first, in an `env -i bash -l` shell), then commit the template change with
the tests in `tests/test_spack_templates.py` passing. Then the full check
list from `chrysalis_test.md` test 1, plus:
- every built package shows `%c,cxx,fortran=oneapi@2025.3.1`; note anything
  that fell back to gcc or refused to build with oneAPI (compass is not
  supported on Aurora, so this is the only place the Aurora template gets
  exercised).
- rerun on the existing instance (existing-instance path, bootstrap store
  reused).

### 2. polaris, intelgpu/mpich

Same as 1 with `--compiler intelgpu`, a new `--spack-path`, and no
`--recreate`; the template is identical, so this only checks the
`intelgpu` plumbing (env names, `config_machines.xml` modules for
`compiler="intelgpu"`, load script). Skip if time is short.

### 3. E3SM-Unified (only with PR 157 checked out)

```bash
git clone https://github.com/E3SM-Project/e3sm-unified.git && cd e3sm-unified
git fetch origin pull/157/head:pr-157 && git checkout pr-157
./deploy.py --machine aurora --deploy-spack \
    --prefix /lus/flare/projects/E3SM_Dec/$USER/spack-v1-test/e3sm-unified-pixi \
    --spack-tmpdir /lus/flare/projects/E3SM_Dec/$USER/spack-v1-test/spack-tmp \
    --mache-fork xylar/mache --mache-branch spack-v1-design 2>&1 | tee deploy.log
```
(`[e3sm_unified] compiler = intel` on Aurora, so this also uses the intel
template.) Before letting it run past the pixi stage, confirm every
`Running from:` path in the log is under the test root. Then the checks
from `chrysalis_test.md` test 2 (no `bin/python` in the view, `ESMFMKFILE`
literal, the mpi4py hook).

## What to report

Per test: pass/fail, log path, deviations, error text, and the final
template diff. Anything that looks like an Aurora-specific template
problem goes on the PR branch; recipe problems to the overlay. Record the
oneAPI root and the real gcc version so the next person does not have to
look them up.
