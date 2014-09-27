#!/usr/bin/env python2.7
"""
Discovery fitter for scharm to charm search. Takes a directory of
workspaces as an input.
"""

import yaml
from os.path import join, basename
import argparse, glob, sys
from os import walk

from scharmfit.utils import load_susyfit, make_dir_if_none

# __________________________________________________________________________
# constants

# only fit files that start with this
_prefit_prefix = 'discovery'

# __________________________________________________________________________
# run routine

def run():
    d = '(default: %(default)s)'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace_dir')
    parser.add_argument(
        '-o','--output-dir', help='save outcrap here ' + d, default='shit')
    config = parser.parse_args(sys.argv[1:])

    # run the fits
    _make_calc_file(config)

def _is_prefit(workspace):
    if workspace.endswith('afterFit.root'):
        return False
    return basename(workspace).startswith(_prefit_prefix)

def _make_calc_file(config):
    # loop over all the workspaces, fit them all
    for base, dirs, files in walk(config.workspace_dir):
        if not dirs and files:
            workspaces = filter(_is_prefit,glob.glob(join(base, '*.root')))
            # the configuration name (key under which the fit result
            # is saved) is the path from the directory we run on to
            # the directory where the workspaces are found.
            if len(workspaces) > 1.0:
                raise OSError("too many workspaces: {}".format(
                        ', '.join(workspaces)))
            ws_name = workspaces[0]
            _fit_ws(ws_name, config.output_dir)

def _fit_ws(ws_path, output_dir, toys=0):
    """Print some plots, figures out file name by the ws_path"""
    make_dir_if_none(output_dir)
    cfg = ws_path.split('/')[-2]
    out_pfx = join(output_dir, cfg)

    load_susyfit()
    from ROOT import Util, RooStats

    ctype = 0 if toys else 2    # use asymtotic if toys is zero
    test_stat_type = 3
    use_cls = True
    points = 20                 # mu values to use

    ws = Util.GetWorkspaceFromFile(ws_path, 'combined')
    result = RooStats.MakeUpperLimitPlot(
        out_pfx, ws, ctype, test_stat_type, toys, use_cls, points)
    

if __name__ == '__main__':
    run()
