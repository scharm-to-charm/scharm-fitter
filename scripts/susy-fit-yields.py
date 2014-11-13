#!/usr/bin/env python2.7
# -*- tab-width: 8 -*-

import ROOT
ROOT.PyConfig.IgnoreCommandLineOptions = True

from ROOT import gROOT
from scharmfit.utils import load_susyfit, OutputFilter
load_susyfit()
gROOT.Reset()

from ROOT import Util
from ROOT import RooArgSet

import os
import sys

def _get_regions(regionCat):
    regions = []
    itr = regionCat.typeIterator()
    for ncat in xrange(regionCat.numTypes()):
        regions.append(itr.Next().GetName())
    return regions

def _get_checked(w, name):
    thing = w.obj(name)
    if thing is None:
        raise ValueError('{} isnt found'.format(name))
    return thing

def _unshitify(numbers):
    regions = numbers['names']
    proc_prefix = 'Fitted_err_'
    procs = []
    for key in numbers:
        if key.startswith(proc_prefix):
            procs.append(key[len(proc_prefix):])

def latexfitresults(
    filename, sampleList, exactRegionNames=False, dataname='obsData',
    showSum=False, doAsym=True):
    workspacename = 'w'
    w = Util.GetWorkspaceFromFile(filename,'w')
    if w is None:
      sys.exit('workspace w not found')
    data_set = w.data(dataname)
    if data_set is None:
      sys.exit("ERROR : Cannot open dataset")

    resultAfterFit = _get_checked(w,'RooExpandedFitResult_afterFit')
    resultBeforeFit = _get_checked(w,'RooExpandedFitResult_beforeFit')
    regionCat = _get_checked(w,"channelCat")

    regionList = _get_regions(regionCat)

    # _________________________________________________________________________
    # code is shit from here on... should clean it up at some point

    data_set.table(regionCat).Print("v");

    print regionList
    regionFullNameList = regionList

    snapshot =  'snapshot_paramsVals_RooExpandedFitResult_afterFit'
    w.loadSnapshot(snapshot)

    if not w.loadSnapshot(snapshot):
        print "ERROR : Cannot load snapshot : ", snapshot
        sys.exit(1)

    tablenumbers = {}
    tablenumbers['names'] = regionList

    regionCatList = [
        'channelCat==channelCat::' +region for region in regionFullNameList]

    regionDatasetList = [
        data_set.reduce(regioncat) for regioncat in regionCatList]
    for index, data in enumerate(regionDatasetList):
        data.SetName("data_" + regionList[index])
        data.SetTitle("data_" + regionList[index])

    nobs_regionList = [ data.sumEntries() for data in regionDatasetList]
    #SUM
    sumNobs = 0.
    for nobs in nobs_regionList:
      sumNobs += nobs
    if showSum:
      nobs_regionList.append(sumNobs)
    tablenumbers['nobs'] = nobs_regionList

    ######
    ######
    ######  FROM HERE ON OUT WE CALCULATE THE FITTED NUMBER OF EVENTS __AFTER__ THE FIT
    ######
    ######

    # total pdf, not splitting in components
    pdfinRegionList = [ Util.GetRegionPdf(w, region)  for region in regionList]
    varinRegionList =  [ Util.GetRegionVar(w, region) for region in regionList]
    rrspdfinRegionList = []
    for index,pdf in enumerate(pdfinRegionList):
      prodList = pdf.pdfList()
      foundRRS = 0
      for idx in range(prodList.getSize()):
        if prodList[idx].InheritsFrom("RooRealSumPdf"):
          rrspdfInt =  prodList[idx].createIntegral(RooArgSet(varinRegionList[index]));
          rrspdfinRegionList.append(rrspdfInt)
          foundRRS += 1
      if foundRRS >1 or foundRRS==0:
        print " \n\n WARNING: ", pdf.GetName(), " has ", foundRRS, " instances of RooRealSumPdf"
        print pdf.GetName(), " component list:", prodList.Print("v")

    nFittedInRegionList =  [ pdf.getVal() for index, pdf in enumerate(rrspdfinRegionList)]
    pdfFittedErrInRegionList = [ Util.GetPropagatedError(pdf, resultAfterFit, doAsym) for pdf in rrspdfinRegionList]

    if showSum:
      pdfInAllRegions = RooArgSet()
      for index, pdf in enumerate(rrspdfinRegionList):
        pdfInAllRegions.add(pdf)
      pdfSumInAllRegions = RooAddition( "pdf_AllRegions_AFTER", "pdf_AllRegions_AFTER", pdfInAllRegions)
      pdfSumInAllRegions.Print()
      nPdfSumVal = pdfSumInAllRegions.getVal()
      nPdfSumError = Util.GetPropagatedError(pdfSumInAllRegions, resultAfterFit, doAsym)
      nFittedInRegionList.append(nPdfSumVal)
      pdfFittedErrInRegionList.append(nPdfSumError)

    tablenumbers['TOTAL_FITTED_bkg_events']    =  nFittedInRegionList
    tablenumbers['TOTAL_FITTED_bkg_events_err']    =  pdfFittedErrInRegionList

    # components
    for isam, sample in enumerate(sampleList):
      nSampleInRegionVal = []
      nSampleInRegionError = []
      sampleInAllRegions = RooArgSet()
      for ireg, region in enumerate(regionList):
        sampleInRegion = Util.GetComponent(w,sample,region,exactRegionNames)
        sampleInRegionVal = 0.
        sampleInRegionError = 0.
        if not sampleInRegion==None:
          sampleInRegion.Print()
          sampleInRegionVal = sampleInRegion.getVal()
          sampleInRegionError = Util.GetPropagatedError(sampleInRegion, resultAfterFit, doAsym)
          sampleInAllRegions.add(sampleInRegion)
        else:
          print " \n YieldsTable.py: WARNING: sample =", sample, " non-existent (empty) in region =",region, "\n"
        nSampleInRegionVal.append(sampleInRegionVal)
        nSampleInRegionError.append(sampleInRegionError)
      if showSum:
        sampleSumInAllRegions = RooAddition( (sample+"_AllRegions_FITTED"), (sample+"_AllRegions_FITTED"), sampleInAllRegions)
        sampleSumInAllRegions.Print()
        nSampleSumVal = sampleSumInAllRegions.getVal()
        nSampleSumError = Util.GetPropagatedError(sampleSumInAllRegions, resultAfterFit, doAsym)
        nSampleInRegionVal.append(nSampleSumVal)
        nSampleInRegionError.append(nSampleSumError)
      tablenumbers['Fitted_events_'+sample]   = nSampleInRegionVal
      tablenumbers['Fitted_err_'+sample]   = nSampleInRegionError

    print tablenumbers

    ######
    ######
    ######  FROM HERE ON OUT WE CALCULATE THE EXPECTED NUMBER OF EVENTS __BEFORE__ THE FIT
    ######
    ######

    #  FROM HERE ON OUT WE CALCULATE THE EXPECTED NUMBER OF EVENTS BEFORE THE FIT
    w.loadSnapshot('snapshot_paramsVals_RooExpandedFitResult_beforeFit')

    pdfinRegionList = [ Util.GetRegionPdf(w, region)  for region in regionList]
    varinRegionList =  [ Util.GetRegionVar(w, region) for region in regionList]
    rrspdfinRegionList = []
    for index,pdf in enumerate(pdfinRegionList):
      prodList = pdf.pdfList()
      foundRRS = 0
      for idx in range(prodList.getSize()):
        if prodList[idx].InheritsFrom("RooRealSumPdf"):

          prodList[idx].Print()
          rrspdfInt =  prodList[idx].createIntegral(RooArgSet(varinRegionList[index]))
          rrspdfinRegionList.append(rrspdfInt)
          foundRRS += 1
      if foundRRS >1 or foundRRS==0:
        print " \n\n WARNING: ", pdf.GetName(), " has ", foundRRS, " instances of RooRealSumPdf"
        print pdf.GetName(), " component list:", prodList.Print("v")

    nExpInRegionList =  [ pdf.getVal() for index, pdf in enumerate(rrspdfinRegionList)]
    pdfExpErrInRegionList = [ Util.GetPropagatedError(pdf, resultBeforeFit, doAsym)  for pdf in rrspdfinRegionList]

    if showSum:
      pdfInAllRegions = RooArgSet()
      for index, pdf in enumerate(rrspdfinRegionList):
        pdfInAllRegions.add(pdf)
      pdfSumInAllRegions = RooAddition( "pdf_AllRegions_BEFORE", "pdf_AllRegions_BEFORE", pdfInAllRegions)
      nPdfSumVal = pdfSumInAllRegions.getVal()
      nPdfSumError = Util.GetPropagatedError(pdfSumInAllRegions, resultAfterFit, doAsym)
      nExpInRegionList.append(nPdfSumVal)
      pdfExpErrInRegionList.append(nPdfSumError)

    tablenumbers['TOTAL_MC_EXP_BKG_events']    =  nExpInRegionList
    tablenumbers['TOTAL_MC_EXP_BKG_err']    =  pdfExpErrInRegionList

    for isam, sample in enumerate(sampleList):
      nMCSampleInRegionVal = []
      nMCSampleInRegionError = []
      sampleInAllRegions = RooArgSet()
      for ireg, region in enumerate(regionList):
        MCSampleInRegion = Util.GetComponent(w,sample,region,exactRegionNames)
        MCSampleInRegionVal = 0.
        MCSampleInRegionError = 0.
        if not MCSampleInRegion==None:
          MCSampleInRegionVal = MCSampleInRegion.getVal()
          MCSampleInRegionError = Util.GetPropagatedError(MCSampleInRegion, resultBeforeFit, doAsym)
          sampleInAllRegions.add(sampleInRegion)
        else:
          print " \n WARNING: sample=", sample, " non-existent (empty) in region=",region
        nMCSampleInRegionVal.append(MCSampleInRegionVal)
        nMCSampleInRegionError.append(MCSampleInRegionError)
      if showSum:
        sampleSumInAllRegions = RooAddition( (sample+"_AllRegions_MC"), (sample+"_AllRegions_MC"), sampleInAllRegions)
        nSampleSumVal = sampleSumInAllRegions.getVal()
        nSampleSumError = Util.GetPropagatedError(sampleSumInAllRegions, resultBeforeFit, doAsym)
        nMCSampleInRegionVal.append(nSampleSumVal)
        nMCSampleInRegionError.append(nSampleSumError)
      tablenumbers['MC_exp_events_'+sample]   = nMCSampleInRegionVal
      tablenumbers['MC_exp_err_'+sample]   = nMCSampleInRegionError

    map_listofkeys = tablenumbers.keys()
    map_listofkeys.sort()

    for name in map_listofkeys:
        if tablenumbers.has_key(name) :
            print name, ": ", tablenumbers[name]

    ###
    return tablenumbers

# _________________________________________________________________________
# end shit code

if __name__ == "__main__":
    import argparse, yaml
    parser = argparse.ArgumentParser()
    parser.add_argument('workspace')
    parser.add_argument('-s','--samples', nargs='+')
    args = parser.parse_args()

    with OutputFilter():
        m3 = latexfitresults(args.workspace,args.samples)
    print yaml.dump(m3)

