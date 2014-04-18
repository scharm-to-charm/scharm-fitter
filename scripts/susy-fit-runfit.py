#!/usr/bin/env python2.7
"""
Fitter for scharm to charm search. Takes a directory of
workspaces as an input.
"""
import yaml
from os.path import join, relpath
import argparse, re, sys, glob
from scharmfit.calculators import UpperLimitCalc, CLsCalc
from os import walk

def run():
    d = '(default: %(default)s)'
    outputs = {'ul':'upper-limits.yml', 'cls':'cls.yml'}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace_dir')
    parser.add_argument('-c','--calc-type', choices=outputs.keys(),
                        required=True)

    # default output file depends on what you're running
    def_string = ', '.join('{}: {}'.format(*x) for x in outputs.iteritems())
    parser.add_argument(
        '-o','--output-file', help='defaults -- {}'.format(def_string))
    config = parser.parse_args(sys.argv[1:])
    if not config.output_file:
        config.output_file = outputs[config.calc_type]

    # run the fits
    _make_calc_file(config)

def _make_calc_file(config):
    cfg_dict = {}
    # choose the calculator
    calculate = {'ul':_get_ul, 'cls':_get_cls}[config.calc_type]

    # loop over all the workspaces, fit them all
    for base, dirs, files in walk(config.workspace_dir):
        if not dirs and files:
            workspaces = glob.glob(join(base,'*_combined_*_model.root'))

            # the configuration name (key under which the fit result
            # is saved) is the path from the directory we run on to
            # the directory where the workspaces are found.
            cfg = base
            if base != config.workspace_dir:
                cfg = relpath(base, config.workspace_dir)
            all_pts = []
            for workspace_name in workspaces:
                print 'fitting {}'.format(workspace_name)
                fit_dict = calculate(workspace_name.strip())
                fit_dict.update(_get_sp_dict(workspace_name))
                all_pts.append(fit_dict)
            cfg_dict[cfg] = all_pts

    with open(config.output_file,'w') as out_yml:
        out_yml.write(yaml.dump(cfg_dict))

_sp_re = re.compile('scharm-([0-9]+)-([0-9]+)_combined')
def _get_sp_dict(workspace_name):
    """gets a dictionary describing the signal point"""
    schs, lsps = _sp_re.search(workspace_name).group(1,2)
    return {'scharm_mass': int(schs), 'lsp_mass': int(lsps)}

# __________________________________________________________________________
# calculate functions (very thin wrapper on the imported calculators)

def _get_ul(workspace_name):
    ul_calc = UpperLimitCalc()
    lower_limit, mean_limit, upper_limit = ul_calc.lim_range(workspace_name)
    ul_dict = {
        'upper': upper_limit,
        'lower': lower_limit,
        'mean': mean_limit,
        }
    return ul_dict

def _get_cls(workspace_name):
    calc = CLsCalc()
    return calc.calculate_cls(workspace_name)

if __name__ == '__main__':
    run()
