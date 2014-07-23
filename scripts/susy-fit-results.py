#!/usr/bin/env python2.7
"""
Cleaned up version of PrintFitResults, I'm mainly interested in using it
to get the fit parameters as a yaml file.
"""
from __future__ import print_function

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
        print("ERROR : Cannot open workspace : ", workspacename)
        sys.exit(1)

    result = w.obj(resultName)
    if result==None:
        print("ERROR : Cannot open fit result ", resultName)
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
    from scharmfit.utils import load_susyfit
    load_susyfit()
    from ROOT import Util, gROOT

    result = Util.GetWorkspaceFromFile(filename, 'w').obj(resultName)
    paramenters = result.floatParsFinal()
    n_par = paramenters.getSize()
    for idx1 in range(n_par):
        par1 = paramenters[idx1].GetName()
        print(par1)
        for idx2 in range(n_par):
            par2 = paramenters[idx2].GetName()
            print('{:.2f}'.format(result.correlation(par1, par2)), end=', ')
        print('...')
    print('')

if __name__ == "__main__":
    import argparse, yaml
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('after_fit_workspace')
    args = parser.parse_args()
    showAfterFitError=True
    resultName = 'RooExpandedFitResult_afterFit'
    if not showAfterFitError:
        resultName =  'RooExpandedFitResult_beforeFit'

    # get_corr_matrix(args.after_fit_workspace, resultName)
    regSys = get_fit_results(args.after_fit_workspace,resultName)
    print(yaml.dump(regSys, default_flow_style=False))

