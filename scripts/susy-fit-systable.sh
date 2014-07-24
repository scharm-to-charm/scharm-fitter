#!/usr/bin/env bash

OUTDIR=bg_fit
REGIONS=signal_mct150,cr_w_mct150_l1pt50,cr_z,cr_t,cr_w_mct150
SAMPLES=Wjets,Zjets,top,other

usage() {
    echo "${0##*/} [-ht] [-o <output directory>] <afterFit file>"
}
doc() {
    usage
    cat <<EOF

Wrapper on the SysTable.py and YieldsTable.py HistFitter scripts.
Writes to $OUTDIR by default.

Options:
 -t make test presentation
 -o <out_dir> set output dir
 -r reg1,reg2,etc set regions
EOF
}

while (( $# ))
do
    case $1 in
	--help) doc; exit 1;;
	-h) doc; exit 1;;
	-o) shift; OUTDIR=$1; shift;;
	-t) MKTEST=1; shift;;
	-r) shift; REGIONS=$1; shift;;
	*)
	    if [[ -n $input ]]
		then
		usage
		echo 'too many inputs'
		exit 2
	    else
		input=$1
	    fi
	    shift;;
    esac
done

if [[ -z $input ]]
then
    usage
    exit 1
fi

# __________________________________________________________________________
# run the script, print outputs

if [[ ! -d $OUTDIR ]]
then
    mkdir $OUTDIR
fi

# start with the systematics table
TABOUT=$OUTDIR/systable.tex
SysTable.py -c $REGIONS -w $input -o $TABOUT > /dev/null

YIELDOUT=$OUTDIR/yieldtable.tex
YieldsTable.py -c $REGIONS -w $input -o $YIELDOUT -s $SAMPLES > /dev/null
rm $OUTDIR/yieldtable.pickle

# also make a test presentation
TESTTABLES=/dev/null
if [[ $MKTEST ]]
    then
    TESTTABLES=$OUTDIR/test_tables.tex
fi

cat <<EOF > $TESTTABLES
\documentclass{beamer}
\useoutertheme{infolines}
\setbeamertemplate{navigation symbols}{}

\title{SysTable}
\author[$USER]{The Mystery (Wo)Man}
\institute{Yal\\\`e}
\begin{document}

\begin{tiny}
\begin{frame}
\begin{table}
EOF

cat $TABOUT >> $TESTTABLES

cat <<EOF >> $TESTTABLES

\end{table}
\end{frame}

\begin{frame}
\begin{table}
EOF

cat $YIELDOUT >> $TESTTABLES

cat <<EOF >> $TESTTABLES
\end{table}
\end{frame}
\end{tiny}
\end{document}
EOF

# replace region names
SRE='s/signal\\_mct150/Signal (\$m_{\\rm CT} > 150\\,\\text{GeV}\$)/'
WRE='s/cr\\_w\\_mct150/CRW/'
ZRE='s/cr\\_z/CRZ/'
TRE='s/cr\\_t/CRT/'
sed -i -e "$SRE" -e $WRE -e $ZRE -e $TRE $TABOUT
sed -i -e "$SRE" -e $WRE -e $ZRE -e $TRE $YIELDOUT

# write the mu table
susy-fit-results.py  $input | susy-fit-mutable.py -o $OUTDIR/mutable.tex
