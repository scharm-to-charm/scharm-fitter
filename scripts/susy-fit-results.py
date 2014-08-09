#!/usr/bin/env python2.7
"""
Cleaned up version of PrintFitResults, I'm mainly interested in using it
to get the fit parameters as a yaml file.
"""

_cormat_key = 'correlation_matrix'
_par_key = 'parameters'
_mat_key = 'matrix'

def _dict_from_par(ip):
    return {
        'value': ip.getVal(),
        'error': ip.getError(),
        # there are these other guys, but not sure anyone cares...
        # 'unctdn': ip.getErrorLo(),
        # 'unctup': ip.getErrorHi()
      }

def get_fit_results( filename, resultName="RooExpandedFitResult_afterFit"):
    from scharmfit.utils import load_susyfit
    load_susyfit()

    from ROOT import Util, gROOT

    gROOT.Reset()

    workspacename = 'w'
    w = Util.GetWorkspaceFromFile(filename,workspacename)

    if w==None:
        print "ERROR : Cannot open workspace : ", workspacename
        sys.exit(1)

    result = w.obj(resultName)
    if result==None:
        print "ERROR : Cannot open fit result ", resultName
        sys.exit(1)

    # calculate error per parameter on  fitresult
    fpf = result.floatParsFinal()
    fpi = result.floatParsInit()

    regSys = {}

    # set all floating parameters constant
    for idx in range(fpf.getSize()):
        parname = fpf[idx].GetName()
        regSys[parname] = {
            'before': _dict_from_par(fpi[idx]),
            'after': _dict_from_par(fpf[idx]),
            }
    return regSys

def get_corr_matrix( filename, resultName="RooExpandedFitResult_afterFit"):
    """
    Returns (list_of_parameters, matrix) tuple.

    The matrix is a nested list, such that matrix[1][0] will give the
    correlation between parameter 1 and 2.
    """
    from scharmfit.utils import load_susyfit
    load_susyfit()
    from ROOT import Util, gROOT

    result = Util.GetWorkspaceFromFile(filename, 'w').obj(resultName)
    paramenters = result.floatParsFinal()
    n_par = paramenters.getSize()
    par_names = [paramenters[iii].GetName() for iii in xrange(n_par)]
    matrix_list = []
    for par1 in par_names:
        matrix_list.append([])
        for par2 in par_names:
            corr = result.correlation(par1, par2)
            matrix_list[-1].append(corr)
    return par_names, matrix_list

if __name__ == "__main__":
    import argparse, yaml
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('after_fit_workspace')
    args = parser.parse_args()
    showAfterFitError=True
    resultName = 'RooExpandedFitResult_afterFit'
    if not showAfterFitError:
        resultName =  'RooExpandedFitResult_beforeFit'

    regSys = get_fit_results(args.after_fit_workspace,resultName)
    sys.stdout.write(yaml.dump(regSys, default_flow_style=False))
    sys.stdout.flush()

    parameter_names, corr_matrix = get_corr_matrix(
        args.after_fit_workspace, resultName)
    cormat = {_cormat_key: {
        _par_key: parameter_names, _mat_key : corr_matrix}}
    sys.stdout.write(yaml.dump(cormat, default_flow_style=None))

