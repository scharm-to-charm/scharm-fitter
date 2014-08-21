#!/usr/bin/env python2.7
"""
Make tables of fit parameters
"""

import argparse, yaml, sys

def _get_fit_pars(fit_parameters):
    if not fit_parameters and not sys.stdin.isatty():
        return yaml.load(sys.stdin)

    with open(fit_parameters) as pars:
        return yaml.load(pars)

_norm_factor_head = r"""
\begin{center}
\begin{tabular}{|l|c|}
\hline
{\bf Normalisation factor}  & Value \\
\hline"""
_norm_factor_tmp = r"""
luminosity & ${l:.2f} \pm {el:.2f}$ \\
top        & ${t:.2f} \pm {et:.2f}$ \\
$Z$ + jets & ${z:.2f} \pm {ez:.2f}$ \\
$W$ + jets & ${w:.2f} \pm {ew:.2f}$ \\
\hline"""
_norm_factor_tail = r"""
\end{tabular}
\end{center}
"""

def _get_mu_table(pars):
    def val(key):
        return pars['mu_' + key]['after']['value']
    def err(key):
        return pars['mu_' + key]['after']['error']
    mu_table = _norm_factor_head
    mu_table += _norm_factor_tmp.format(
        l=pars['Lumi']['after']['value'],
        el=pars['Lumi']['after']['error'],
        t=val('top'), et=err('top'),
        z=val('Zjets'), ez=err('Zjets'),
        w=val('Wjets'), ew=err('Wjets'))
    mu_table += _norm_factor_tail
    return mu_table[1:]

if __name__ == "__main__":
    import argparse, yaml
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fit_parameters', nargs='?')
    parser.add_argument('-o', '--out-file')
    args = parser.parse_args()
    pars = _get_fit_pars(args.fit_parameters)
    table = _get_mu_table(pars)
    if args.out_file:
        with open(args.out_file, 'w') as out:
            out.write(table)
    else:
        sys.stdout.write(table)
