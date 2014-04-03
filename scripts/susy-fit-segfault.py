#!/usr/bin/env python2.7

def die():
    import ROOT
    hf = ROOT.RooStats.HistFactory
    chan = hf.Channel('zork')
    chan.SetData(10)
    bg = hf.Sample('trash')
    bg.SetValue(10)
    chan.AddSample(bg)
    print 'done, no segfault!'

if __name__ == '__main__':
    die()

