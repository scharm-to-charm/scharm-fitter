#!/usr/bin/env bash

OUTFILE=bg_fit.tex
REGIONS=signal_mct150,cr_w_mct150,cr_z,cr_t

usage() {
    echo "${0##*/} [-h] [-o <out file name>] <afterFit file>"
}
doc() {
    usage
    cat <<EOF

Wrapper on the SysTable.py HistFitter script. Writes to $OUTFILE by default.
EOF
}

while (( $# ))
do
    case $1 in
	--help) doc; exit 1;;
	-h) doc; exit 1;;
	--naked) NAKED=1; shift;;
	-n) NAKED=1; shift;;
	-o) shift; OUTFILE=$1; shift;;
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

mkfifo texout
SysTable.py -c $REGIONS -w $input -o texout > /dev/null &

if [[ ! $NAKED ]]
    then
    cat <<EOF > $OUTFILE
\documentclass{beamer}
\useoutertheme{infolines}
\setbeamertemplate{navigation symbols}{}

\title{SysTable}
\author[$USER]{The Mystery (Wo)Man}
\begin{document}

\begin{tiny}

EOF
    cat texout >> $OUTFILE

    cat <<EOF >> $OUTFILE

\end{tiny}

\end{document}
EOF

else
    cat texout > $OUTFILE
fi

rm texout

