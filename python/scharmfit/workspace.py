"""
Module containing workspace setup routines. The actual fitting and
statistical analyiss stuff is done elsewhere.
"""

from scharmfit.utils import OutputFilter
import os, re, glob, math
from os.path import isdir, join, basename
from collections import defaultdict, Counter
import warnings
from itertools import chain, product

# GENERAL CONFUSING THINGS:
#
#  - The input files are generally structured as
#    {variation: {region: {sample: ... }, ... }, ... }
#    When creating the workspace it's more convenient to structure this as
#    {region: {sample: {variation: (down, up) }, ... }, ... }
#    Some functions called in the constructor handle this reordering.
#
#  - Blinding and 'pseudodata': for blinded exclusion fits, the signal
#    region is filled with the sum of the SM backgrounds ('pseudodata').
#    Since we don't know what this sum is before adding all the backgrounds,
#    the pseudodata regions are added to the Measurement _after_ all the
#    other regions, when the workspace is saved.
#
#  - `Log` files: I generally find huge amounts of output distracting, so
#    I've created a contex manager `OutputFilter` that does some magic with
#    the output streams to silence noisy routines. You can comment these
#    out to get the output, or just insert `accept_strings={''}` into the
#    `OutputFilter` constructor.


# define some keys used in the yaml input file (to avoid hardcoding
# them in multiple places)
_baseline_yields_key = 'nominal_yields'
_yield_systematics_key = 'yield_systematics'
_relative_systematics_key = 'relative_systematics'

# Enum-like value to indicate discovery fit, also used to name that
# workspace
DISCOVERY = 'discovery'

class Workspace(object):
    """
    Organizes the building of workspaces, mainly by providing functions to
    transfer from the input yaml file to a RooFit workspace.
    """
    # -- various definitions (for histfitter and input textfile schema) --
    # histfitter
    meas_name = 'meas'

    # out file names
    name_tpl = '{pfx}_{sigdir}.root'
    nominal = 'nominal'
    up1s = 'up1sigma'
    down1s = 'down1sigma'
    sr_plus_cr_fit_prefix = 'srcr'
    cr_only_fit_prefix = 'background'

    # input file schema
    baseline_yields_key = _baseline_yields_key
    yield_systematics_key = _yield_systematics_key
    relative_systematics_key = _relative_systematics_key
    # number and error are stored as first and second entry
    _nkey = 0                  # yield
    _errkey = 1                # stat error
    def __init__(self, yields, fit_config, misc_config):
        self._fixed_backgrounds = fit_config['fixed_backgrounds']
        self._setup_misc_config(misc_config)

        # load yields
        yields = _combine_backgrounds(
            yields, fit_config.get('combined_backgrounds',{}))
        self._yields = yields[self.baseline_yields_key]

        # load systematics and save list of backgrounds
        all_sp, backgrounds = get_signal_points_and_backgrounds(yields)
        _check_subset(fit_config['fixed_backgrounds'], backgrounds)
        self._load_systematics(yields, fit_config, all_sp + backgrounds)
        self._backgrounds = backgrounds

        # load in signal systematics
        rel_yields = yields[self.relative_systematics_key]
        self._load_signal_systs(rel_yields, fit_config, misc_config)

        # create / configure the measurement
        import ROOT
        with OutputFilter(): # turn off David and Wouter's self-promotion
            self.hf = ROOT.RooStats.HistFactory
        self.meas = self.hf.Measurement(self.meas_name, self.meas_name)

        # NOTE: see this twiki for lumi ref
        # https://twiki.cern.ch/twiki/bin/viewauth/Atlas/LuminosityForPhysics
        self.meas.SetLumi(1.0)
        lumiError = 0.028
        self.meas.SetLumiRelErr(lumiError)

        self._signal_point = None
        self._fit_signal_region = False
        # for blinding / pseudodata: `pseudodata` just means the sume of SM
        # backgrounds are used.
        self._region_sums = Counter()
        self._pseudodata_regions = set()
        self._non_fit_regions = set()

        # We're using pseudodata, which means we have to save the
        # channels and add them to meas later.
        self._channels = {}

    def _setup_misc_config(self, misc_config):
        """setup the stuff passed via command line"""
        self._blinded = misc_config['blind']
        self._inject = misc_config['injection']
        self.debug = misc_config['debug']
        self._do_pseudodata = False

    def _load_systematics(self, yields, config, all_proc):
        """
        called by initialize routine, handle all the organization
        and storing of the systematic variations
        """
        # filter out unwanted systematics, anything missing from the
        # yields is assumed to be entered as a relative systematic further
        # down.
        requested_syst = config['systematics']
        yield_systematics, missing_syst = _filter_systematics(
            yields[self.yield_systematics_key], requested_syst)
        base_yields = yields[self.baseline_yields_key]

        # HistFactory actually wants all the systematics as relative
        # systematics, we convert them here.  the relative systematics
        # are keyed as
        # {region: {process:{systematic: (down, up), ...}, ... }, ...}
        self._systematics = _get_relative_from_abs_systematics(
            base_yields, yield_systematics)

        # add the relative systematics
        rel_systs = _filter_rel_systematics(
            yields.get(self.relative_systematics_key, {}), missing_syst)
        _update_with_relative_systematics(
            self._systematics, rel_systs, all_proc)

    def _load_signal_systs(self, rel_syst, fit_config, misc_config):
        """
        load signal systematics from relative systematics, fit config,
        and misc config files.
        """
        siglist = fit_config.get('signal_systematics',[])
        updown = misc_config['signal_systematic']
        self._sigsysts = _get_signal_systematics(rel_syst, siglist, updown)
        self._sigsyst_sign = {'up':1, 'down':-1}.get(updown, 0)

    # ____________________________________________________________________
    # top level methods to set control / signal regions
    def add_cr(self, cr):
        chan = self.hf.Channel(cr)
        if self._do_pseudodata:
            self._pseudodata_regions.add(cr)
        else:
            data_count = self._yields[cr]['data']
            with OutputFilter():
                chan.SetData(data_count[self._nkey])
        # ACHTUNG: not at all sure what this does
        # chan.SetStatErrorConfig(0.05, "Gaussian")
        self._add_mc_to_channel(chan, cr)
        self._channels[cr] = chan

    def add_vr(self, vr):
        """
        same as adding a cr, but doesn't add it to the fit in
        histfitter magic stage
        """
        self.add_cr(vr)
        self._non_fit_regions.add(vr)

    def add_sr(self, sr, fit=True):
        chan = self.hf.Channel(sr)
        if self._blinded or self._inject:
            self._pseudodata_regions.add(sr)
        else:
            # print 'unblind!'
            data_count = self._yields[sr]['data']
            with OutputFilter():
                chan.SetData(data_count[self._nkey])
        # don't fit the SR if this is a BG only fit
        if fit:
            self._fit_signal_region = True
        else:
            self._non_fit_regions.add(sr)
        # ACHTUNG: again, not sure what this does
        # chan.SetStatErrorConfig(0.05, "Gaussian")
        self._add_mc_to_channel(chan, sr, is_sr=True)
        self._channels[sr] = chan

    def set_signal(self, signal_name):
        if self._signal_point:
            raise ValueError('tried to overwrite {} with {}'.format(
                    self._signal_point, signal_name))
        if self._channels:
            raise ValueError("can't set signal point after adding regions")
        self._signal_point = signal_name
        self.meas.SetPOI("mu_Sig")

    # ____________________________________________________________________
    # functions to add samples to the channel

    def _add_mc_to_channel(self, chan, region, is_sr=False):
        """
        Adds the signal mc and the backgrounds to this channel.
        """
        sp = self._signal_point
        # the 'discovery fit' uses a one signal event in the signal region
        # with no systematics applied
        if sp == DISCOVERY:
            if is_sr:
                sname = '_'.join([self._signal_point,region])
                signal = self.hf.Sample(sname)
                _set_value(signal, 1.0, 0.0)
                signal.SetNormalizeByTheory(True)
                signal.AddNormFactor('mu_Sig',1,0,100)
                chan.AddSample(signal)
        elif sp and sp in self._yields[region]:
            self._add_signal_to_channel(chan, region)

        for bg in self._backgrounds:
            self._add_background_to_channel(chan, region, bg)

    def _get_rel_sigsyst(self, region):
        """return the relative systematic on the signal sample"""
        if self._sigsyst_sign:
            sys2 = self._sigsysts[region,self._signal_point]
            return 1 + math.copysign(sys2**0.5, self._sigsyst_sign)
        return 1

    def _add_signal_to_channel(self, chan, region):
        """should be called by _add_mc_to_channel"""
        # get yield / stat error in SR
        yields = self._yields

        # If we're this far, we can create the signal sample
        sname = '_'.join([self._signal_point,region])
        signal = self.hf.Sample(sname)

        # I've kept the _nkey, and _errkey variables so it's easy to
        # change over to a dictionary. For now they are list indices.
        sig_yield = yields[region][self._signal_point]
        sig_syst = self._get_rel_sigsyst(region)
        signal_count = sig_yield[self._nkey] * sig_syst
        _set_value(signal, signal_count, sig_yield[self._errkey] * sig_syst)

        if self._inject:
            self._region_sums[region] += signal_count

        # ACHTUNG: The documentation basically says that
        # this "activates" the statistical error... great!
        signal.ActivateStatError()

        # I think this means the lumi uncertainty isn't used for this
        # sample (i.e. it's not controled for by a control region)
        signal.SetNormalizeByTheory(True)

        signal.AddNormFactor('mu_Sig',1,0,2)

        # --- add systematics ---
        syst_dict = self._systematics[region][self._signal_point]
        for syst, var in syst_dict.iteritems():
            signal.AddOverallSys(syst, *var)

        chan.AddSample(signal)

    def _add_background_to_channel(self, chan, region, bg):
        base_vals = self._yields[region].get(bg, [0.0, 0.0])
        bg_n = base_vals[self._nkey]
        # region sums are needed for blinded results
        self._region_sums[region] += bg_n
        sname = '_'.join([region,bg])
        background = self.hf.Sample(sname)
        _set_value(background, bg_n, base_vals[self._errkey])

        if not bg in self._fixed_backgrounds:
            background.AddNormFactor('mu_{}'.format(bg), 1,0,2)
        else:
            # SEE ABOVE COMMENT on SetNormalizeByTheory
            background.SetNormalizeByTheory(True)

        # SEE ABOVE COMMENT on ActivateStatError
        background.ActivateStatError()
        # --- add systematics ---
        syst_dict = self._systematics[region].get(bg, {})
        for syst, var in syst_dict.iteritems():
            background.AddOverallSys(syst, *var)

        chan.AddSample(background)

    # _________________________________________________________________
    # save the workspace

    def _get_ws_name(self):
        """
        The workspace is named according to the signal point. If there's
        no signal point, it's called 'background'
        """
        if self._signal_point:
            prefix = self._signal_point
        elif self._fit_signal_region:
            prefix = self.sr_plus_cr_fit_prefix
        else:
            prefix = self.cr_only_fit_prefix

        outnames = {1: self.up1s, -1: self.down1s, 0: self.nominal}
        sigsyst_name = outnames[self._sigsyst_sign]

        return self.name_tpl.format(pfx=prefix, sigdir=sigsyst_name)

    def _build_measurement(self):
        """
        Fill the pseudodata regions to complete measurement.
        """
        for chan_name, channel in self._channels.iteritems():
            # add the pseudodata regions
            if chan_name in self._pseudodata_regions:
                pseudo_count = self._region_sums[chan_name]
                if chan_name in self._non_fit_regions:
                    pseudo_count = 0.0
                with OutputFilter():
                    channel.SetData(pseudo_count)
            self.meas.AddChannel(channel)

        # some safety checks
        n_free_pars = len(self._backgrounds) - len(self._fixed_backgrounds)
        if self._signal_point:
            n_free_pars += 1

        n_chan = len(self._channels) - len(self._non_fit_regions)
        if n_free_pars > n_chan:
            err_tmp = (
                'underrestrained fit: '
                '{} free parameters restrained by only {} regions')
            raise ValueError(err_tmp.format(n_free_pars, n_chan))

    def save_workspace(self, results_dir, verbose=False):
        # if we haven't set a signal point, need to set a dummy
        # (otherwise something will crash)
        if not self._signal_point:
            self.meas.SetPOI("mu_Sig")
        if not isdir(results_dir):
            os.mkdir(results_dir)

        # we actually build the measurement here (couldn't be done earlier
        # because we needed to calculate pseudo-data)
        self._build_measurement()

        # don't want to save the output files in the current dir, set
        # the output prefix here.
        # self.meas.SetOutputFilePrefix(
        #     join(results_dir, self._get_ws_prefix()))

        # I think this turns off the fitting...
        self.meas.SetExportOnly(True)

        pass_strings = ['ERROR:','WARNING:']
        veto_strings={
            'ERROR argument with name nominalLumi',
            'ERROR argument with name nom_alpha_',
            "Can't find parameter of interest: mu_Sig"}
        filter_args = dict(
            accept_re='({})'.format('|'.join(pass_strings)),
            veto_strings=veto_strings)

        if self.debug:
            print ' --- printing tree ---'
            self.meas.PrintTree()
            print ' --- printing xml ---'
            self.meas.PrintXML(results_dir)
            print ' --- making model and measurement ---'

        out_name = self._get_ws_name()

        with OutputFilter(**filter_args):
            from ROOT import TFile
            h2ws = self.hf.HistoToWorkspaceFactoryFast(self.meas)
            ws = h2ws.MakeCombinedModel(self.meas)

        out_path = join(results_dir, out_name)
        ws.writeToFile(out_path, True)

    def do_histfitter_magic(self, ws_dir, verbose=False):
        """
        Here we break into histfitter voodoo. The functions here are pulled
        out of the HistFitter.py script. The input workspace is the one
        produced by the `save_workspace` function above.
        """
        from scharmfit import utils
        utils.load_susyfit()
        from ROOT import ConfigMgr, Util

        ws_name = self._get_ws_name()
        ws_path = join(ws_dir, ws_name)

        # The histfitter authors somehow thought that creating a
        # singleton configuration manager was good design. Maybe it is
        # when you're wrapping ROOT code (with all its global variable
        # glory). In any case, most of the hacking below is to work
        # around this.
        mgr = ConfigMgr.getInstance()
        mgr.initialize()
        mgr.setNToys(1)         # make configurable?

        # such a hack... but this is to check if the fit config is unique
        fc_number = 0
        with OutputFilter():
            # name fig configs '0', '1', '2', '3', etc...
            while mgr.getFitConfig(str(fc_number)):
                fc_number += 1
        fc = mgr.addFitConfig(str(fc_number))

        # had to dig pretty deep into the HistFitter code to find this
        # stuff, but this seems to be how it sets things up.
        fc.m_inputWorkspaceFileName = ws_path
        # HistFitter name convention seems to be that the background only fit
        # is called "Bkg" or "" (empty string).
        fc.m_signalSampleName = self._signal_point or ''

        # HistFitter doesn't seem to distinguish between background
        # and signal channels. The only possible difference is a
        # commented out line that sets 'lumiConst' to true if there
        # are no signal channels. May be worth looking into...
        for chan in self._channels:
            if chan not in self._non_fit_regions:
                fc.m_bkgConstrainChannels.push_back(chan)
            # fc.m_signalChannels.push_back(chan)

        accept_strings = {'ERROR:','WARNING:'} if not verbose else {''}
        # this snapshot error appears to be a hackish check, can ignore
        veto = {'snapshot_paramsVals_initial'}

        with OutputFilter(accept_strings=accept_strings, veto_strings=veto):
            Util.GenerateFitAndPlot(
                fc.m_name,
                "ana_name",
                False, #drawBeforeFit,
                False, #drawAfterFit,
                False, #drawCorrelationMatrix,
                False, #drawSeparateComponents,
                False, #drawLogLikelihood,
                False, #runMinos,
                "", #minosPars
                )
            # I can't get doUpperLimit to work. While that would be
            # the nicer solution, for a hack instead I'll call
            # doUpperLimitAll from another routine later.
            # mgr.doUpperLimit(fc)

            # mgr.m_outputFileName = 'upperlim.root'
            # mgr.doUpperLimitAll()


# _________________________________________________________________________
# systematic calculation (convert yields to relative systematics, etc...)

def _get_signal_systematics(rel_systs, syst_list, direction):
    """
    Return a {(region, process): sum_square, ...} dict.
    The `direction` should be 'up','down', or None.
    """
    out_dict = {}
    if not direction:
        return out_dict
    # translate version to an index in the systematic list
    idx = {'down':0, 'up':1}[direction]
    for syst in syst_list:
        for region, procdict in rel_systs[syst].iteritems():
            for proc, downup in procdict.iteritems():
                # multiply the signal by the appropriate variation.
                # we're assuming the systematics aren't correlated
                # (and using linear error prop)
                delta = downup[idx] - 1
                out_key = region, proc
                sum_sq = out_dict.get(out_key, 0.0)
                sum_sq += delta**2
                out_dict[out_key] = sum_sq
    return out_dict

def _get_relative_from_abs_systematics(base_yields, systematic_yields):
    """calculate relative systematics based on absolute values"""
    all_syst = set(systematic_yields.iterkeys())
    sym_systematics, asym_systematics = _split_systematics(all_syst)

    # the relative systematics are keyed as
    # {region: {process:{systematic: (down, up), ...}, ... }, ...}
    rel_systs = {}
    # build all the relative systematics
    for region, process_dict in base_yields.iteritems():
        rel_systs[region] = {}
        for process, vals in process_dict.iteritems():
            if process == 'data':
                continue
            nom_yield, err = vals
            rel_systs[region][process] = {}

            # start with symmetric ones
            for syst in sym_systematics:
                try:
                    varied_yield = systematic_yields[syst][region][process][0]
                except KeyError as err:
                    continue # missing means no variation
                rel_syst_err = varied_yield / nom_yield - 1.0
                rel_syst_err /= 2.0 # cut in half because it's symmetric
                rel_syst_range = ( 1 - rel_syst_err, 1 + rel_syst_err)
                rel_systs[region][process][syst] = rel_syst_range

            # now do the asymmetric systematics
            for syst in asym_systematics:
                sdown = syst + _asym_suffix_down
                sup = syst + _asym_suffix_up

                def var(sys_name):
                    """get the relative variation from sys_name"""
                    try:
                        raw = systematic_yields[sys_name][region][process][0]
                    except KeyError as err:
                        return None # missing means no variation
                    return raw / nom_yield
                updown = (var(sdown), var(sup))
                if updown == (None, None):
                    continue
                rel_systs[region][process][syst] = updown

    return rel_systs

def _combine_backgrounds(yields, combine_dict):
    """
    Combine some backgrounds in the yeilds dictionary.
    Return the resulting dictionary with the yields merged.
    """

    def rename(proc):
        for new, olds in combine_dict.items():
            if proc in olds:
                return new
        return proc

    def combine(region):
        newreg = {}
        for proc, vals in region.iteritems():
            newproc = rename(proc)
            if newproc not in newreg:
                newreg[newproc] = vals
            else:
                val = newreg[newproc][0]
                val += vals[0]
                if len(newreg[newproc]) > 1:
                    err = newreg[newproc][1]
                    err = (err**2 + vals[1]**2)**0.5
                    newreg[newproc] = [val, err]
                else:
                    newreg[newproc] = [val]
        return newreg

    nom_yields = yields[_baseline_yields_key]
    new_nom = {x:combine(y) for x, y in nom_yields.items()}
    new_systs = {}
    for syst, regdic in yields[_yield_systematics_key].items():
        new_sysreg = new_systs.setdefault(syst, {})
        for regname, procdic in regdic.items():
            new_sysreg[regname] = combine(procdic)
    return {
        _baseline_yields_key: new_nom,
        _yield_systematics_key: new_systs,
        _relative_systematics_key: yields[_relative_systematics_key]}


_asym_suffix_up = 'up'
_asym_suffix_down = 'down'

def _filter_systematics(original, requested):
    """
    Slim down 'original' dict of systematics by only allowing
    `requested` and up / down variations of `requested`.
    Return a tuple (filtered, missing), where `filtered` is the
    slimed selection, `missing` is a list of the systematics that
    weren't found.
    """
    filtered = {}
    missing = []
    ud_suffix = [_asym_suffix_down, _asym_suffix_up]
    for systn in requested:
        if systn in original:
            filtered[systn] = original[systn]
        elif all(systn + sfx in original for sfx in ud_suffix):
            for sfx in ud_suffix:
                filtered[systn + sfx] = original[systn + sfx]
        else:
            missing.append(systn)
    return filtered, missing

_missing_syst_err = "no systematic '{}' found, check your configuration."
def _filter_rel_systematics(original, requested):
    """
    Filter `original`, if all `requested` aren't found, throw exception.
    """
    filtered = {}
    for systn in requested:
        if systn in original:
            filtered[systn] = original[systn]
        else:
            raise ValueError(_missing_syst_err.format(systn))
    return filtered

def _split_systematics(systematics):
    """
    Split into symmetric and asymmetric vairations and return a tuple
    (symmetric, asymmetric).
    Works by finding the systematics with an "up" and "down" suffix,
    and calling these asymmetric.
    """
    asym = set()
    for sys in systematics:
        if sys.endswith(_asym_suffix_up):
            stem = sys[:-len(_asym_suffix_up)]
            if stem + _asym_suffix_down in systematics:
                asym.add(stem)

    asym_variations = set()
    for sys in asym:
        asym_variations.add(sys + _asym_suffix_down)
        asym_variations.add(sys + _asym_suffix_up)
    sym_systematics = set(systematics) - asym_variations
    return sym_systematics, asym

def _update_with_relative_systematics(existing, rel_systs, all_proc):
    """
    Add relative systematics to the systematics we use. Throw an
    exception if we try to overwrite.
    """
    for sys_name, region_dict in rel_systs.iteritems():
        for region_name, process_dict in region_dict.iteritems():
            exist_region = existing.setdefault(region_name, {})
            # we allow a list to be passed to the region directly
            # in which case it's applied to all processes
            try:
                for process_name, downup in process_dict.iteritems():
                    exist_process = exist_region.setdefault(process_name, {})
                    if sys_name in exist_process:
                        raise ValueError('tried to overwrite systematic')
                    exist_process[sys_name] = downup
            except AttributeError as err:
                if "object has no attribute 'iteritems'" not in str(err):
                    raise
                if not len(process_dict) == 2:
                    raise ValueError(
                        '{} not an up / down pair'.format(process_dict))
                for proc in all_proc:
                    exist_proc = exist_region.setdefault(proc, {})
                    exist_proc[sys_name] = process_dict


# __________________________________________________________________________
# helper functions

def _get_sp(proc):
    """regex search for signal points"""
    sig_finder = re.compile('scharm-([0-9]+)-([0-9]+)')
    try:
        schstr, lspstr = sig_finder.search(proc).groups()
    except AttributeError:
        return None
    # return int(schstr), int(lspstr)
    return proc

def _check_subset(subset, superset):
    """check to make sure each entry in the first arg is in the second"""
    for xx in subset:
        if not xx in superset:
            raise ValueError("{} not in {}".format(xx, ', '.join(superset)))

def _set_value(sample, value, err):
    """
    Workaround for the crashing Sample.SetValue method.

    Probably leaks memory, but good luck avoiding this with ROOT.
    $@! FURTHER EXPLETIVES REMOVED BY AUTHOR !@$
    """
    from ROOT import TH1D
    sname = sample.GetName()
    with OutputFilter():        # suppress memory leak complaint
        hist = TH1D(sname + '_hist', '', 1, 0, 1)
    hist.SetBinContent(1, value)
    hist.SetBinError(1, err)
    sample.SetHisto(hist)

def get_signal_points_and_backgrounds(all_yields):
    yields = all_yields[_baseline_yields_key]
    # assume structure {syst: {proc: <counts>, ...}, ...}
    signal_points = set()
    backgrounds = set()
    for procdic in yields.itervalues():
        for proc in procdic:
            sp = _get_sp(proc)
            if sp:
                signal_points.add(sp)
            elif proc not in {'data'}:
                backgrounds.add(proc)
    return list(signal_points), list(backgrounds)


def do_upper_limits(verbose=False, prefix='upperlim'):
    from scharmfit import utils
    utils.load_susyfit()
    from ROOT import ConfigMgr, Util
    mgr = ConfigMgr.getInstance()
    mgr.m_outputFileName = prefix + '.root'
    mgr.m_nToys = 1
    mgr.m_calcType = 2
    mgr.m_testStatType = 3
    mgr.m_useCLs = True
    mgr.m_nPoints = -1
    if verbose:
        mgr.doUpperLimitAll()
    else:
        with OutputFilter():
            mgr.doUpperLimitAll()
