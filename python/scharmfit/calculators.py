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
        pass
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
        return dict(
            cls=limit.GetCLs(),
            cls_exp=limit.GetCLsexp(),
            cls_up_1_sigma=limit.GetCLsu1S(),
            cls_down_1_sigma=limit.GetCLsd1S(),
            cls_up_2_sigma=limit.GetCLsu2S(),
            cls_down_2_sigma=limit.GetCLsd2S())


