"""Module containing fitting machinery"""

from scharmfit.utils import OutputFilter
import h5py
import os, re, glob
from os.path import isdir, join, isfile
from collections import defaultdict, Counter
import warnings

# NOTE: these systematics have an 'up' and 'down' variant.
# some work is needed with the b-tagging systematics: we should
# be adding the uncertainties in quadrature. As it stands, they are being
# treated as seperate parameters.
_up_down_syst = {'jes', 'u','c','b','t', 'el', 'mu', 'met'}

class Workspace(object):
    """
    Organizes the building of workspaces, mainly by providing functions to
    transfer from the input yaml file to a RooFit workspace.
    """
    # -- various definitions (for histfitter and input textfile schema)
    # histfitter
    meas_name = 'meas'

    # input file
    fixed_backgrounds = {'other'}
    baseline_syst = 'none'
    # number and error are stored as first and second entry
    _nkey = 0                  # yield
    _errkey = 1                # stat error
    def __init__(self, counts, systematics, backgrounds):
        import ROOT
        with OutputFilter(): # turn off David and Wouter's self-promotion
            self.hf = ROOT.RooStats.HistFactory

        self.counts = counts
        self.systematics = systematics
        self.backgrounds = backgrounds
        self.meas = self.hf.Measurement(self.meas_name, self.meas_name)

        self.signal_point = None
        for syst in systematics:
            self.meas.AddConstantParam('alpha_{}'.format(syst))

        self.meas.SetLumi(1.0)
        lumiError = 0.039
        self.meas.SetLumiRelErr(lumiError)
        self.meas.SetExportOnly(False)

        # for blinding / pseudodata
        self.region_sums = Counter()
        self.do_pseudodata = False
        self.blinded = True
        self.pseudodata_regions = {}

        # we have to add the channels to the measurement  _after_ adding
        # data to the channels.
        # We're using pseudodata, which means we have to save the channels
        # and add them later.
        self.channels = {}

    # ____________________________________________________________________
    # top level methods to set control / signal regions

    def add_cr(self, cr):
        chan = self.hf.Channel(cr)
        if self.do_pseudodata:
            self.pseudodata_regions[cr] = chan
        else:
            data_count = self.counts[self.baseline_syst][cr]['data']
            chan.SetData(data_count[self._nkey])
        # ACHTUNG: not at all sure what this does
        chan.SetStatErrorConfig(0.05, "Poisson")
        self._add_mc_to_channel(chan, cr)
        self.channels[cr] = chan

    def add_sr(self, sr):
        chan = self.hf.Channel(sr)
        if self.blinded:
            self.pseudodata_regions[sr] = chan
        else:
            data_count = self.counts[self.baseline_syst][sr]['data']
            chan.SetData(data_count[self._nkey])
        # ACHTUNG: again, not sure what this does
        chan.SetStatErrorConfig(0.05, "Poisson")
        self._add_mc_to_channel(chan, sr)
        self.channels[sr] = chan

    def set_signal(self, signal_name):
        if self.signal_point:
            raise ValueError('tried to overwrite {} with {}'.format(
                    self.signal_point, signal_name))
        self.signal_point = signal_name
        self.meas.SetPOI("mu_{}".format(signal_name))

    # ____________________________________________________________________
    # functions to add samples to the channel

    def _add_mc_to_channel(self, chan, region):
        """
        Adds the signal mc and the backgrounds to this channel.
        Will throw exceptions if the signal isn't set.
        """
        self._add_signal_to_channel(chan, region)

        for bg in self.backgrounds:
            self._add_background_to_channel(chan, region, bg)

    def _add_signal_to_channel(self, chan, region):
        """should be called by _add_mc_to_channel"""
        if self.signal_point:
            # get yield / stat error in SR
            baseline_syst = self.counts[self.baseline_syst]

            # signal points don't have to be saved in the yaml file
            # if they are missing it means 0.0 (both yield and stat error)
            if not self.signal_point in baseline_syst[region]:
                # warnings.warn('no signal point {} in {}, skipping'.format(
                #         self.signal_point, region), stacklevel=4)
                return

            # If we're this far, we can create the signal sample
            sname = '_'.join([self.signal_point,region])
            signal = self.hf.Sample(sname)

            # The signal yield is a list with two entries (yield, stat_error)
            sig_yield = baseline_syst[region][self.signal_point]
            signal_count = sig_yield[self._nkey]
            signal.SetValue(signal_count)
            sig_stat_error = sig_yield[self._errkey]
            signal.GetHisto().SetBinError(1,sig_stat_error)

            # this does something with lumi error... not sure what
            signal.SetNormalizeByTheory(True)

            # set a floating normalization factor
            signal.AddNormFactor('mu_{}'.format(self.signal_point),1,0,2)
            chan.AddSample(signal)

    def _add_background_to_channel(self, chan, region, bg):
        base_vals = self.counts[self.baseline_syst][region][bg]
        bg_n = base_vals[self._nkey]
        # region sums are needed for blinded results
        self.region_sums[region] += bg_n
        sname = '_'.join([region,bg])
        background = self.hf.Sample(sname)
        background.SetValue(bg_n)
        stat_error = base_vals[self._errkey]
        background.GetHisto().SetBinError(1,stat_error)
        if not bg in self.fixed_backgrounds:
            background.AddNormFactor('mu_{}'.format(bg), 1,0,2)

        # --- add systematics ---
        def get_syst_count(syst_name):
            """shortcut to get the right systematic variation"""
            return self.counts[syst_name][bg][region][self._nkey]

        for syst in self.systematics:
            if syst in _up_down_syst:
                sup_normed = get_syst_count(syst + 'up')
                sdn_normed = get_syst_count(syst + 'down')

                background.AddOverallSys(
                    syst, sup_normed / bg_n, sdn_normed / bg_n)
            else:
                syst_counts = get_syst_count(syst)
                rel_syst = syst_counts / bg_n - 1
                background.AddOverallSys(
                    syst, 1 - rel_syst/2, 1 + rel_syst/2)

        # NOTE: we'll probably have to hack in a lot more systematics here
        # by hand...

        chan.AddSample(background)

    # _________________________________________________________________
    # save the workspace

    def save_workspace(self, results_dir='results',verbose=False):
        # if we haven't set a signal point, need to set a dummy
        # (otherwise something will crash)
        if not self.signal_point:
            self.meas.SetPOI("mu_SIG")
        if not isdir(results_dir):
            os.mkdir(results_dir)

        # we actually build the measurement here
        for chan_name, channel in self.channels.iteritems():
            # add the pseudodata regions
            if chan_name in self.pseudodata_regions:
                pseudo_count = self.region_sums[chan_name]
                channel.SetData(pseudo_count)
            self.meas.AddChannel(channel)

        # don't want to save the output files in the current dir
        self.meas.SetOutputFilePrefix(join(results_dir,self.signal_point))

        # I think this turns off the fitting...
        self.meas.SetExportOnly(True)

        # NOTE: the lines immediately below could be cleaner than the
        # hack further down, but the first solution segfaults for
        # mysterious reasons. Assuming we don't _really_ care how the
        # fit works, we should just use the hack further down.  (if we
        # want to know what we're doing we shouldn't be using RooFit
        # in the first place...)

        # POSSIBLY CLEANER SOLUTION
        # from ROOT import TFile
        # h2ws = self.hf.HistoToWorkspaceFactoryFast(self.meas)
        # ws = h2ws.MakeCombinedModel(self.meas)
        # out = TFile(join(results_dir, 'combined.root'), 'recreate')
        # ws.Write()
        # out.close()

        # HACK SOLUTION (which we got from HistFitter)
        # First set up an output filter (most of the output seems pretty
        # useless).
        # There are a bunch of errors saying the nominal lumi has been
        # set twice, which seem harmless.  Also somc stuff about
        # missing a parameter of interest in the non-combined
        # workspaces, which seems harmless since we're only using the
        # combined one.
        pass_strings = ['ERROR:','WARNING:']
        filter_args = dict(
            accept_re='({})'.format('|'.join(pass_strings)),
            veto_words={
                'nominalLumi',
                "Can't find parameter of interest:"})

        with OutputFilter(**filter_args):
            workspace = self.hf.MakeModelAndMeasurementFast(self.meas)
        self._cleanup_results_dir(results_dir)

    def _cleanup_results_dir(self, results_dir):
        """Delete HistFactory byproducts that we don't need"""
        good_tmp = join(results_dir, '*_combined_{meas}_model.root')
        good_files = glob.glob(good_tmp.format(meas=self.meas_name))
        for trash in glob.glob(join(results_dir,'*')):
            if not trash in good_files:
                os.remove(trash)

class UpperLimitCalc(object):
    def __init__(self):
        """
        for now has no init...
        """
        pass
    def lim_range(self, workspace_name):
        """
        returns a 3-tuple of limits
        """
        from scharmfit import utils
        utils.load_susyfit()
        from ROOT import Util
        from ROOT import RooStats
        if not isfile(workspace_name):
            raise OSError("can't find workspace {}".format(workspace_name))
        workspace = Util.GetWorkspaceFromFile(workspace_name, 'combined')

        Util.SetInterpolationCode(workspace,4)
        with OutputFilter():
            inverted = RooStats.DoHypoTestInversion(
                workspace,
                1,                      # n_toys
                2,                      # asymtotic calculator
                3,                      # test type (3 is atlas standard)
                True,                   # use CLs
                20,                     # number of points
                0,                      # POI min
                -1,                     # POI max (why -1?)
                )

        # one might think that inverted.GetExpectedLowerLimit(-1) would do
        # something different from GetExpectedUpperLimit(-1),
        # but then one would be wrong...
        mean_limit = inverted.GetExpectedUpperLimit(0)
        lower_limit = inverted.GetExpectedUpperLimit(-1)
        upper_limit = inverted.GetExpectedUpperLimit(1)
        return lower_limit, mean_limit, upper_limit

# __________________________________________________________________________
# may not be needed

def _chop_ud(word):
    for chop in ['up','down']:
        if word.endswith(chop):
            return word[:-len(chop)]
    return word

def _path_from_sr(met_gev, pt_gev, signal_point, tag_config='conf',
            top='workspaces'):
    path_tmp = '{top}/{tag}/met{met:.0f}/pt{pt:.0f}/{sp}'
    return path_tmp.format(
        tag=tag_config, met=met_gev, pt=pt_gev, sp=signal_point, top=top)

def _sr_from_path(path):
    sr_re = re.compile('([^/]*)/met([0-9]+)/pt([0-9]+)/([^/]*)')
    tag, mstr, pstr, sp = sr_re.search(path).group(1,2,3,4)
    return int(mstr), int(pstr), sp, tag
