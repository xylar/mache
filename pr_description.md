This PR moves `mache` from the `E3SM-Project/spack` fork (Spack 0.23 plus E3SM packages on a `spack_for_mache_<version>` branch) to unmodified Spack 1.x. Environments are built from three pinned sources: a `spack/spack` release, a `spack/spack-packages` release and the new [E3SM-Project/e3sm-spack-packages](https://github.com/E3SM-Project/e3sm-spack-packages) overlay, which carries only the E3SM delta (Albany, Trilinos-for-Albany, and subclasses of upstream recipes for newer versions and fixes). The design is in the `spack_v1_design.md` draft that accompanies this branch; Andrew Nolan's #281 was the starting point. This is a breaking change for Spack instances and templates, so the version is 5.0.0rc1.

For reviewers to decide:

- Whether `spack_v1_design.md` should be committed under `docs/design/` with this PR.
- The overlay is pinned by commit until it is tagged; the first tag (`v2026.06.0`) and the switch to a tag pin should happen before 5.0.0 is released.

What changes for downstream repositories:

- `mache/spack/pins.yaml` pins the three sources. Overrides (a `tag`, `commit` or `branch` per repository) come from `pins=` in `make_spack_env`, `spack.pins` in `deploy/config.yaml.j2`, a `pre_spack` hook, or `--spack-pins <file>`.
- A new `spack_path` is needed per major `mache` version; a checkout of Spack 0.x is refused rather than converted. The instance is isolated from `~/.spack` with `spack isolate --self`.
- Load scripts source a captured `activate.sh` instead of running `spack env activate` (`spack.activation: dynamic` restores the old behaviour). `post_spack` hooks still receive the dynamic form in `spack_result['activation']`.
- Templates use the Spack 1.x compiler model (compiler externals with `extra_attributes.compilers`, a `mache` toolchain selected through `packages:all:require`); `%{{ compiler }}` is no longer appended to any spec, so downstream `deploy/spack/*.yaml` overrides need the same migration and `mache` rejects un-migrated ones. The three Intel classic templates (`compy_intel_impi`, `chrysalis_intel-classic_*`) are retired because those compilers have no package in `spack-packages`.
- `spack.build_jobs` (and `build_jobs=`) pass through to `spack install -j`.
- A pre-existing bug found while testing: with `use_e3sm_hdf5_netcdf = False` or `exclude_packages: [cmake]`, the hdf5/netcdf/cmake specs a downstream package requested were dropped along with the template's own roots. Requested specs are now kept.
- In the overlay, `esmf` removes upstream's run-time `python`/`py-pyyaml` dependencies by editing the class's dependency table after subclassing (directives cannot be un-inherited); a full recipe copy is the fallback if that proves fragile.

Checklist
- [x] User's Guide has been updated if needed
- [x] Developer's Guide has been updated if needed
- [x] API documentation lists any new or modified class, method, or function
- [ ] Documentation [builds](https://docs.e3sm.org/mache/main/developers_guide/building_docs.html) cleanly and changes look as expected
- [x] Tests pass and new features are covered by tests
- [x] PR description includes a summary and any relevant issue references
- [ ] `Testing` comment, if appropriate, in the PR documents testing used to verify the changes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
