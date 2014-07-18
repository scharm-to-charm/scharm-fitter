## Scharm to Charm Fitter

This package includes all the code to calculate CLs upper limits for
direct production of supersymmetric charm quarks decaying to charm jets.

The aim is to provide:

 1. A common script that can read yields (in a textfile format) and
    construct workspaces to test various signal points.
 2. A script to run the fit on an existing workspace and save the fit
    results to a textfile.

Less important goals may include:

 - Scripts to perform sanity checks on the inputs / outputs,

What's not currently included:

 - The suite of HistFitter scripts like `YieldsTable`, `SysTable`, etc.
 - Plotting code.

### Quickstart

Running `install.py install` will add a `.pth` file to your local
python installation. It will also run `make` in the `src/` directory to
build the HistFitter fitting functions. All top level scripts are in
the `scripts` directory:

 - `susy-fit-*`: try the `-h` flag to get help.
 - `susy-fit-test.py`: this segfaults on some computers I use, even
   though it's doing very little. I suspect it has something to do
   with a bad pyroot install, but if it fails, everything else here
   will as well.

Example inputs are in `example_data/`. If `scripts/` has been
added to your `PATH`, the following command ~~should~~ *would*
(if I got around update the example data) produce some
workspaces:

```bash
cd example_data
susy-fit-workspace.py inputs.yml -c configuration.yml -f
```

Adding the `-f` flag will produce the `_afterFit.root`, -l will
produce `_upperlimits.root` files.

### Input / Output format

Input files should be formatted as follows:

```yaml
nominal_yields:
  REGION_NAME:
    data: [DATA_YIELD]
    BACKGROUND: [YIELD, STATISTICAL_UNCERTAINTY]
    ....
    scharm-SCHARM_MASS-LSP_MASS: [YIELD, STATISTICAL_UNCERTAINTY]:
  REGION_NAME:
    ....

yield_systematics:
  SYSTEMATIC:
    REGION_NAME:
      BACKGROUND: [YIELD]
    ....

relative_systematics:
  SYSTEMATIC:
    REGION_NAME:
      BACKGROUND: [DOWN, UP]
    REGION_NAME: [DOWN, UP]
  ....

```

The `REGION_NAME`s are completely arbitrary, since the fit treats all regions
identically (except when the signal region is blinded and the MC SM sum is used in place of real data).

Some of the `SYSTEMATIC` categories under `yield_systematics` will be
treated in special ways:
 - The b-tagging systematics (names starting with `b`, `c`, `u`, or
   `t` and ending with `up` or `down`, i.e. `bup`, `udown` etc...)
   can be added in quadrature before fitting. (will print warnings
   if all these backgrounds aren't found).
 - Other names that end in `up` or `down` will be paired to give an
   asymmetric uncertainty.
 - Any other (unpaired) systematics will be entered as a symmetric uncertainty
   centered on the nominal value.

Signal points must be of the form "`scharm-` scharm mass `-` lsp
mass".  The masses can be arbitrary integers. Data points should be
entered as `data`, and the `BACKGROUND` names are arbitrary.

Values given by `YIELD` and `STATISTICAL_UNCERTAINTY` should be
absolute. Relative uncertainties are specified with `1.0` meaning "no
variation", e.g. a variation that is expected to fluctuate by 20% in
each direction would be `[0.8, 1.2]`. Specifying a systematic in the
form `REGION_NAME: [DOWN, UP]` applies the systematic to all samples
in the region.

#### Fit Config File

An additional "fit config" file is required as an input to the workspace
creation routine. This is formatted as:

```yaml
CONFIG_NAME:
  control_regions: [REG1, REG2, ...]
  signal_region: SIG_REGION
  combine_tagging: TRUE_OR_FALSE
  fixed_backgrounds: [BG1, BG2, ...]
  systematics: [SYS1, SYS2, ...]
```

This file will be created (although not necessarily with sensible
regions) if it doesn't exist. The option `combine_tagging` tells the
fitter whether it should add the flavor tagging systematics in
quadrature.

### Outstanding issues:

 - The code may not be very robust to incorrectly formatted
   files. Invalid yaml won't get through, but no promises about
   anything that doesn't conform to the above schema.
 - The workspace creation routine prints a lot of errors of the form:
   `ERROR argument with name nom_something is already in this
   set`. These are _probably_ just harmless overwrites, since the
   nominal value shouldn't be use in the fit, but it should be
   checked. For now these errors are being filtered from the output
   stream.
 - Workspace creation produces about 5 files, only one of which we
   seem to need. Right now I'm deleting the others, should make sure
   this is safe.
