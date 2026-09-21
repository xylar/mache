## Testing

`pixi run pytest` (573 passed, 6 skipped) and pre-commit pass on the branch.

On my laptop (katara, gcc 13.3 / OpenMPI 4.1.6, Spack 1.2.2 + spack-packages v2026.06.0 + the overlay at `13c34e4`), `make_spack_env` built an environment with `parallel-netcdf@1.15.0` and `zlib-ng` into a fresh `spack_path` and again into the same one, which exercises the reset and re-isolation of an existing checkout. The captured `activate.sh` gives the same `PATH`, `PKG_CONFIG_PATH` and `SPACK_ENV` as `spack env activate --sh` in a fresh shell, and `spack find` works after sourcing it. Every packaged template renders and validates against Spack's `env` schema for all `e3sm_lapack`/`e3sm_hdf5_netcdf` combinations.

The overlay's CI (style, `spack audit`, concretization of every package and of the compass/polaris/E3SM-Unified specs) is green, and `parallel-netcdf` and `tempestremap` install from it locally.

A full polaris deployment on katara (`./deploy.py --machine katara --deploy-spack --recreate ... --mache-fork xylar/mache --mache-branch spack-v1-design`, with the migrated `deploy/spack/katara_gnu_openmpi.yaml`) built the library environment (cmake, hdf5, metis, parmetis, and the overlay's netcdf-c 4.10.1, netcdf-fortran 4.6.3, parallel-netcdf 1.15.0, e3sm-scorpio 2.0.3) and the software environment (esmf 8.9.1, moab 5.6.0); a second run without `--recreate` reused the instance. The generated `load_polaris_katara_gnu_openmpi.sh` sources the captured `activate.sh`; after sourcing it in a fresh shell, `nc-config` and `$PIO` point into the view and `python` is still pixi's. MOAB initially failed against `eigen@5.0.1`, which is fixed in the overlay.

Compass on katara does not get as far as Spack: its pixi solve fails on `main` (`mpas_tools 1.5.1` needs `libnetcdf 4.10.0`, conda-forge's `esmf 8.9.1` wants an older one), independent of this branch. Instead I ran its `post_spack` hook's `spack config add modules:prefix_inspections:...:[LD_LIBRARY_PATH]` commands against the polaris environment and re-captured: `activate.sh` then prepends the view's `lib` and `lib64` to `LD_LIBRARY_PATH`, which is what capturing after `post_spack` is for.

Not yet tested: the Chrysalis/Perlmutter deployments from the design's Testing section.

---

*Posted by Claude Code on @xylar's behalf. The testing, analysis and wording above are AI-authored; please check them accordingly.*
