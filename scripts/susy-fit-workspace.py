#!/usr/bin/env python2.7
"""
Workspace generator for scharm to charm search.
"""
_yields_file = 'yaml file giving the yields'
_config_file = (
    'file listing signal / control regions, will be generated if missing')
_hf_magic = 'run histfitter stuff'
import argparse, re, sys, os
from os.path import isfile, isdir, join
from itertools import chain
import yaml
import warnings
from scharmfit.fitter import Workspace
from scharmfit.fitter import get_signal_points_and_backgrounds

def run():
    d = 'default: %(default)s'
    parser = argparse.ArgumentParser(description=__doc__)

    # add input options
    parser.add_argument(
        'yields_file', help=_yields_file)
    parser.add_argument(
        '-y','--fit-config', required=True, help=_config_file)
    parser.add_argument('-o', '--out-dir', default='workspaces', help=d)
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('-m', '--magic', action='store_true', help=_hf_magic)
    # parse inputs and run
    args = parser.parse_args(sys.argv[1:])
    _multispaces(args)

def _multispaces(config):

    with open(config.yields_file) as yields_yml:
        yields = yaml.load(yields_yml)

    # get / generate the fit configuration
    fit_configs = _get_config(config.fit_config, yields)

    signal_points, bgs = get_signal_points_and_backgrounds(yields)
    print 'using backgrounds: {}'.format(', '.join(bgs))

    misc_config = dict(backgrounds=bgs, out_dir=config.out_dir,
                       debug=config.debug, do_hf=config.magic)

    # loop ovar all signal points and fit configurations. Note that
    # memory leaks in HistFactory make this difficult.
    for signal_point in signal_points:
        for cfg_name, fit_cfg in fit_configs.iteritems():
            print 'booking signal point {} with {} config'.format(
                signal_point, cfg_name)
            _book_signal_point(yields, signal_point, fit_cfg,
                               misc_config)

def _book_signal_point(yields, signal_point, fit_config, misc_config):
    import ROOT
    # TODO: this leaks memory like crazy, not sure why but bug reports
    # have been filed. For now just using output filters.
    fit = Workspace(yields, misc_config['backgrounds'])
    if misc_config['debug']:
        fit.debug = True
    fit.set_signal(signal_point)
    for cr in fit_config['control_regions']:
        fit.add_cr(cr)

    sr = fit_config['signal_region']
    fit.add_sr(sr)

    out_dir = misc_config['out_dir']
    if not isdir(out_dir):
        os.makedirs(out_dir)

    fit.save_workspace(out_dir)

    # here be black magic
    ws_name = join(out_dir, '{}_combined_{meas}_model.root').format(
        signal_point, meas=fit.meas_name)
    if misc_config['do_hf']:
        fit.do_histfitter_magic(ws_name)
        sys.exit('wrote a histfitter workspace, quitting')
    ROOT.gDirectory.GetList().Delete()

# _______________________________________________________________________
# helpers

def _get_config(cfg_name, yields_dict):
    """gets / generates the fit config file"""

    if isfile(cfg_name):
        with open(cfg_name) as yml:
            fit_configs = yaml.load(yml)
    else:
        def_config = {
            'control_regions': [
                'cr_1l', 'cr_df', 'cr_z'
                ],
            'signal_region': 'signal',
            }
        fit_configs = {'default': def_config}
        with open(cfg_name, 'w') as yml:
            yml.write(yaml.dump(fit_configs))

    # check to make sure all the requested regions actually exist
    ichain = chain.from_iterable
    y_regs = set(ichain(sys.keys() for sys in yields_dict.itervalues()))
    f_regs = set(
        ichain(c['control_regions'] for c in fit_configs.itervalues()))
    f_regs |= set(c['signal_region'] for c in fit_configs.itervalues())
    missing_regions = f_regs - y_regs
    if missing_regions:
        raise ValueError('missing regions: {}'.format(
                ', '.join(missing_regions)))

    return fit_configs

if __name__ == '__main__':
    run()
