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
module.  All top level scripts are in the `scripts` directory, try
`script-name.py -h` to learn more.
