#!/usr/bin/env python2.7
import argparse, re, sys


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('yields_file')
    parser.add_argument('-y','--fit-config', required=True)
    args = parser.parse_args(sys.argv[1:])
    _multispaces(args)

def _get_sp(proc):
    """regex search for signal points"""
    sig_finder = re.compile('scharm-([0-9]+)-([0-9]+)')
    try:
        schstr, lspstr = sig_finder.search(proc).groups()
    except AttributeError:
        return None
    return int(schstr), int(lspstr)

def _multispaces(config):

    with open(config.yields_file) as yields_yml:
        yields = yaml.load(yields_yml)

    # assume structure {syst: {proc: <counts>, ...}, ...}
    signal_points = []
    for syst in yields_yml.itervalues():
        for proc in syst:
            sp = _get_sp(proc)
            if sp:
                signal_points.append( sp )

    with open(config.fit_config) as yml:
        fit_configs = yaml.load(yml)

    signal_point = signal_points[0]
    print 'booking signal point {}'.format(signal_point)
    _book_signal_point(yields, signal_point)

def _book_signal_point(counts, signal_point):
    import ROOT
    # backgrounds = fit_config['backgrounds']

    # TODO: this leaks memory like crazy, not sure why but bug reports
    # have been filed. For now just using output filters.
    fit = Workspace(counts, systematics, backgrounds)
    fit.set_signal(signal_point)
    for cr in fit_config['control_regions']:
        fit.add_cr(cr)

    sr = fit_config['signal_region']
    fit.add_sr(sr)

    out_dir = 'test-output'
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    fit.save_workspace(out_dir)
    ROOT.gDirectory.GetList().Delete()

if __name__ == '__main__':
    run()
