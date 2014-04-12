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
 - Plotting code.

### Quickstart

Running `install.py install` will add a `.pth` file to your local
python installation. This will allow scripts to find the needed
module.  All top level scripts are in the `scripts` directory:

 - `susy-fit-*`: try the `-h` flag to get help.
 - `susy-fit-test.py`: this segfaults on some computers I use, even
   though it's doing very little. I suspect it has something to do
   with a bad pyroot install, but if it fails, everything else here
   will as well.

### Input / Output format

Input files should be formatted as follows:

```yaml
nominal_yields:
  REGION_NAME:
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
  ....

```

The `REGION_NAME`s are completely arbitrary, since the fit treats all regions
identically (except when the signal region is blinded and the MC SM sum is used in place of real data).

Signal point and background names are _mostly_ arbitrary, with a few exceptions:
 - some `BACKGROUND`s will be treated in a special way, for example
   the b-tagging systematics will all be added in quadrature before
   the fit, (will probably add warnings if all these backgrounds
   aren't found)
 - signal points must be of the form "`scharm-` scharm
   mass `-` lsp mass".  The masses can be arbitrary integers, though.

Values given by `YIELD` and `STATISTICAL_UNCERTAINTY` should be
absolute. Relative uncertainties are specified with `1.0` meaning "no
variation", e.g. a variation that is expected to fluctuate by 20% in
each direction would be `[0.8, 1.2]`.

#### Fit Config File

An additional "fit config" file is required as an input to the workspace
creation routine. This is formatted as:

```yaml
CONFIG_NAME:
  control_regions: [REG1, REG2, ...]
  signal_region: SIG_REGION
```

This file will be created (although not necessarily with sensible
regions) if it doesn't exist.

### Outstanding issues:

 - Need to add relative systematics to the fit (currently they will be
   ignored).
 - The code may not be very robust to incorrectly formatted
   files. Invalid yaml won't get through, but no promises about
   anything that doesn't conform to the above schema.
 - The workspace creation routine prints a lot of errors of the form:
   `ERROR argument with name nom_something is already in this
   set`. These are _probably_ just harmless overwrites, since the
   nominal value shouldn't be use in the fit, but it should be checked.
 - Workspace creation produces about 5 files, only one of which we
   seem to need. Right now I'm deleting the others, should make sure
   this is safe.
 - Figure out whether the `sample.ActivateStatError()` function is
   needed in our case. If so, figure out how to keep it from crashing.
