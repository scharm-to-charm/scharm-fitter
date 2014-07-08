#!/usr/bin/env python2.7

def die():
    import ROOT
    hf = ROOT.RooStats.HistFactory
    chan = hf.Channel('chan')
    chan.SetData(10)
    bg = hf.Sample('somesample')
    hist = ROOT.TH1D('fuck','root', 1, 0, 1)
    hist.SetBinContent(1, 10)
    bg.SetHisto(hist)
    chan.AddSample(bg)
    print 'done, no segfault!'

if __name__ == '__main__':
    die()

