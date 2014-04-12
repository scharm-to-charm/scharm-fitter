#!/usr/bin/env python2.7
"""
Upper limit calculator scharm to charm search. Takes a directory of
workspaces as an input.
"""
import yaml
from os.path import join
import argparse, re, sys, glob
from scharmfit.fitter import UpperLimitCalc

def run():
    d = '(default: %(default)s)'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace_dir')
    parser.add_argument(
        '-o','--output-file', default='upper-limits.yml', help=d)
    config = parser.parse_args(sys.argv[1:])
    _get_upper_limit(config)

def _get_upper_limit(config):
    workspaces = glob.glob(join(config.workspace_dir,'*_combined_*.root'))
    all_pts = []
    for workspace_name in workspaces:
        print 'fitting {}'.format(workspace_name)
        ul_dict = _ul_from_workspace(workspace_name.strip())
        all_pts.append(ul_dict)
    with open(config.output_file,'w') as out_yml:
        out_yml.write(yaml.dump(all_pts))

_sp_re = re.compile('scharm-([0-9]+)-([0-9]+)_combined')
def _ul_from_workspace(workspace_name):
    ul_calc = UpperLimitCalc()
    lower_limit, mean_limit, upper_limit = ul_calc.lim_range(workspace_name)
    schs, lsps = _sp_re.search(workspace_name).group(1,2)
    ul_dict = {
        'upper': upper_limit,
        'lower': lower_limit,
        'mean': mean_limit,
        'scharm_mass': int(schs),
        'lsp_mass': int(lsps)
        }
    return ul_dict

if __name__ == '__main__':
    run()
