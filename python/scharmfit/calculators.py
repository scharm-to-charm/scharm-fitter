"""routines to turn workspaces into CLs, upper limits, etc"""

from scharmfit.utils import OutputFilter
from os.path import isfile

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
            return {'obs_u1s':limits.GetCLs()}
        elif ws_type == self.down1s:
            return {'obs_d1s':limits.GetCLs()}
        # should never get here
        raise ValueError('can\'t classify {} as type of limit'.format(
                workspace_name))

