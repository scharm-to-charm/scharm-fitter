"""Module containing fitting machinery"""

from scharmfit.utils import OutputFilter
import h5py
import os, re, glob
from os.path import isdir, join, isfile
from collections import defaultdict, Counter
import warnings
from itertools import chain

# NOTE: these systematics have an 'up' and 'down' variant.
# some work is needed with the b-tagging systematics: we should
# be adding the uncertainties in quadrature. As it stands, they are being
# treated as seperate parameters.
_up_down_syst = {'jes', 'u','c','b','t', 'el', 'mu', 'met'}
_baseline_yields_key = 'nominal_yields'
_yield_systematics_key = 'yield_systematics'

class Workspace(object):
    """
    Organizes the building of workspaces, mainly by providing functions to
    transfer from the input yaml file to a RooFit workspace.
    """
    # -- various definitions (for histfitter and input textfile schema)
    # histfitter
    meas_name = 'meas'

    # input file schema
    fixed_backgrounds = {'other'}
    baseline_yields_key = _baseline_yields_key
    yield_systematics_key = _yield_systematics_key
    # number and error are stored as first and second entry
    _nkey = 0                  # yield
    _errkey = 1                # stat error
    def __init__(self, yields, backgrounds):
        import ROOT
        with OutputFilter(): # turn off David and Wouter's self-promotion
            self.hf = ROOT.RooStats.HistFactory

        self._yields = yields[self.baseline_yields_key]
        # HistFactory actually wants all the systematics as relative
        # systematics, we convert them here.  the relative systematics
        # are keyed as
        # {region: {process:{systematic: (down, up), ...}, ... }, ...}
        yield_systematics = yields[self.yield_systematics_key]
        self._systematics = _get_relative_systematics(
            self._yields, yield_systematics)
        self.backgrounds = backgrounds

        # create / configure the measurement
        self.meas = self.hf.Measurement(self.meas_name, self.meas_name)

        # ACHTUNG: I we get errors about nom_alpha_* parameters being
        # defined multiple times when I turn these lines off, but
        # setting the parameters as constant definitely isn't the
        # right way to solve the problem. For now we'll just filter
        # these errors they seem harmless.
        #
        # for syst in chain(*_split_systematics(yield_systematics)):
        #     syst_parameter_name = 'alpha_{}'.format(syst)
        #     self.meas.AddConstantParam(syst_parameter_name)
        self.meas.SetLumi(1.0)
        lumiError = 0.039       # NOTE: check this (or make configurable)
        self.meas.SetLumiRelErr(lumiError)
        # # SEE ABOVE
        # self.meas.AddConstantParam("Lumi")
        # for bg in self.backgrounds:
        #     if not bg in self.fixed_backgrounds:
        #         self.meas.AddConstantParam('mu_{}'.format(bg))
        self.meas.SetExportOnly(True)

        self.signal_point = None
        # for blinding / pseudodata
        self.region_sums = Counter()
        self.do_pseudodata = False
        self.blinded = True
        self.pseudodata_regions = {}

        # we have to add the channels to the measurement _after_
        # adding data to the channels.  We're using pseudodata, which
        # means we have to save the channels and add them later.
        self.channels = {}

        self.debug = False

    # ____________________________________________________________________
    # top level methods to set control / signal regions
    def add_cr(self, cr):
        chan = self.hf.Channel(cr)
        if self.do_pseudodata:
            self.pseudodata_regions[cr] = chan
        else:
            data_count = self._yields[cr]['data']
            chan.SetData(data_count[self._nkey])
        # ACHTUNG: not at all sure what this does
        # chan.SetStatErrorConfig(0.05, "Gaussian")
        self._add_mc_to_channel(chan, cr)
        self.channels[cr] = chan

    def add_sr(self, sr):
        chan = self.hf.Channel(sr)
        if self.blinded:
            self.pseudodata_regions[sr] = chan
        else:
            data_count = self._yields[sr]['data']
            chan.SetData(data_count[self._nkey])
        # ACHTUNG: again, not sure what this does
        # chan.SetStatErrorConfig(0.05, "Gaussian")
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
            yields = self._yields

            # signal points don't have to be saved in the yaml file
            # if they are missing it means 0.0 (both yield and stat error)
            if not self.signal_point in yields[region]:
                return

            # If we're this far, we can create the signal sample
            sname = '_'.join([self.signal_point,region])
            signal = self.hf.Sample(sname)

            # The signal yield is a list with two entries (yield, stat_error)
            sig_yield = yields[region][self.signal_point]
            signal_count = sig_yield[self._nkey]
            signal.SetValue(signal_count)
            sig_stat_error = sig_yield[self._errkey]
            signal.GetHisto().SetBinError(1,sig_stat_error)
            # TODO: see if we need to call ActivateStatError(). For
            # now it's commented out because it makes the code
            # crash...

            # signal.ActivateStatError()

            # this does something with lumi error... not sure what
            signal.SetNormalizeByTheory(True)

            # set a floating normalization factor
            signal.AddNormFactor('mu_{}'.format(self.signal_point),1,0,2)

            # --- add systematics ---
            syst_dict = self._systematics[region][self.signal_point]
            for syst, var in syst_dict.iteritems():
                signal.AddOverallSys(syst, *var)

            chan.AddSample(signal)

    def _add_background_to_channel(self, chan, region, bg):
        base_vals = self._yields[region][bg]
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

        background.SetNormalizeByTheory(False)
        # SEE ABOVE COMMENT on ActivateStatError
        # background.ActivateStatError()
        # --- add systematics ---
        syst_dict = self._systematics[region][bg]
        for syst, var in syst_dict.iteritems():
            background.AddOverallSys(syst, *var)

        chan.AddSample(background)

    # _________________________________________________________________
    # save the workspace

    def save_workspace(self, results_dir, verbose=False):
        # if we haven't set a signal point, need to set a dummy
        # (otherwise something will crash)
        if not self.signal_point:
            self.meas.SetPOI("mu_SIG")
        if not isdir(results_dir):
            os.mkdir(results_dir)

        # we actually build the measurement here (couldn't be done earlier
        # because we needed to calculate pseudo-data)
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
        # # both the below methods segfault...
        # # method 1
        # ws.writeToFile(join(results_dir, 'combined.root'), True)
        # # method 2
        # out = TFile(join(results_dir, 'combined.root'), 'recreate')
        # ws.Write()
        # out.close()

        # HACK SOLUTION (which we got from HistFitter)
        # First set up an output filter (most of the output seems
        # pretty useless).  There are a bunch of errors saying the
        # nominal lumi has been set twice, which seem harmless.  Also
        # somc stuff about missing a parameter of interest in the
        # non-combined workspaces, which seems harmless since we're
        # only using the combined one.
        pass_strings = ['ERROR:','WARNING:']
        veto_strings={
            'ERROR argument with name nominalLumi',
            'ERROR argument with name nom_alpha_',
            "Can't find parameter of interest:"}
        filter_args = dict(
            accept_re='({})'.format('|'.join(pass_strings)),
            veto_strings=veto_strings)

        if self.debug:
            self.meas.PrintTree()
            self.meas.PrintXML(results_dir)
            self.hf.MakeModelAndMeasurementFast(self.meas)
        else:
            with OutputFilter(**filter_args):
                self.hf.MakeModelAndMeasurementFast(self.meas)

            # The above line makes several files. It's not obvious
            # that they are all needed. This deletes the extra files.
            self._cleanup_results_dir(results_dir)

    def _cleanup_results_dir(self, results_dir):
        """
        Delete HistFactory byproducts that we don't need.
        At this point it's not clear what we do and don't need...
        """
        good_tmp = join(results_dir, '*_combined_{meas}_model.root')
        good_files = glob.glob(good_tmp.format(meas=self.meas_name))
        for trash in glob.glob(join(results_dir,'*')):
            if not trash in good_files:
                os.remove(trash)

    def do_histfitter_magic(self, input_workspace):
        """
        Here we break into histfitter voodoo. What this actually does
        is one of the great mysteries of science.
        """
        from scharmfit import utils
        utils.load_susyfit()
        from ROOT import ConfigMgr, Util
        mgr = ConfigMgr.getInstance()
        mgr.initialize()
        mgr.setNToys(1)

        fc = mgr.addFitConfig("nothing")
        fc.m_inputWorkspaceFileName = input_workspace
        for chan in self.channels:
            if chan == 'signal':
                continue
            fc.m_bkgConstrainChannels.push_back(chan)
        fc.m_signalChannels.push_back('signal')

        Util.GenerateFitAndPlot(
            fc.m_name,
            "ana_name",
            True, #drawBeforeFit,
            True, #drawAfterFit,
            False, #drawCorrelationMatrix,
            False, #drawSeparateComponents,
            False, #drawLogLikelihood,
            False, #runMinos,
            "", #minosPars
            )


# stuff to calculate systematics in a format HistFactory likes
def _get_relative_systematics(base_yields, systematic_yields):
    """calculate relative systematics based on absolute values"""
    all_syst = set(systematic_yields.iterkeys())
    sym_systematics, asym_systematics = _split_systematics(all_syst)

    # the relative systematics are keyed as
    # {region: {process:{systematic: (down, up), ...}, ... }, ...}
    rel_systs = {}
    # build all the relative systematics
    for region, process_dict in base_yields.iteritems():
        rel_systs[region] = {}
        for process, (nom_yield, err) in process_dict.iteritems():
            if process == 'data':
                continue
            rel_systs[region][process] = {}

            # start with symmetric ones
            for syst in sym_systematics:
                varied_yield = systematic_yields[syst][region][process][0]
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
                    raw = systematic_yields[sys_name][region][process][0]
                    return raw / nom_yield

                rel_systs[region][process][syst] = (var(sdown), var(sup))

    # NOTE: we'll probably have to hack in a lot more systematics here
    # by hand...

    # TODO: merge the b-tagging systematics as is recommended by
    # the b-tagging group (sum of squares)
    return rel_systs


_asym_suffix_up = 'up'
_asym_suffix_down = 'down'
def _split_systematics(systematics):
    """
    Split into symmetric and asymmetric vairations.
    Find the systematics with an "up" and "down" version, call these
    asymmetric.
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

# __________________________________________________________________________
# limit calculators

class UpperLimitCalc(object):
    """Calculates the upper limit min, mean, and max values"""
    def __init__(self):
        """
        for now has no init... In the future we may set things like
        the fit method (use toys, asymptotic, CLs vs whatever...)
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
        # NOTE: We're completely silencing the fitter. Add an empty string
        # to the accept_strings to get all output.
        with OutputFilter(accept_strings={}):
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

        # one might think that inverted.GetExpectedLowerLimit(-1)
        # would do something different from GetExpectedUpperLimit(-1).
        # This doesn't seem to be true, from what I can tell both
        # functions do exactly the same thing.
        mean_limit = inverted.GetExpectedUpperLimit(0)
        lower_limit = inverted.GetExpectedUpperLimit(-1)
        upper_limit = inverted.GetExpectedUpperLimit(1)
        return lower_limit, mean_limit, upper_limit

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


