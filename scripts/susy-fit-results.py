#!/usr/bin/env python2.7
"""
Cleaned up version of PrintFitResults, I'm mainly interested in using it
to get the fit parameters as a yaml file.
"""

def _dict_from_par(ip):
  return {
    'v': ip.getVal(),
    'e': ip.getError(),
    'errup': ip.getErrorLo(),
    'errdn': ip.getErrorHi()
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
    ip = fpi[idx]
    ipv  = ip.getVal()
    ipe  = ip.getError()
    ipel = ip.getErrorLo()
    ipeh = ip.getErrorHi()

    fp = fpf[idx]
    fpv  = fp.getVal()
    fpe  = fp.getError()
    fpel = fp.getErrorLo()
    fpeh = fp.getErrorHi()

    name = parname

    regSys[name] = (ipv,ipe,ipel,ipeh,fpv,fpe,fpel,fpeh)

  return regSys




##################################

# MAIN

if __name__ == "__main__":
  import os, sys
  import getopt
  def usage():
    print "Usage:"
    print "PrintFitResult.py [-c channel] [-w workspace_afterFit] [-o outputFileName]\n"
    print "Minimal set of inputs [-c channels] [-w workspace_afterFit]"
    print "*** Options are: "
    print "-c <analysis name>: single name accepted only (OBLIGATORY) "
    print "-w <workspaceFileName>: single name accepted only (OBLIGATORY) ;   if multiple channels/regions given in -c, assumes the workspace file contains all channels/regions"
    sys.exit(0)

  try:
    opts, args = getopt.getopt(sys.argv[1:], "o:c:w:m:f:s:%b")
  except:
    usage()
  if len(opts)<1:
    usage()

  outputFileName="default"
  method="1"
  showAfterFitError=True
  showPercent=False
  for opt,arg in opts:
    if opt == '-w':
      wsFileName=arg

  resultName = 'RooExpandedFitResult_afterFit'
  if not showAfterFitError:
    resultName =  'RooExpandedFitResult_beforeFit'

  regSys = get_fit_results(wsFileName,resultName)
  print regSys

