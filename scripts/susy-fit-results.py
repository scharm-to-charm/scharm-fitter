#!/usr/bin/env python2.7
import ROOT
ROOT.PyConfig.IgnoreCommandLineOptions = True
from ROOT import gROOT,gSystem,gDirectory

from scharmfit.utils import load_susyfit
load_susyfit()
# from ROOT import ConfigMgr,FitConfig #this module comes from gSystem.Load("libSusyFitter.so")
gROOT.Reset()

from ROOT import TFile, RooWorkspace, TObject, TString, RooAbsReal, RooRealVar, RooFitResult, RooDataSet, RooAddition, RooArgSet,RooAbsData,RooRandom 
from ROOT import Util, TMath
from ROOT import RooFit
from ROOT import RooExpandedFitResult
    
import os
import sys
from sys import exit

import pickle


  

def latexfitresults( filename, resultName="RooExpandedFitResult_afterFit", outName="test.tex" ):

  ############################################
  workspacename = 'w'
  w = Util.GetWorkspaceFromFile(filename,workspacename)

  if w==None:
    print "ERROR : Cannot open workspace : ", workspacename
    sys.exit(1) 

  result = w.obj(resultName)
  if result==None:
    print "ERROR : Cannot open fit result ", resultName
    sys.exit(1)

  #####################################################

  regSys = {}

  # calculate error per parameter on  fitresult
  fpf = result.floatParsFinal() 
  fpi = result.floatParsInit()

  '''
  // P r i n t   l a t ex   t a b l e   o f   p a r a m e t e r s   o f   p d f 
  // --------------------------------------------------------------------------


  // Print parameter list in LaTeX for (one column with names, one column with values)
  params->printLatex() ;

  // Print parameter list in LaTeX for (names values|names values)
  params->printLatex(Columns(2)) ;

  // Print two parameter lists side by side (name values initvalues)
  params->printLatex(Sibling(*initParams)) ;

  // Print two parameter lists side by side (name values initvalues|name values initvalues)
  params->printLatex(Sibling(*initParams),Columns(2)) ;

  // Write LaTex table to file
  params->printLatex(Sibling(*initParams),OutputFile("rf407_latextables.tex")) ;
  '''

  ####fpf.printLatex(RooFit.Format("NE",RooFit.AutoPrecision(2),RooFit.VerbatimName()),RooFit.Sibling(fpi),RooFit.OutputFile(outName)) 

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

  wsFileName='/results/MyOneLeptonKtScaleFit_HardLepR17_BkgOnlyKt_combined_NormalMeasurement_model_afterFit.root'
  try:
    opts, args = getopt.getopt(sys.argv[1:], "o:c:w:m:f:s:%b")
  except:
    usage()
  if len(opts)<1:
    usage()

  analysisName = ''
  outputFileName="default"
  method="1"
  showAfterFitError=True
  showPercent=False
  for opt,arg in opts:
    if opt == '-c':
      analysisName=arg
    if opt == '-w':
      wsFileName=arg

  resultName = 'RooExpandedFitResult_afterFit'
  if not showAfterFitError:
    resultName =  'RooExpandedFitResult_beforeFit'

  regSys = latexfitresults(wsFileName,resultName,outputFileName)

  line_chanSysTight = str(regSys) + analysisName

  outputFileName = "fitresult_" + analysisName + ".tex"
  
  f = open(outputFileName, 'w')
  f.write( line_chanSysTight )
  f.close()
  print "\nwrote results in file: %s"%(outputFileName)

