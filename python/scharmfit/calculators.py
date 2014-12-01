"""routines to turn workspaces into CLs, upper limits, etc"""

from scharmfit.utils import OutputFilter
from os.path import isfile

# __________________________________________________________________________
# limit calculators

class UpperLimitCalc(object):
    """Calculates the upper limit min, mean, and max values"""
    def __init__(self, n_toys=0, do_prefit=False):
        self._n_toys = n_toys
        # use asymptotic (calc type 2) if we're not using toys
        self._calc_type = 0 if n_toys else 2
        self._do_prefit = do_prefit

    def _prefit_ul(self, workspace):
        Util.SetInterpolationCode(workspace,4)

        with OutputFilter(accept_strings={}):
            inverted = RooStats.DoHypoTestInversion(
                workspace,
                1,
                2,              # use asymptotic
                3,              # test type (3 is atlas standard)
                True,           # use CLs
                20,             # number of points
                0,              # POI min
                -1,             # POI max (why -1?)
                )

        try:
            return inverted.GetExpectedUpperLimit(2)
        except ReferenceError:
            return -1

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

        # using -1 as the poi max means auto range (I think)
        poi_max = self._prefit_ul(workspace) if self._do_prefit else -1

        # NOTE: We're completely silencing the fitter. Add an empty string
        # to the accept_strings to get all output.
        with OutputFilter(accept_strings={}):
            inverted = RooStats.DoHypoTestInversion(
                workspace,
                self._n_toys,
                self._calc_type,
                3,                      # test type (3 is atlas standard)
                True,                   # use CLs
                20,                     # number of points
                0,                      # POI min
                poi_max,
                )

        try:
            mean_limit = inverted.GetExpectedUpperLimit(0)
            lower_limit = inverted.GetExpectedUpperLimit(-1)
            upper_limit = inverted.GetExpectedUpperLimit(1)
        except ReferenceError:
            return -1, -1, -1
        return lower_limit, mean_limit, upper_limit

    def observed_upper_limit(self, workspace_name):
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
                self._n_toys,
                self._calc_type,
                3,                      # test type (3 is atlas standard)
                True,                   # use CLs
                20,                     # number of points
                0,                      # POI min
                -1,
                )

        try:
            return inverted.UpperLimit()
        except ReferenceError:
            return -1

class CLsCalc(object):
    """Calculates the CLs"""
    def __init__(self):
        """
        for now has no init... In the future we may set things like
        the fit method (use toys, asymptotic, CLs vs whatever...)
        """
        # magic strings, found on the end of filenames
        self.nominal = 'nominal'
        self.up1s = 'up1sigma'
        self.down1s = 'down1sigma'

    def calculate_cls(self, workspace_name):
        """
        returns a dictionary of CLs values
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
            limit = RooStats.get_Pvalue(
                workspace,
                True,                   # doUL
                1,                      # n_toys
                2,                      # asymtotic calculator
                3,                      # test type (3 is atlas standard)
                )
        ws_type = workspace_name.rsplit('_',1)[1].split('.')[0]
        if ws_type == self.nominal:
            return {
                'obs':limit.GetCLs(),
                'exp':limit.GetCLsexp(),
                'exp_u1s':limit.GetCLsu1S(),
                'exp_d1s':limit.GetCLsd1S(),
                }
        elif ws_type == self.up1s:
            return {'obs_u1s':limit.GetCLs()}
        elif ws_type == self.down1s:
            return {'obs_d1s':limit.GetCLs()}
        # should never get here
        raise ValueError('can\'t classify {} as type of limit'.format(
                workspace_name))

