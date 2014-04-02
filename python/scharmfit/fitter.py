from stop.bullshit import OutputFilter
from stop.hists import HistNd
import h5py
import os, re
from os.path import isdir, join, isfile
from collections import defaultdict, Counter
import warnings
import sqlite3

_up_down_syst = {'jes', 'u','c','b','t', 'el', 'mu', 'met'}

def path_from_sr(met_gev, pt_gev, signal_point, tag_config='conf',
            top='workspaces'):
    path_tmp = '{top}/{tag}/met{met:.0f}/pt{pt:.0f}/{sp}'
    return path_tmp.format(
        tag=tag_config, met=met_gev, pt=pt_gev, sp=signal_point, top=top)

def sr_from_path(path):
    sr_re = re.compile('([^/]*)/met([0-9]+)/pt([0-9]+)/([^/]*)')
    tag, mstr, pstr, sp = sr_re.search(path).group(1,2,3,4)
    return int(mstr), int(pstr), sp, tag

_sql_table = [
    'tag_config text',
    'met_gev integer',
    'pt_gev integer',
    'signal_point text',
    'ul_lower float',
    'ul_mean float',
    'ul_upper float']

def make_sql(name='all-fit-results.db'):
    table_spec = ','.join(_sql_table)
    with sqlite3.connect(name) as conn:
        conn.execute('create table upperlimits ({})'.format(table_spec))

def insert_sql(met_gev, pt_gev, signal_point, tag_config, upper_limits,
               name='all-fit-results.db'):
    col_names = [s.split()[0] for s in _sql_table]
    ins_tup = (
        tag_config, met_gev, pt_gev, signal_point,
        upper_limits['lower'], upper_limits['mean'], upper_limits['upper'])
    valstr = ','.join(['?']*len(ins_tup))
    with sqlite3.connect(name, timeout=900) as conn:
        conn.execute(
            "insert into upperlimits values ({})".format(valstr), ins_tup)

def _chop_ud(word):
    for chop in ['up','down']:
        if word.endswith(chop):
            return word[:-len(chop)]
    return word

def get_systematics(base_dir):
    systs = []
    for d in os.listdir(base_dir):
        if isdir(join(base_dir,d)):
            systs.append(_chop_ud(d))
    return sorted(set(systs) - {'baseline'})


class CountDict(dict):
    """
    Stores as (syst, physics, region)
    """
    def __init__(self, kin_dir, systematics='all'):

        if systematics == 'all':
            systematics = _get_systematics(kin_dir)

        def has_systematic(syst):
            if syst in systematics + ['baseline']:
                return True
            if syst.replace('up','') in systematics:
                return True
            if syst.replace('down','') in systematics:
                return True
            return False

        self.systematics = []
        for d in os.listdir(kin_dir):
            if isdir(join(kin_dir,d)):
                self.systematics.append(d)

        for syst in self.systematics:
            if not has_systematic(syst):
                continue
            tmp = defaultdict(dict)
            print 'loading {}'.format(syst)
            agg_path = join(kin_dir, syst, 'aggregate.h5')
            if not isfile(agg_path):
                raise OSError("{} not found".format(agg_path))
            with h5py.File(agg_path, 'r') as h5file:
                for phys, var_group in h5file.iteritems():
                    for var, reg_group in var_group.iteritems():
                        for region, hist in reg_group.iteritems():
                            if var == 'kinematics':
                                tmp[syst, phys, region]['sum'] = HistNd(hist)
                            elif var == 'kinematicWt2':
                                tmp[syst, phys, region]['wt2'] = HistNd(hist)
            self.update(tmp)

inf = float('inf')

class Workspace(object):
    '''
    Organizes the building of workspaces, mainly by providing functions to
    transfer from the input yaml file to a RooFit workspace.
    '''
    fixed_backgrounds = {'diboson'}
    meas_name = 'meas'
    def __init__(self, counts, systematics, backgrounds):
        import ROOT
        with OutputFilter():
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

        # we have to add the channels _after_ adding data
        # so using pseudodata means we have to save the channels
        # and add them later
        self.channels = {}

    def set_signal(self, signal_name):
        valid_signals = set(zip(*self.counts.keys())[1])
        if not signal_name in valid_signals:
            possible_sigs = '\n'.join(valid_signals)
            raise ValueError(
                '{} not in:\n {}'.format(signal_name, possible_sigs))
        if self.signal_point:
            raise ValueError('tried to overwrite {} with {}'.format(
                    self.signal_point, signal_name))
        self.signal_point = signal_name
        self.meas.SetPOI("mu_{}".format(signal_name))

    def _add_mc_to_channel(self, chan, sr, cutfunc):
        """
        Adds the signal mc and the backgrounds to this channel.
        Will throw exceptions if the signal isn't set.
        """
        if self.signal_point:
            signal = self.hf.Sample(str('_'.join([self.signal_point,sr])))
            sig_hists = self.counts['baseline', self.signal_point, sr]
            signal_count = cutfunc(sig_hists['sum'])
            signal.SetValue(signal_count)
            sig_stat_error = cutfunc(sig_hists['wt2'])**0.5
            signal.GetHisto().SetBinError(1,sig_stat_error)
            signal.SetNormalizeByTheory(True)
            signal.AddNormFactor('mu_{}'.format(self.signal_point),1,0,2)
            chan.AddSample(signal)

        for bg in self.backgrounds:
            background = self.hf.Sample('_'.join([sr,bg]))
            base_count = cutfunc(self.counts['baseline',bg,sr]['sum'])
            self.region_sums[sr] += base_count
            if base_count == 0.0:
                warn_str = ('zero base count found in {}'
                            ' skipping').format(bg)
                warnings.warn(warn_str, stacklevel=2)
                continue

            background.SetValue(base_count)
            stat_error = cutfunc(self.counts['baseline',bg,sr]['wt2'])**0.5
            background.GetHisto().SetBinError(1,stat_error)
            if not bg in self.fixed_backgrounds:
                background.AddNormFactor('mu_{}'.format(bg), 1,0,10)

            for syst in self.systematics:
                if syst in _up_down_syst:
                    sup_normed = cutfunc(
                        self.counts[syst + 'up',bg,sr]['sum'])
                    sdn_normed = cutfunc(
                        self.counts[syst + 'down',bg,sr]['sum'])

                    background.AddOverallSys(
                        syst, sup_normed / base_count,
                        sdn_normed / base_count)
                else:
                    syst_counts = cutfunc(self.counts[syst,bg,sr]['sum'])
                    rel_syst = syst_counts / base_count - 1
                    background.AddOverallSys(
                        syst, 1 - rel_syst/2, 1 + rel_syst/2)

            chan.AddSample(background)

    def add_cr(self, cr, met_cut, ljpt_cut):
        def cut_hist(hist):
            m_cut = (met_cut,inf)
            j_cut = (ljpt_cut,inf)
            return hist['met'].slice(*m_cut)['leadingJetPt'].slice(*j_cut)

        chan = self.hf.Channel(cr)
        data_count = cut_hist(self.counts['baseline','data',cr]['sum'])
        if self.do_pseudodata:
            self.pseudodata_regions[cr] = chan
        else:
            chan.SetData(data_count)
        chan.SetStatErrorConfig(0.05, "Poisson")

        self._add_mc_to_channel(chan, cr, cut_hist)

        self.channels[cr] = chan

    def add_sr(self, sr, met_cut, ljpt_cut):
        def cut_hist(hist):
            m_cut = (met_cut,inf)
            j_cut = (ljpt_cut,inf)
            return hist['met'].slice(*m_cut)['leadingJetPt'].slice(*j_cut)

        chan = self.hf.Channel(sr)
        if self.blinded:
            self.pseudodata_regions[sr] = chan
        else:
            data_count = cut_hist(self.counts['baseline','data',sr]['sum'])
            chan.SetData(data_count)
        chan.SetStatErrorConfig(0.05, "Poisson")

        self._add_mc_to_channel(chan, sr, cut_hist)

        self.channels[sr] = chan


    def save_workspace(self, results_dir='results', prefix='stop',
                       verbose=False):
        if not self.signal_point:
            self.meas.SetPOI("mu_SIG")
        if not isdir(results_dir):
            os.mkdir(results_dir)

        for chan_name, channel in self.channels.iteritems():
            if chan_name in self.pseudodata_regions:
                pseudo_count = self.region_sums[chan_name]
                channel.SetData(pseudo_count)
            self.meas.AddChannel(channel)

        self.meas.SetOutputFilePrefix(join(results_dir,prefix))
        pass_strings = ['ERROR:','WARNING:']
        if verbose:
            pass_strings.append('INFO:')
        self.meas.SetExportOnly(True)
        with OutputFilter(
            accept_re='({})'.format('|'.join(pass_strings)),
            veto_words={'nominalLumi'}):
            workspace = self.hf.MakeModelAndMeasurementFast(self.meas)

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
        from pyroot import utils
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

