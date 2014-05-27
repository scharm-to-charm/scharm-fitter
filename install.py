#!/usr/bin/env python2.7

import site
from os.path import isfile, isdir, join, abspath, split
import os, sys
import argparse
from subprocess import Popen

def _here_path():
    return '/'.join(abspath(__file__).split('/')[:-1] + ['python'])

def _pth_file_path():
    usr_path = site.getusersitepackages()
    pth_file = join(usr_path, 'fitter.pth')
    return pth_file

def _add_path():
    pth_file_dir, pth_file = split(_pth_file_path())
    usr_path = _here_path()
    if not isdir(pth_file_dir):
        os.makedirs(pth_file_dir)
    with open(join(pth_file_dir,pth_file),'w') as pfile:
        pfile.write(_here_path())


def _rm_path():
    if isfile(_pth_file_path()):
        os.remove(_pth_file_path())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices={'install','remove'})
    args = parser.parse_args(sys.argv[1:])
    {'install': _add_path, 'remove': _rm_path}[args.action]()
    if args.action == 'install':
        Popen(['make'], cwd='src').communicate()
