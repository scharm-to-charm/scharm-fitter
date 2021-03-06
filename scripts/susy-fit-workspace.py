#!/usr/bin/env python2.7
"""
Workspace generator for scharm to charm search.
"""
_yields_file = 'yaml file giving the yields'
_config_file = (
    'file listing signal / control regions, will be generated if missing')
_after_fit = "produce and 'afterFit' files"
_upper_limits = "produce histfitter 'upper limit' stuff"
_up_help = 'do upward variant of signal theory'
_down_help = 'do downward variant of signal theory'
_sub_help = 'only use subset of fit configurations'

import argparse, re, sys, os
from os.path import isfile, isdir, join, dirname
from itertools import chain
import yaml
import warnings
from scharmfit.workspace import Workspace, do_upper_limits, DISCOVERY
from scharmfit.workspace import get_signal_points_and_backgrounds

def run():
    d = 'default: %(default)s'
    sigop = dict(action='store_const', dest='signal_systematic')
    parser = argparse.ArgumentParser(description=__doc__)

    # add input options
    parser.add_argument(
        'yields_file', help=_yields_file)
    parser.add_argument(
        '-c','--fit-config', required=True, help=_config_file)
    parser.add_argument('-o', '--out-dir', default='workspaces', help=d)
    parser.add_argument('-s', '--subset', help=_sub_help, nargs='+')
    parser.add_argument('-b', '--background-only', action='store_true')
    parser.add_argument('-d', '--debug', action='store_true')
    fit_version = parser.add_mutually_exclusive_group()
    fit_version.add_argument('--blind', action='store_true', dest='blind')
    fit_version.add_argument('--injection', action='store_true')
    fit_version.add_argument('--up', const='up', help=_up_help, **sigop)
    fit_version.add_argument('--down', const='down', help=_down_help, **sigop)
    hf_action = parser.add_mutually_exclusive_group()
    hf_action.add_argument('-f', '--after-fit', action='store_true',
                           help=_after_fit)
    hf_action.add_argument('-l', '--upper-limit', action='store_true',
                           help=_upper_limits)
    parser.add_argument('-v', '--verbose', action='store_true')
    # parse inputs and run
    args = parser.parse_args(sys.argv[1:])
    _book_workspaces(args)

# _________________________________________________________________________
# main workspace booking function

def _book_workspaces(args):
    """book one workspace for each signal point"""

    with open(args.yields_file) as yields_yml:
        yields = yaml.load(yields_yml)

    # get / generate the fit configuration
    fit_configs = _get_config(args.fit_config, yields, args.subset)
    if not fit_configs:
        print 'wrote {}, quitting...'.format(args.fit_config)
        return

    signal_points, bgs = get_signal_points_and_backgrounds(yields)
    print 'using backgrounds: {}'.format(', '.join(bgs))
    if args.background_only:
        signal_points = []

    # in most cases, the workspace setup doesn't actually need to run
    # the HistFitter routines: what's given in HistFactory is enough
    run_histfitter = args.after_fit or args.upper_limit

    # setup fitting options from command line
    cl_config = dict(do_hf=run_histfitter)
    pass_options = [
        'out_dir', 'debug', 'verbose', 'blind', 'injection',
        'signal_systematic']
    cl_config.update({x:getattr(args, x) for x in pass_options})

    # loop ovar all signal points and fit configurations.
    for cfg in fit_configs.iteritems():
        cfg_name, fit_cfg = cfg

        print 'booking background with config {}'.format(cfg_name)
        _book_background_fits(yields, cfg, cl_config)

        # skip signal points if doing 'up' or 'down' with no given sig systs
        if not fit_cfg.get('signal_systematics') and args.signal_systematic:
            continue

        for signal_point in signal_points:
            print 'booking signal point {} with {} config'.format(
                signal_point, cfg_name)
            _book_signal_point(yields, signal_point, cfg, cl_config)

    # this relies on HistFitter's global variables, has to be run
    # after booking a bunch of workspaces.
    if args.upper_limit:
        pfx = args.signal_systematic or 'nominal'
        dirpfx = join(dirname(args.fit_config), pfx)
        print 'calculating {} upper limits (may take a while)'.format(dirpfx)
        do_upper_limits(verbose=args.verbose, prefix=dirpfx)

def _book_background_fits(yields, cfg, cl_config):
    """various types of 'background only' fits"""

    # everything here calls the method below, with some special version
    # of the signal point

    # blank signal point means no point (but use SR in fit)
    _book_signal_point(yields, '', cfg, cl_config)
    # 'CR_ONLY' means don't use SR in fit
    _book_signal_point(yields, 'CR_ONLY', cfg, cl_config)
    # DISCOVERY means set signal to 1 in SR only
    _book_signal_point(yields, DISCOVERY, cfg, cl_config)


def _book_signal_point(yields, signal_point, fit_configuration, cl_config):
    """
    Book the workspace for one signal point. If the point is '' we run
    a background only fit.
    """
    cfg_name, fit_config = fit_configuration
    import ROOT
    # TODO: this leaks memory like crazy, known HistFactory bug
    fit = Workspace(yields, fit_config, cl_config)

    fit_sr = True
    # hackish way to specify no signal point AND no signal region
    if signal_point == 'CR_ONLY':
        fit_sr = False
        signal_point = ''

    if signal_point:
        fit.set_signal(signal_point)
    for sr in fit_config['signal_regions']:
        fit.add_sr(sr, fit=fit_sr)
    for cr in fit_config['control_regions']:
        fit.add_cr(cr)
    # we can't do hypothisis testing with validation regions, so we only
    # add the validation regions when no signal point is specified
    if not signal_point:
        for vr in fit_config.get('validation_regions', []):
            fit.add_vr(vr)

    out_dir = join(cl_config['out_dir'], cfg_name)
    if not isdir(out_dir):
        os.makedirs(out_dir)

    fit.save_workspace(out_dir)

    if not cl_config['do_hf']:
        return

    # here be black magic
    fit.do_histfitter_magic(out_dir, verbose=cl_config['verbose'])

# _______________________________________________________________________
# helpers

_nom_yields_key = 'nominal_yields'
_syst_yields_key = 'yield_systematics'
def _get_config(cfg_name, yields_dict, subset=None):
    """gets / generates the fit config file"""

    all_syst = _all_syst_from_yields(yields_dict)
    def_config = {
        'control_regions': [
            x for x in yields_dict[_nom_yields_key] if x.startswith('cr_')
            ],
        'signal_regions': ['signal_mct150'],
        'fixed_backgrounds': ['other'],
        'systematics': list(all_syst),
        'combined_backgrounds': {'other':['singleTop']},
        'validation_regions': [],
        'signal_systematics': [],
        }
    if isfile(cfg_name):
        with open(cfg_name) as yml:
            fit_configs = yaml.load(yml)
        for cfg in fit_configs.values():
            for opt in cfg:
                if opt not in def_config:
                    raise ValueError('invalid config option: {}'.format(opt))
        if subset:
            fit_configs = {x:fit_configs[x] for x in subset}
    else:
        fit_configs = {'default': def_config}
        with open(cfg_name, 'w') as yml:
            yml.write(yaml.dump(fit_configs, width=70))
        return None

    # check to make sure all the requested regions actually exist
    ichain = chain.from_iterable
    y_regs = set(yields_dict[_nom_yields_key].iterkeys())
    f_regs = set(
        ichain(c['control_regions'] for c in fit_configs.itervalues()))
    f_regs |= set(
        ichain(c['signal_regions'] for c in fit_configs.itervalues()))
    missing_regions = f_regs - y_regs
    if missing_regions:
        raise ValueError('missing regions: {}'.format(
                ', '.join(missing_regions)))

    return fit_configs

def _all_syst_from_yields(yields_dict):
    """return the systematic variations, with up / down stripped off"""
    all_syst = set(yields_dict[_syst_yields_key].iterkeys())
    def _strip(syst):
        for suffix in ['up','down']:
            if syst.endswith(suffix):
                return syst[:-len(suffix)]
        return syst
    return set(_strip(x) for x in all_syst)

if __name__ == '__main__':
    run()
