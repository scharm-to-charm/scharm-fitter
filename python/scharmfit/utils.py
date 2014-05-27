import tempfile
import os, sys, re, errno
from time import time
from itertools import product
import math
from os.path import dirname

def make_dir_if_none(hists_dir):
    """
    Checking whether a directory exists and then creating it if not results
    in a race condition if you launch several jobs at once. This should
    be safer.
    """
    try:
        os.makedirs(hists_dir)
    except OSError as err:
        if err.errno == errno.EEXIST and os.path.isdir(hists_dir):
            pass
        else:
            raise

def load_susyfit(use_histfitter_version=False):
    """
    Loads the root interfaces with HistFitter
    """
    if use_histfitter_version:
        # assume libSusyFitter is in some local HistFitter package
        from distutils import spawn
        hf_path = spawn.find_executable('HistFitter.py')
        if hf_path is None:
            raise OSError("can't find HistFitter.py, is it in PATH?")
        hf = dirname(hf_path)
        lib_path = '{}/../lib'.format(hf)
    else:
        # assume that libSusyFitter.so is in this package
        import inspect
        here = inspect.getsourcefile(make_dir_if_none)
        lib_path = '{}/../../lib'.format(dirname(here))
    import ROOT
    with OutputFilter(accept_re='ERROR'):
        ROOT.gSystem.Load('{}/libSusyFitter.so'.format(lib_path))
        

class OutputFilter(object):
    """
    Workaround filter for annoying ROOT output. By default silences
    all output, but this can be modified:
     - accept_strings: print any lines that match any of these
     - accept_re: print any lines that match this regex
     - veto_strings: veto any lines that match these strings
    """
    def __init__(self, veto_strings={'TClassTable'}, accept_strings={},
                 accept_re=''):
        self.veto_words = set(veto_strings)
        self.accept_words = set(accept_strings)
        self.temp = tempfile.NamedTemporaryFile()
        if accept_re:
            self.re = re.compile(accept_re)
        else:
            self.re = None
    def __enter__(self):
        self.old_out, self.old_err = os.dup(1), os.dup(2)
        os.dup2(self.temp.fileno(), 1)
        os.dup2(self.temp.fileno(), 2)
    def __exit__(self, exe_type, exe_val, tb):
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(self.old_out, 1)
        os.dup2(self.old_err, 2)
        os.close(self.old_out)
        os.close(self.old_err)
        self.temp.seek(0)

        # dump everything if an exception was thrown
        if exe_type is not None:
            for line in self.temp:
                sys.stderr.write(line)
            return False

        # if no exception is thrown only dump important lines
        for line in self.temp:
            if self._should_veto(line):
                continue
            accept = self._should_accept(line)
            if self.re is not None:
                re_found = self.re.search(line)
            else:
                re_found = False
            if accept or re_found:
                sys.stderr.write(line)

    def _should_accept(self, line):
        for phrase in self.accept_words:
            if phrase in line:
                return True
        return False

    def _should_veto(self, line):
        for veto in self.veto_words:
            if veto in line:
                return True
        return False
