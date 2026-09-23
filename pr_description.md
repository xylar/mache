This PR moves `mache` from the `E3SM-Project/spack` fork (Spack 0.23 plus E3SM packages on a `spack_for_mache_<version>` branch) to unmodified Spack 1.x. Environments are built from three pinned sources: a `spack/spack` release, a `spack/spack-packages` release and the new [E3SM-Project/e3sm-spack-packages](https://github.com/E3SM-Project/e3sm-spack-packages) overlay, which carries only the E3SM delta (Albany, Trilinos-for-Albany, and subclasses of upstream recipes for newer versions and fixes). The design is in `docs/design/spack_v1.md`; Andrew Nolan's #281 was the starting point. This is a breaking change for Spack instances and templates, so the version is 5.0.0rc1.

What changes for downstream repositories:

- `mache/spack/pins.yaml` pins the three sources. Overrides (a `tag`, `commit` or `branch` per repository) come from `pins=` in `make_spack_env`, `spack.pins` in `deploy/config.yaml.j2`, a `pre_spack` hook, or `--spack-pins <file>`.
- A new `spack_path` is needed per major `mache` version; a checkout of Spack 0.x is refused rather than converted. The instance is isolated from `~/.spack` with `spack isolate --self`.
- Load scripts source a captured `activate.sh` instead of running `spack env activate` (`spack.activation: dynamic` restores the old behaviour). `post_spack` hooks still receive the dynamic form in `spack_result['activation']`.
- Templates use the Spack 1.x compiler model (compiler externals with `extra_attributes.compilers`, a `mache` toolchain selected through `packages:all:require`); `%{{ compiler }}` is no longer appended to any spec, so downstream `deploy/spack/*.yaml` overrides need the same migration and `mache` rejects un-migrated ones. The three Intel classic templates (`compy_intel_impi`, `chrysalis_intel-classic_*`) are retired because those compilers have no package in `spack-packages`.
- `spack.build_jobs` (and `build_jobs=`) pass through to `spack install -j`.
- `mache/spack/patches/*.patch` are applied to the pinned Spack checkout and recorded in the provenance file. The one patch is a backport of [spack/spack#52752](https://github.com/spack/spack/pull/52752), without which an external whose module is already loaded fails to build; #495 tracks dropping it.
- Deploys work on compute nodes without outbound ssh: the bootstrap clones `mache` over https, GitHub ssh URLs are rewritten to https for every git command a deploy runs (so downstream ssh submodules resolve), and the caller's proxy variables reach the Spack build script.
- A pre-existing bug found while testing: with `use_e3sm_hdf5_netcdf = False` or `exclude_packages: [cmake]`, the hdf5/netcdf/cmake specs a downstream package requested were dropped along with the template's own roots. Requested specs are now kept.
- In the overlay, `esmf` removes upstream's run-time `python`/`py-pyyaml` dependencies by editing the class's dependency table after subclassing (directives cannot be un-inherited); a full recipe copy is the fallback if that proves fragile.

Before merging: `e3sm-spack-packages` has two configure fixes on `main` that are not in the pinned tag `v2026.06.0` (netcdf-c's `MPI_Comm_f2c` detection with MPICH-based MPIs, and parallel-netcdf's `-fvisibility=hidden` for Fortran). Tag `v2026.06.1` and bump the pin so E3SM-Unified testing runs against them.

Fixes #496

Checklist
- [ ] `e3sm-spack-packages` tagged and `mache/spack/pins.yaml` bumped to that tag
- [x] User's Guide has been updated if needed
- [x] Developer's Guide has been updated if needed
- [x] API documentation lists any new or modified class, method, or function
- [x] Documentation [builds](https://docs.e3sm.org/mache/main/developers_guide/building_docs.html) cleanly and changes look as expected
- [x] Tests pass and new features are covered by tests
- [x] PR description includes a summary and any relevant issue references
- [x] `Testing` comment, if appropriate, in the PR documents testing used to verify the changes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
