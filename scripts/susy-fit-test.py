#!/usr/bin/env python2.7

def die():
    import ROOT
    hf = ROOT.RooStats.HistFactory
    chan = hf.Channel('chan')
    bg = hf.Sample('somesample')
    hist = ROOT.TH1D('fuck','root', 1, 0, 1)
    hist.SetBinContent(1, 10)
    hist.SetBinError(1,10)
    bg.SetHisto(hist)
    bg.AddOverallSys('dicks', 0.0, 2.0)
    bg.ActivateStatError()
    chan.AddSample(bg)
    chan.SetData(10)
    meas = hf.Measurement('blork','fuck')
    meas.AddChannel(chan)
    meas.SetPOI('mu_SIG')
    meas.SetExportOnly(True)
    meas.SetLumi(1.0)
    meas.SetLumiRelErr(0.039)
    hf.MakeModelAndMeasurementFast(meas)
    print 'done, no segfault!'

if __name__ == '__main__':
    die()

