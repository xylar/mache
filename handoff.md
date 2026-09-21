# Handoff: implementing Spack 1.x support in mache

Written for an agent starting fresh in this worktree. This file is not
subject to the repo's "writing for human readers" rules; it is dense on
purpose. Never commit `handoff.md` or `spack_v1_design.md` at the root of the
branch (AGENTS.md: drafts at the worktree root stay uncommitted). Ask Xylar
whether `spack_v1_design.md` should move to `docs/design/spack_v1.md` and be
committed when the branch is ready for a PR; do not decide that yourself.

## 0. Reading order and roles

1. `AGENTS.md` (repo rules: pixi, ruff, 79 cols, pre-commit, PR/testing
   comment conventions, signing posts).
2. `spack_v1_design.md` in this directory: the spec. Every normative
   statement there wins over anything here. Section anchors are referenced
   below as `design § <heading>`.
3. This file: sequencing, mechanics, verified facts, commands.

Do not re-derive facts in section 2; they were checked on 2026-09-19/21 with
`gh api`, the Spack v1.2.2 sources and the local checkouts listed below.

## 1. Environment facts (this laptop, `katara`)

| What | Where |
|------|-------|
| This worktree / branch | `/home/xylar/code/e3sm/mache/spack-v1-design`, branch `spack-v1-design` (= `main` at 4.0.0, `6d9b0669`; no commits yet) |
| Main checkout | `/home/xylar/code/e3sm/mache/mache` (branch `main`). Worktrees are siblings named after the branch: `git worktree add -b <name> /home/xylar/code/e3sm/mache/<name> main` |
| Remotes (main checkout) | `E3SM-Project/mache` (ssh), `xylar/mache` (ssh), `andrewdnolan` = `https://github.com/andrewdnolan/mache.git` (added 2026-09-19; branch `andrewdnolan/spack-v1.0.0` is PR #281) |
| Old Spack fork | `/home/xylar/code/spack/develop`: `E3SM-Project/spack` at `v0.23.1-106-gcc757747a7` (v0.23.1 + 106 E3SM commits). `git log --oneline v0.23.1..HEAD` and `git diff --stat v0.23.1..HEAD` are the source of the package inventory in the design |
| Overlay seed | `https://github.com/andrewdnolan/spack-packages`, branch `open_PR_rebase` (already v2 layout under `repos/spack_repo/e3sm/`, namespace `e3sm`, api `v2.2`, has `spack-repo-index.yaml`). Branch `e3sm-pkgs` is an older subset |
| Overlay repo | `https://github.com/E3SM-Project/e3sm-spack-packages` — exists, **empty** (no initial commit, no license) as of 2026-09-21. Maintainers: xylar, andrewdnolan |
| Downstream checkouts | E3SM-Unified `/home/xylar/code/e3sm/e3sm-unified/main`; compass `/home/xylar/code/compass/main`; polaris `/home/xylar/code/e3sm/polaris/main` (each a worktree named after its branch) |
| Toolchain on katara | `/usr/bin/gcc`, `/usr/bin/gfortran`, `/usr/bin/mpicc` (OpenMPI), `python3` 3.12 from miniforge. No `spack` installed |
| Python env | `pixi run pytest`, `pixi run pre-commit run --files <files>`, `pixi run ruff ...`, all from the worktree root. The `default` pixi env is installed under `.pixi/` of the main checkout; run `pixi install` once in this worktree if needed |
| Scratch | Use `~/scratch/spack-v1/` (create it) for the local Spack instance; never `/tmp` |
| Memory notes | `/home/xylar/.claude/projects/-home-xylar-code-e3sm-mache-mache/memory/` — session-local to Claude Code on this laptop; the content that matters is duplicated here |

Testing policy agreed with Xylar (2026-09-21): develop and verify on the
laptop first, using polaris + the `katara` machine; move to Chrysalis only
for the deployment tests in design § Testing.

## 2. Verified facts (do not re-check unless something contradicts them)

### Spack and spack-packages

- Latest releases: Spack `v1.2.2` (2026-07-20); spack-packages `v2026.06.0`
  (2026-06-22, package API v2.2, "any Spack 1.0.0 or newer is compatible").
  Earlier: `v2026.03.0`, `v2025.11.0`, `v2025.07.0`.
- Spack v1.2.2 `etc/spack/defaults/base/repos.yaml` pins `builtin` to
  `branch: releases/v2026.06` (a moving branch — hence our own pin).
- Spack 1.x config scope precedence, lowest to highest: defaults, system,
  site (`$SPACK_ROOT/etc/spack/site/`), plugin, user (`~/.spack`), **spack**
  (`$SPACK_ROOT/etc/spack/`), environment, custom, command line. Writing to
  `$SPACK_ROOT/etc/spack/repos.yaml` therefore outranks the user's config.
- `spack isolate --self` (new in 1.2.0) moves the user scope, caches, stages
  and bootstrap store under `$SPACK_ROOT`; `--undo` reverts. Idempotency is
  not documented — verify (Phase 0).
- `bin/spack` requires Python >= 3.6; the `SPACK_PYTHON` < 3.12 hack in the
  current `spack_install.bash.j2` is only for 0.23's `ast.Str` and goes.
- `lib/spack/spack/util/environment.py::EnvironmentModifications.shell_modifications`
  computes `new_env` from the calling process's environment and emits
  `export NAME=<full new value>;` (shlex-quoted) for each changed variable;
  `MANPATH` gets a trailing `:` appended. `spack env activate --sh` prints
  `export SPACK_ENV=<path>;`, `export SPACK_ENV_VIEW=<view>;` when a view is
  present, `alias despacktivate='spack env deactivate';`, then the
  modifications. csh variant uses `setenv`/`alias despacktivate "..."`.
- `lib/spack/spack/build_environment.py::load_external_modules` is called
  only from `setup_package` (build context). Run-time activation does not
  load external modules. Run-time modifications come from
  `spack/user_environment.py::environment_modifications_for_specs`: prefix
  inspections of the view (`modules:prefix_inspections`; default bin→PATH,
  man/share/man→MANPATH, lib/pkgconfig etc.→PKG_CONFIG_PATH, ''→CMAKE_PREFIX_PATH,
  share/aclocal→ACLOCAL_PATH) plus packages' `setup_run_environment` /
  `setup_dependent_run_environment`, plus `env_vars:` from spack.yaml.
- Compiler packages in spack-packages v2026.06.0: `gcc`, `nvhpc`, `cce`,
  `llvm-amdgpu`, `intel-oneapi-compilers` (icx/icpx/ifx; `provides("c","cxx")`,
  `provides("fortran")`), `intel-oneapi-compilers-classic` (versions 2021.1.2
  … 2021.13.1 only, mapped onto oneapi versions). **There is no `intel`
  package in any spack-packages release** (Intel 20.x) — that is why the
  three Intel-classic templates are retired (design Decision 9).
- Spack 1.x compiler externals: `packages:<compiler>:externals:[{spec, prefix
  and/or modules, extra_attributes: {compilers: {c, cxx, fortran}, flags,
  environment, extra_rpaths}}]`. The 1.0 changelog example uses `fc`; the
  docs and mache's current templates use `fortran`. Keep `fortran`.
- `%` in 1.x means "direct dependency"; `pkg %gcc +foo` applies `+foo` to gcc.
  `spack style --spec-strings <files>` reports/fixes old-style ordering.
- Toolchains: `toolchains: {name: [{spec: "%c=gcc@14", when: "%c"}, ...]}`;
  used as `pkg %name`. Docs show `packages:all:require: "%[when=%c]c=clang
  %[when=%cxx]cxx=clang"` as the explicit conditional form. Whether
  `packages:all:require: ["%mache"]` (toolchain name) is accepted is
  unverified → Phase 0.
- Cross-repo subclassing: `from spack_repo.builtin.packages.<pkg>.package
  import <Class>`; build systems from `spack_repo.builtin.build_systems.<bs>`.
  Builder lookup for a package module: Spack looks for a class named
  `<BuildSystem>Builder` in the package's own module first — unverified for a
  subclassed package → Phase 0.
- Spack 1.2 installer: concurrent builds by default, interactive TUI. Whether
  the TUI is suppressed when stdout is not a TTY is unverified → Phase 0.

### Upstream state of E3SM-relevant packages (spack-packages v2026.06.0)

`albany`: `develop` only. `trilinos-for-albany`: absent. `e3sm-scorpio`: ≤1.8.1
(fork has 1.9.0–2.0.3 + variants). `esmf`: ≤8.9.1 (fork: no python dep, NERSC/
Chicoma/Frontier netcdf special cases, oneAPI libstdc++ fix). `tempestextremes`:
2.3, 2.3.1 (fork: 2.2.2–2.4.2, CMake, two patches). `tempestremap`: ≤2.2.0
(fork: MOAB-master version, tolerance patch). `parallel-netcdf`: ≤1.14.1 (fork:
1.15.0). `netcdf-c`: ≤4.10.0 (fork: 4.10.1). Already upstream at the fork's
versions: `moab` 5.6.0+tempest, `nco` 5.3.9, `netcdf-fortran` 4.6.2, `hdf5`
1.14.6, `visit` 3.4.1. Andrew's merged upstream PRs: spack-packages #833,
#835, #853, #858, #872, #936.

### mache today (branch rebased onto `main` at 4.0.0, `6d9b0669`, on 2026-09-21; the 10 commits since `82e711b6` touched nothing under `mache/spack` or `mache/deploy/spack.py`)

- `mache/spack/env.py`: `make_spack_env(spack_path, env_name, spack_specs,
  compiler, mpi, *, machine, config_file, include_e3sm_lapack,
  include_e3sm_hdf5_netcdf, e3sm_hdf5_netcdf, yaml_template,
  exclude_packages, tmpdir, spack_mirror, custom_spack)`; renders
  `mache/spack/templates/build_spack_env.template` and runs it with
  `env -i bash -l`. Also `get_modules_env_vars_and_mpi_compilers`,
  `MPI_COMPILERS`.
- `mache/spack/script.py`: `get_spack_script(spack_path, env_name, compiler,
  mpi, shell, machine, include_e3sm_lapack, include_e3sm_hdf5_netcdf,
  load_spack_env, *, e3sm_hdf5_netcdf, exclude_packages)`. With
  `load_spack_env=True` it emits `source {spack_path}/share/spack/setup-env.{shell}`
  + `spack env activate {env_name}`, then the config_machines.xml snippet,
  then `<machine>.<shell>` / `<machine>_<compiler>_<mpi>.<shell>` template
  overrides.
- `mache/spack/shared.py`: `_get_yaml_data(machine, compiler, mpi,
  include_e3sm_lapack, e3sm_hdf5_netcdf, specs, yaml_template,
  exclude_packages)`, `_filter_yaml_data` (removes excluded root specs,
  `packages.<name>` externals, `packages.all.providers` entries),
  `PATH_LIKE_ENV_VARS`, `render_env_var`, `normalize_excluded_packages`.
- `mache/spack/list.py`: `list_machine_compiler_mpilib()` parses
  `mache/spack/templates/*.yaml` names.
- `mache/spack/templates/`: 25 `<machine>_<compiler>_<mpi>.yaml` (all with a
  legacy `compilers:` block and `packages:all:compiler`), `pm-cpu.sh`,
  `pm-gpu.sh`, `compy_gnu_openmpi.{sh,csh}`, `build_spack_env.template`.
  Compilers per template: see `grep -H "set compiler" mache/spack/templates/*.yaml`.
- `mache/deploy/spack.py`: `deploy_spack_envs`, `deploy_spack_software_env`,
  `load_existing_spack_envs`, `load_existing_spack_software_env`,
  `_install_spack_env` (renders `mache/deploy/templates/spack_install.bash.j2`
  with `branch = f'spack_for_mache_{Version(__version__).base_version}'` and
  `spack_repo = https://github.com/E3SM-Project/spack.git`),
  `_write_mache_spack_env_yaml` (honours `deploy/spack/<machine>_<compiler>_<mpi>.yaml`
  overrides in the target repo), `SpackDeployResult(compiler, mpi, env_name,
  spack_path, view_path, activation)`, `SpackSoftwareEnvResult(... path_setup)`.
- `mache/deploy/run.py`: hook order `pre_pixi`, `post_pixi`, `pre_spack`
  (l.292), spack deploy/load (l.308–326), results into
  `ctx.runtime['spack']['results']` (l.338: `'activation': result.activation`),
  `post_spack` (l.354), `pre_publish` (l.382), `post_publish` (l.419). The
  load template `mache/deploy/templates/load.sh.j2` embeds `spack_activation`
  at l.264–269 and exports `MACHE_DEPLOY_SPACK_LIBRARY_VIEW`.
- `mache/deploy/templates/cli_spec.json.j2` has `--deploy-spack`,
  `--no-spack`, `--spack-path`; `config.yaml.j2.j2` `spack:` section keys:
  `deploy, supported, software{supported, env_name}, spack_path,
  env_name_prefix, specs_template, exclude_packages, tmpdir, mirror,
  custom_spack`.
- Tests: `tests/test_deploy_spack.py` (uses `get_spack_script`, template
  filtering), `tests/test_spack_config_machines.py`, `tests/target_machines_dir/`.
- Docs to update: `docs/users_guide/spack/build.md`,
  `docs/developers_guide/spack.md`, `docs/users_guide/deploy.md`,
  `docs/developers_guide/deploy.md`, `docs/developers_guide/api.md`,
  `docs/design/mache_deploy.md` (spack paragraphs).
- Version convention for pre-releases: `__version_info__ = (3, 3, 0)` with
  `__version__ = '3.3.0rc1'` overriding the join (see `git show 3.3.0rc1:mache/version.py`).

### Downstream (checked 2026-09-19 on the `main` worktrees above)

- All three deploy via `mache deploy`. None passes `yaml_template`. No
  `deploy/spack.yaml.j2` spec contains `%`.
- compass and polaris ship an identical 0.x-style
  `deploy/spack/katara_gnu_openmpi.yaml` (`gcc@13.3.0`, `openmpi@4.1.6`,
  `prefix: /usr`, `compilers:` block, `packages:all:compiler`,
  `%{{ compiler }}` on specs). E3SM-Unified ships none.
- compass `deploy/hooks.py::_set_ld_library_path_for_spack_env` (a
  `post_spack` step) sources `setup-env.sh`, activates the env and runs
  `spack config add modules:prefix_inspections:lib:[LD_LIBRARY_PATH]` and
  `...lib64:[LD_LIBRARY_PATH]` → capture must run after `post_spack`.
- E3SM-Unified `deploy/hooks.py::post_spack` (l.224–) appends
  `spack_result['activation']` to a script and pip-installs `mpi4py` against
  the view → hooks must keep receiving the *dynamic* activation string
  (design Decision 14).
- polaris `polaris/machines/katara.cfg`: `[deploy] compiler = gnu`,
  `software_compiler = gnu`, `mpi_gnu = openmpi`,
  `spack = /home/xylar/data/polaris/spack`, `use_e3sm_hdf5_netcdf = False`;
  `[parallel] system = single_node`, 8 cores. polaris `deploy.py` flags:
  `--machine --pixi --prefix --compiler --mpi --deploy-spack --no-spack
  --spack-path --recreate --mache-version --python --mache-fork
  --mache-branch --quiet --bootstrap-only`.

## 3. Phase 0 — local Spack 1.2.2 and the three verifications

Goal: answer the design's "verify during implementation" items before
writing code that depends on them. ~1 hour. Record outcomes in section 7 of
this file.

```bash
mkdir -p ~/scratch/spack-v1 && cd ~/scratch/spack-v1
git clone --branch v1.2.2 https://github.com/spack/spack.git instance
git clone --branch v2026.06.0 https://github.com/spack/spack-packages.git \
    instance/var/spack/package_repos/builtin
cat > instance/etc/spack/repos.yaml <<YAML
repos:
  builtin: $PWD/instance/var/spack/package_repos/builtin/repos/spack_repo/builtin
YAML
source instance/share/spack/setup-env.sh
spack isolate --self          # run twice; second run must be a no-op or clean error
spack config scopes           # confirm user scope now under $SPACK_ROOT
spack repo list               # builtin must show [+]
spack compiler find           # registers /usr/bin/gcc@13.3.0 as an external in packages.yaml
spack spec zlib-ng            # forces clingo bootstrap; needs network once
```

V1 — toolchain name inside `packages:all:require`:

```bash
mkdir -p ~/scratch/spack-v1/v1 && cat > ~/scratch/spack-v1/v1/spack.yaml <<'YAML'
spack:
  specs: [zlib-ng, hdf5~mpi]
  concretizer: {unify: true}
  toolchains:
    mache:
    - {spec: "%c=gcc@13.3.0", when: "%c"}
    - {spec: "%cxx=gcc@13.3.0", when: "%cxx"}
    - {spec: "%fortran=gcc@13.3.0", when: "%fortran"}
  packages:
    all:
      require: ["%mache"]
YAML
spack -e ~/scratch/spack-v1/v1 concretize -f && spack -e ~/scratch/spack-v1/v1 spec -l | grep -E "hdf5|zlib-ng"
```
Pass: concretizes; `hdf5` shows `%c,cxx,fortran=gcc@13.3.0`. Fail: replace
`require` with the explicit form from design § Environment templates and
retest. Also test that a package with no language deps (add `py-pip` or a
`bundle`) still concretizes under the requirement.

V2 — captured activation content:

```bash
spack -e ~/scratch/spack-v1/v1 install
env -0 > ~/scratch/spack-v1/env_before
spack env activate --sh ~/scratch/spack-v1/v1 > ~/scratch/spack-v1/raw_activate.sh
spack env activate --csh ~/scratch/spack-v1/v1 > ~/scratch/spack-v1/raw_activate.csh
cat ~/scratch/spack-v1/raw_activate.sh
```
Record: the exact variable set, quoting style, whether `PATH` carries the
full old value (expected yes), the `MANPATH` trailing colon, the alias line.
Keep these two files: they become the fixture for `tests/test_spack_activation.py`.

V3 — subclass + builder override across repos:

```bash
spack repo create ~/scratch/spack-v1/e3sm_test e3sm     # creates spack_repo/e3sm
mkdir -p ~/scratch/spack-v1/e3sm_test/spack_repo/e3sm/packages/zlib_ng
cat > ~/scratch/spack-v1/e3sm_test/spack_repo/e3sm/packages/zlib_ng/package.py <<'PY'
from spack_repo.builtin.packages.zlib_ng.package import ZlibNg as BuiltinZlibNg
from spack_repo.builtin.packages.zlib_ng.package import AutotoolsBuilder as BuiltinAutotoolsBuilder  # adjust to the real builder class name(s) in the builtin file
from spack.package import *

class ZlibNg(BuiltinZlibNg):
    variant("e3sm_marker", default=True, description="overlay marker")

class AutotoolsBuilder(BuiltinAutotoolsBuilder):
    def setup_build_environment(self, env):
        super().setup_build_environment(env)
        env.set("E3SM_OVERLAY_MARKER", "1")
PY
spack repo add --scope site ~/scratch/spack-v1/e3sm_test/spack_repo/e3sm   # then ensure e3sm precedes builtin in `spack repo list`
spack spec -N zlib-ng | head -3            # must show e3sm.zlib-ng and +e3sm_marker
spack build-env zlib-ng -- printenv E3SM_OVERLAY_MARKER   # must print 1
```
Pass: both. Fail on the builder part: fall back to overriding at the package
level (`setup_build_environment` on the package class) and note it in the
design § The e3sm package repository.

V4 — installer output in a log: `spack -e ~/scratch/spack-v1/v1 install --fresh 2>&1 | cat | head`
(with a fresh spec) must be plain text, no TUI escape sequences. If not, find
the flag/config in `spack install --help` (`config:installer`, 1.2 changelog
mentions `spack -c config:installer:...`) and record it.

## 4. Phase 1 — seed `E3SM-Project/e3sm-spack-packages`

Clone the empty repo, then, in one initial commit set:

1. `LICENSE`: copy `/home/xylar/code/e3sm/mache/mache/LICENSE` (BSD 3-Clause,
   E3SM Project) verbatim.
2. `spack-repo-index.yaml`: `repo_index: {paths: [repos/spack_repo/e3sm]}`.
3. `repos/spack_repo/e3sm/repo.yaml`: `repo: {namespace: e3sm, api: v2.2}`.
4. Packages from `andrewdnolan/spack-packages@open_PR_rebase`
   (`gh api repos/andrewdnolan/spack-packages/contents/<path>?ref=open_PR_rebase --jq .content | base64 -d`
   or clone it). Per package:

   | Package dir | Action |
   |-------------|--------|
   | `albany/` | keep as full package (E3SM-only). Diff against the fork's `var/spack/repos/builtin/packages/albany/package.py` at `/home/xylar/code/spack/develop` for anything newer than Andrew's copy (fork commits after 2025-08: `41dbaf0605` compass-2026-03-21 tag, `55092424fd` new tags, `7d0fe9c1b2` uvm fix) and port them |
   | `trilinos_for_albany/` + 3 patches | keep as full package; port `bd890a1c09` (VOTD build fix) and `7d0fe9c1b2` from the fork if missing |
   | `esmf/` + 4 patches | **rewrite as subclass** of `spack_repo.builtin.packages.esmf.package.Esmf`; carry only: dropping `python`/`py-pyyaml` run deps (override via `conflicts`/`depends_on` cannot remove — if removal is impossible by subclassing, keep esmf as a full copy and say so in README), the NetCDF handling on `NERSC_HOST=perlmutter`/Chicoma/Frontier, and the oneAPI `ESMF_F90LINKPATHS` fix (fork commit `44d70b5dea`) — all inside a `MakefileBuilder` subclass per V3 |
   | `moab/` + patch | drop (upstream 5.6.0 has tempest) unless the patch is still needed; check `tools-492.patch` against upstream |
   | `parallel_netcdf/` | subclass adding `version("1.15.0", sha256=...)` from the fork (`be6afa61e7`) |
   | `tempestextremes/` | subclass adding 2.4.1, 2.4.2 (+ patches `system_2.2.2.patch`, `system_2.2.3.patch` only if those versions are kept) from fork `e7f687b62b`; open upstream PR too |
   | `tempestremap/` + patch | subclass: MOAB-master version + `grid_elements_tolerance.patch` |
   | new `e3sm_scorpio/` | subclass of builtin adding 1.8.2–2.0.3 versions, the three variants and the cce module fix from the fork (`8fb3bbf57c`, `19cedc2e01`, `a79bbe4da9`, `fbb20b0cd8`, `cc757747a7`); open upstream PR |
   | new `netcdf_c/` | subclass adding 4.10.1 (`3c789b07f4`); open upstream PR |
   | `superlu` | only if `albany`/`trilinos-for-albany` need `BUILD_SHARED_LIBS=ON` (fork `018f652e10`); subclass |

   Every package: `maintainers("xylar", "andrewdnolan")` (+ Albany owners on
   albany/trilinos-for-albany); files copied from upstream keep the
   `SPDX-License-Identifier: (Apache-2.0 OR MIT)` header; new files get a
   BSD-3 header. Directory names with underscores. Imports only from
   `spack.package` and `spack_repo.builtin.*`.
5. `README.md`: purpose, the license statement (design § Repository setup),
   one line per package with reason + upstream PR link, "tested against"
   derived from `ci/versions.yaml`.
6. `ci/versions.yaml`: `[{spack: v1.2.2, builtin: v2026.06.0}]`.
   `ci/specs.txt`: the union of the three downstream `spack.yaml.j2` specs
   with pins substituted (read the `deploy/pins.cfg` in each checkout).
7. `.github/workflows/ci.yaml`: jobs `style`, `concretize`, `install` per
   design § Continuous integration. Concretize job sketch: checkout; clone
   spack at `${{ matrix.spack }}`; `spack repo set --destination ... builtin`
   + `spack repo update --tag ${{ matrix.builtin }} builtin` (or clone + path
   entry as in Phase 0); `spack repo add --scope site $GITHUB_WORKSPACE/repos/spack_repo/e3sm`;
   `spack compiler find`; cache `~/.spack/bootstrap` (or the isolated path)
   with `actions/cache`; loop `spack spec -N e3sm.<pkg>` over
   `repos/spack_repo/e3sm/packages/*` and `spack spec -N "<line>"` over
   `ci/specs.txt`.
8. Verify locally against the Phase 0 instance: register the checkout with
   `spack repo add`, `spack spec -N` every package, `spack install
   parallel-netcdf` and `tempestremap`.
9. Push `main`. No tag yet (design § Repository setup). Note the commit SHA
   for `pins.yaml`.

## 5. Phase 2 — pins, shared install template, build flow (mache)

Files, in order:

1. `mache/version.py`: `__version_info__ = (5, 0, 0)`, `__version__ = '5.0.0rc1'`.
2. `mache/spack/pins.yaml` (new; add `include mache/spack/pins.yaml` to
   `MANIFEST.in`; check `pyproject.toml` package-data if used): content per
   design § Version pins with `e3sm: {git: https://github.com/E3SM-Project/e3sm-spack-packages.git, commit: <sha from Phase 1>}`.
3. `mache/spack/pins.py` (new): `load_pins(overrides=None) -> dict`,
   `_validate_ref(entry)` (exactly one of tag/commit/branch),
   `merge_pins(base, override)` (per-repo merge; an override naming a ref
   key deletes the other ref keys of that repo; cannot add/remove repos),
   `render_repos_yaml(spack_path, pins) -> str` (path-based entries in
   `pins['repos']` order, paths `{spack_path}/var/spack/package_repos/{name}/repos/spack_repo/{name}`;
   the `spack-repo-index.yaml` path for `e3sm` is `repos/spack_repo/e3sm`,
   for `builtin` `repos/spack_repo/builtin`), `checkout_command(entry, dest) -> str`
   (bash: clone if missing else fetch; `git checkout --detach <tag|commit>`
   or `git reset --hard origin/<branch>`), `release_pins_are_valid(pins, version) -> bool`
   for the guard test.
4. `mache/spack/templates/spack_install.bash.j2` (new; delete
   `mache/spack/templates/build_spack_env.template` and
   `mache/deploy/templates/spack_install.bash.j2`; update `MANIFEST.in`).
   Steps exactly as design § Build flow: prologue (also written to
   `prologue.sh`), legacy check (`python3 -c` reading
   `lib/spack/spack/__init__.py` `__version__`, exit 1 with message if < 1),
   three checkouts, write `etc/spack/repos.yaml` via heredoc, `source
   setup-env.sh`, `spack isolate --self`, `spack repo list`, mirror, env
   remove/create/activate/install (`-j {{ build_jobs }}` when set),
   `spack.lock` + `provenance.yaml` (three `git rev-parse HEAD`), `custom_spack`.
5. `mache/spack/env.py::make_spack_env`: add `pins=None`, `activation='captured'`;
   replace the template rendering; call `mache.spack.activation` after the
   script (Phase 4); update docstring.
6. `mache/deploy/spack.py::_install_spack_env`: drop `branch`/`spack_repo`;
   render the shared template with pins from
   `get_effective_spack_config` (`spack.pins`) merged with
   `ctx.args.spack_pins` (file) and `ctx.runtime['spack']['pins']`. Add
   `build_jobs` passthrough (`spack.build_jobs`).
7. `mache/deploy/templates/cli_spec.json.j2`: add `--spack-pins` (dest
   `spack_pins`, route `deploy`). `config.yaml.j2.j2`: add `pins: {}`,
   `activation: captured`, `build_jobs: null` under `spack:` with comments.
   `mache deploy update` only rewrites `deploy.py` and `cli_spec.json`, so
   downstream `config.yaml.j2` files simply lack the keys — code must default.
8. Tests: `tests/test_spack_pins.py` (merge precedence, validation, branch
   replacing tag, `render_repos_yaml` order, release guard true/false cases),
   `tests/test_spack_install_script.py` (render for tag/commit/branch; legacy
   check present; no `spack_for_mache`; no `SPACK_PYTHON`).
9. Run: `pixi run pytest tests/test_spack_pins.py tests/test_spack_install_script.py tests/test_deploy_spack.py`
   and `pixi run pre-commit run --files <changed>`.

## 6. Phase 3 — template migration

Delete: `compy_intel_impi.yaml`, `chrysalis_intel-classic_openmpi.yaml`,
`chrysalis_intel-classic_impi.yaml` (and update `docs/users_guide/` machine
lists if they enumerate these).

For each of the remaining 22 templates apply design § Environment templates
items 1–6. Mechanical checklist per file:

- [ ] remove the whole `compilers:` list; move any `environment:`, `flags:`,
      `extra_rpaths:` from it into the compiler external's `extra_attributes`
      (Perlmutter/Frontier/Aurora/Chicoma have `PKG_CONFIG_PATH` prepends
      and module lists — the module list is already on the external).
- [ ] remove `packages: all: compiler: [...]`.
- [ ] add `toolchains: mache: [...]` (or the explicit `require` form if V1
      failed) and `packages: all: require: ["%mache"]`.
- [ ] specs: drop the `- {{ compiler }}` root; `- {{ mpi }}%{{ compiler }}` →
      `- {{ mpi }}`; `"{{ spec }}%{{ compiler }}"` → `"{{ spec }}"`; same for
      hdf5/netcdf/pnetcdf roots.
- [ ] externals: strip `%{{ compiler }}` from `spec:` lines; providers:
      `mpi: [{{ mpi }}]`.
- [ ] compiler package key/spec: `intel@2025.3` → `intel-oneapi-compilers@2025.3`
      (pm-cpu_intel, pm-gpu_intel, pm-gpu_intelgpu); `oneapi@…` →
      `intel-oneapi-compilers@…` (dane, chrysalis_intel, aurora ×2); the
      `packages:` key must be the package name (`intel-oneapi-compilers`),
      not `intel`/`oneapi`.
- [ ] `extra_attributes.compilers` keys `c`, `cxx`, `fortran` present
      (already true on main; Cray templates use `cc`/`CC`/`ftn` as values).
- [ ] `concretizer:` unchanged.

Then `mache/spack/shared.py`: add `validate_spack_env_yaml(text, source)`
raising `ValueError` if top-level `compilers` or `packages.all.compiler`
exists; call it from `_get_yaml_data` after `_filter_yaml_data` (covers
downstream overrides and `yaml_template`). `_filter_yaml_data` needs no
change for toolchains. Also remove `%{{ compiler }}` appending anywhere in
Python (there is none; the appending lives only in the templates).

Tests: extend `tests/test_deploy_spack.py` or add `tests/test_spack_templates.py`:
parametrize over `list_machine_compiler_mpilib()`, render with
`_get_yaml_data(..., specs=['zlib-ng'], ...)`, `yaml.safe_load`, assert
`'compilers' not in data['spack']`, `'compiler' not in data['spack']['packages']['all']`,
toolchain present, `require` present, no `%` in any root spec, and that
`exclude_packages=['hdf5_netcdf']` still removes the four packages.

Migrate compass/polaris `deploy/spack/katara_gnu_openmpi.yaml` the same way
(needs `extra_attributes.compilers: {c: /usr/bin/gcc, cxx: /usr/bin/g++,
fortran: /usr/bin/gfortran}`; verify `gcc --version` = 13.3.0 on katara);
keep it uncommitted in those checkouts until their own PRs.

## 7. Phase 4 — captured activation

1. `mache/spack/activation.py` (new):
   - `capture_activation(spack_path, env_name, prologue_path, work_dir, log_filename=None, quiet=True)`:
     runs the `env -i bash -l -c '...'` command from design § Capture step
     (env dir is `{spack_path}/var/spack/environments/{env_name}`; use
     `spack env activate --sh {env_name}` — managed env by name — after
     `source setup-env.sh`), writes `<work_dir>/spack/<env>.env_before` and
     `<env>.raw_activate.sh`, returns their paths.
   - `parse_raw_activation(text) -> list[tuple[str, str|None]]`: `shlex.split`
     per line; accept `export NAME=VALUE;`, `unset NAME;`; skip `alias`.
   - `parse_env_before(bytes) -> dict` from NUL-separated `env -0`.
   - `rewrite_modifications(mods, env_before) -> list[Modification]` where a
     Modification is `('prepend', name, [elements])` for names in
     `PATH_LIKE_ENV_VARS` ∪ {`MANPATH` handled: strip trailing empty element},
     `('set', name, value)` otherwise, `('unset', name)`. Prepend elements =
     new elements not in old, order kept; warn (logger) on elements lost.
   - `render_activation(mods, shell, spack_path) -> str`: header sets
     `SPACK_ROOT` and prepends `$SPACK_ROOT/bin` to PATH; sh uses
     `export NAME="X${NAME:+:$NAME}"`; csh uses the `if ($?NAME)` form;
     values shell-quoted.
   - `write_activation_files(spack_path, env_name, mods) -> tuple[Path, Path]`
     → `activate.sh`, `activate.csh` in the env dir.
   - `activation_source_line(spack_path, env_name, shell) -> str`.
2. `mache/spack/script.py::get_spack_script`: when `load_spack_env=True`,
   emit `activation_source_line(...)` instead of the two lines, unless a new
   kwarg `activation='dynamic'` is passed (keep the old two lines then). Keep
   ordering: activation first, then config_machines snippet, then overrides.
3. `mache/deploy/spack.py`: `deploy_spack_envs` / `load_existing_spack_envs`
   build `SpackDeployResult.activation` with `get_spack_script(...,
   activation=<effective>)`; `load_existing_spack_envs` also checks
   `activate.sh` exists when `captured` and raises with a "redeploy" message.
   Add `capture_spack_activations(ctx, results, log_filename, quiet)` that
   loops over results (library envs only) and calls the module. Effective
   setting: `spack.activation` in config → runtime override → default
   `captured`.
4. `mache/deploy/run.py`: hooks keep receiving the dynamic string (design
   § What hooks see): at l.338 put `get_spack_script(..., activation='dynamic')`
   into `ctx.runtime['spack']['results'][...]['activation']`; call
   `capture_spack_activations` after `post_spack` (l.354) and before
   `pre_publish` (l.382); the load-script `spack_activation` (l.1637 area)
   uses `result.activation` (captured form).
5. `make_spack_env`: after the build script, if `activation == 'captured'`,
   call `capture_activation` + `write_activation_files` using
   `<cwd>/spack/prologue.sh` written by the script (the legacy API writes its
   files in cwd today: `{env_name}.yaml`, `build_{env_name}.bash`).
6. Tests `tests/test_spack_activation.py`: fixtures from Phase 0 V2
   (`raw_activate.sh`, `env_before`); cases: PATH prepend with old value,
   unset baseline var, MANPATH trailing colon, literal `SPACK_ENV`/`ESMFMKFILE`
   style var, alias dropped, `unset` passthrough, csh rendering, elements lost
   → warning not error; `activation_source_line` for sh/csh.

## 8. Phase 5 — docs, cleanup, PR

- Docs listed in section 2 ("mache today"): replace every mention of
  `spack_for_mache_<version>` / `E3SM-Project/spack`; document `pins.yaml`,
  `--spack-pins`, `spack.pins`, `spack.activation`, `spack.build_jobs`, the
  retired Intel-classic templates, the `%` semantics note for downstream
  specs, and the `activate.sh` file. `docs/developers_guide/spack.md`
  "Adding Spack support for a new machine" needs the new template skeleton.
- `mache/deploy/templates/hooks.py.j2` / docs examples that show
  `spack_result['activation']`: state that it is the dynamic form.
- `pixi run pytest` (all, except `workflow_tests/test_deploy_workflow.py`),
  `pixi run pre-commit run --files $(git diff --name-only main)`.
- `pr_description.md` at the worktree root, uncommitted, per
  `.claude/skills/pr-descriptions/SKILL.md` and AGENTS.md (no hard wraps, no
  commit list, no testing in the description). Testing goes into a `Testing`
  comment per `.claude/skills/testing-comments/SKILL.md`. Commits end with
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`; PR
  body ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
  Ask before pushing or opening the PR.

## 9. Phase 6 — end-to-end on the laptop, then Chrysalis

Laptop (polaris on katara), before any HPC:

```bash
cd /home/xylar/code/e3sm/polaris/main   # or a fresh worktree of polaris main
# migrated deploy/spack/katara_gnu_openmpi.yaml in place (Phase 3)
./deploy.py --machine katara --deploy-spack --recreate \
    --spack-path ~/scratch/spack-v1/polaris_instance \
    --mache-fork xylar --mache-branch spack-v1-design   # or whatever branch name holds the implementation, pushed to xylar/mache
```
Check: `~/scratch/spack-v1/polaris_instance/etc/spack/repos.yaml` has e3sm
then builtin; `spack repo list` shows both `[+]`; the library env builds
(`e3sm-scorpio`, `parallel-netcdf`, `metis`, `parmetis` — exercises the
overlay); `activate.sh` exists in the env dir and contains only prepends for
`PATH`/`CMAKE_PREFIX_PATH`/`PKG_CONFIG_PATH`/`ACLOCAL_PATH`/`MANPATH` plus
literals; the generated `load_polaris_*.sh` sources it; `source` it in a
fresh shell and confirm `which nc-config` and `$PIO` point into the view;
compare with `spack env activate --sh` run manually. Then the compass
`LD_LIBRARY_PATH` hook path with compass on katara.

Chrysalis and Perlmutter: design § Testing items 1–4, in that order. Fresh
`spack_path` per design § Downstream migration. Claude Code may or may not
run there; the commands are the same `./deploy.py` invocations with
`--machine chrysalis` etc.

## 10. Recorded outcomes (fill in as phases complete)

- Phase 0 V1 (toolchain in `require`): **pass** (2026-09-21). `packages:all:require:
  ["%mache"]` concretizes; `hdf5~mpi` gets `%c=gcc@13.3.0`, `zlib-ng` gets
  `%c,cxx=gcc@13.3.0`, `py-pip` (no language deps) concretizes with no
  compiler. Keep the toolchain form.
- Phase 0 V2 (raw activation content): **recorded** in
  `~/scratch/spack-v1/raw_activate.{sh,csh}` + `env_before` (copied into
  `tests/spack_activation/`). Variables: `SPACK_ENV`, `SPACK_ENV_VIEW`, alias
  `despacktivate`, `ACLOCAL_PATH`, `CMAKE_PREFIX_PATH`, `MANPATH` (trailing
  `:`), `PATH` (full old value after the view's `bin`), `PKG_CONFIG_PATH`.
  Values are `shlex.quote`d (unquoted when safe). Externals with
  `prefix: /usr` contribute `/usr/share/man`, `/usr/share/aclocal`,
  `/usr/share/pkgconfig`, `/usr/lib/pkgconfig` via prefix inspections; these
  are legitimately "new" elements and the rewrite keeps them, in order.
  `MANPATH` keeps its trailing `:` when the variable was unset before.
- Phase 0 V3 (builder subclass lookup): **pass**. `e3sm.zlib-ng` subclass
  with `AutotoolsBuilder(BuiltinAutotoolsBuilder)` in the overlay module:
  `spack spec -N` shows `e3sm.zlib-ng ... +e3sm_marker`, `spack build-env
  zlib-ng -- printenv E3SM_OVERLAY_MARKER` prints `1`. Spack 1.2.2 package
  API range is (1,0)–(2,5); `api: v2.2` in `repo.yaml` is accepted.
- Phase 0 V4 (installer output non-TTY): **pass**. `spack install 2>&1 | cat`
  prints plain `[ ] <hash> pkg@ver stage (Ns)` lines, no escape sequences.
- `spack isolate --self` idempotent: **no**. Second run exits 3 with
  `Isolation destination: .../etc/spack/isolate already exists`;
  `--overwrite` deletes `etc/spack/isolate` (bootstrap store, caches, user
  scope). It also rewrites the *tracked* `etc/spack/include.yaml` (and saves
  `etc/spack/.isolate.include.yaml`), which `git reset --hard` reverts. The
  build script therefore always `git checkout --detach && git reset --hard
  <ref>` (clean tree), then moves `etc/spack/isolate` aside, runs `spack
  isolate --self`, copies the freshly written `*.yaml` into the old
  directory and moves it back, so the bootstrap store survives rebuilds.
- `spack compiler find` writes `etc/spack/isolate/packages.yaml` (user
  scope) after isolation; the build flow never runs it.
- Phase 1 overlay commit SHA pinned in `pins.yaml`: `fada9f58d9fe90571d316aff73fa35a13c43e623` (moab eigen fix; pushed to `E3SM-Project/e3sm-spack-packages@main`, 2026-09-21). Upstream `tempestremap` in v2026.06.0 lacks `depends_on("c", type="build")` (configure runs `AC_PROG_CC`); the overlay adds it. `netcdf-fortran` 4.6.3 (polaris pin) is in the overlay too. Upstream PRs for the version bumps and the tempestremap fix are still to be opened.

## 11. Gotchas

- The build script runs under `env -i bash -l`, so nothing from the pixi
  environment (including `mache` itself) is importable there; anything that
  needs Python + mache runs in the mache process before/after the script
  (that is why the activation rewrite is post-processing, not in-script).
- `git reset --hard` in the Spack checkout must not remove
  `etc/spack/repos.yaml`: spack's `.gitignore` ignores `etc/spack/*.yaml`;
  confirm on the pinned tag before relying on it (or always rewrite the file,
  which the design does anyway).
- Spack clones `builtin` into `~/.spack/package_repos/<hash>` on first use if
  `repos.yaml` still points at the git default; writing our path-based
  `builtin` entry at the `spack` scope must happen *before* the first
  `spack` invocation in the script.
- `spack env create <name> <yaml>` for a managed env: the yaml is copied to
  `var/spack/environments/<name>/spack.yaml`; `activate.sh` written there is
  deleted by `spack env remove`. Intended.
- `exclude_packages` filtering still removes `packages.all.providers.mpi`
  entries by package name; with `mpi: [{{ mpi }}]` (no `%`) the name parse
  in `_extract_spack_package_name` still works.
- `list_machine_compiler_mpilib` only looks at `.yaml` names, so deleting
  the three Intel-classic templates is enough to drop them from `mache`'s
  supported list; `MPI_COMPILERS` keeps `intel-classic`/`impi` entries on
  purpose (config_machines.xml still has them).
- Do not edit the three downstream repos' committed files as part of the
  mache PR; their changes are separate PRs after mache 5.0.0rc1 exists.
- 79-column limit applies to Python only; YAML/Jinja templates already
  exceed it (long prefixes) and ruff does not check them.

## 12. Status at end of the implementation session (2026-09-21)

Done: Phases 0–5. Branch `spack-v1-design` has 5 commits on top of `main`
(version bump; pins/install/activation; template migration; docs; the
`_filter_yaml_data` fix) and is pushed to `xylar/mache`. `pr_description.md`
and `testing_comment.md` are drafted at the worktree root (uncommitted). No
PR opened yet.

Laptop end-to-end via `make_spack_env` (yaml_template = migrated katara
override, specs `parallel-netcdf@1.15.0+cxx+fortran`, `zlib-ng`): fresh
`spack_path` and rebuild of an existing one both pass; `activate.sh` gives
the same `PATH`/`PKG_CONFIG_PATH`/`SPACK_ENV` as `spack env activate --sh`;
plain `spack find` works after sourcing it. `parallel-netcdf` and
`tempestremap` install from the overlay.

Found and fixed on the way: `_filter_yaml_data` (PR #366) dropped root specs
the caller requested for an excluded package (e.g. polaris's
`hdf5@1.14.6+cxx+fortran+hl+mpi+shared` with `use_e3sm_hdf5_netcdf = False`).

Phase 6 on the laptop: done (2026-09-21). `./deploy.py --machine katara
--deploy-spack --recreate --spack-path ~/scratch/spack-v1/polaris_instance
--mache-fork xylar/mache --mache-branch spack-v1-design` (note: `owner/repo`)
built the library env (cmake, hdf5, metis, parmetis + overlay netcdf-c
4.10.1, netcdf-fortran 4.6.3, parallel-netcdf 1.15.0, e3sm-scorpio 2.0.3)
and the software env (esmf 8.9.1 from the overlay, moab 5.6.0). `moab`
first failed against `eigen@5.0.1` (needs C++14) -> overlay `moab` subclass
pins `eigen@:3` (`fada9f5`, pinned in `pins.yaml`). A second deploy without
`--recreate` exercised the existing-instance path. `activate.sh` holds only
prepends + literals; the load script sources it; `nc-config`/`$PIO` point
into the view, python stays pixi's, `spack find` works. compass on katara
(the `LD_LIBRARY_PATH` hook) not yet run.

Still to do after that: design § Testing items 1–4 on Chrysalis/Perlmutter;
open the mache PR; upstream PRs to spack-packages for the overlay's version
bumps and the `tempestremap` `c` dependency; tag the overlay `v2026.06.0`
and switch `pins.yaml` to the tag before 5.0.0; downstream PRs (polaris,
compass, E3SM-Unified) once 5.0.0rc1 exists.
