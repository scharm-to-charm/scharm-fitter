import tempfile
import os, sys, re, errno
from time import time
from itertools import product
import math

def make_dir_if_none(hists_dir):
    """
    Avoids race condition from launching multiple jobs.
    """
    try:
        os.makedirs(hists_dir)
    except OSError as err:
        if err.errno == errno.EEXIST and os.path.isdir(hists_dir):
            pass
        else:
            raise

class OutputFilter(object):
    """
    Workaround filter for annoying ROOT errors.
    """
    def __init__(self, veto_words={'TClassTable'}, accept_words={},
                 accept_re=''):
        self.veto_words = set(veto_words)
        self.accept_words = set(accept_words)
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
        for line in self.temp:
            if self._should_veto(line):
                continue
            accept = set(line.split()) & self.accept_words
            if self.re is not None:
                re_found = self.re.search(line)
            else:
                re_found = False
            if accept or re_found:
                sys.stderr.write(line)

    def _should_veto(self, line):
        for veto in self.veto_words:
            if veto in line:
                return True
        return False
