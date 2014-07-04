#!/usr/bin/env bash

usage() {
    echo "${0##*/} [-h] <afterFit file>"
}
doc() {
    usage
    cat <<EOF

Wrapper on the SysTable.py HistFitter script
EOF
}

while (( $# ))
do
    case $1 in
	--help) doc; exit 1;;
	-h) doc; exit 1;;
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

cat <<EOF > bg_fit.tex
\documentclass{beamer}
\useoutertheme{infolines}
\setbeamertemplate{navigation symbols}{}

\title{SysTable}
\author[$USER]{The Mystery (Wo)Man}
\begin{document}

\begin{tiny}

EOF

mkfifo texout
SysTable.py -c signal_mct150,cr_w_mct150,cr_z,cr_t -w $input -o texout &
cat texout >> bg_fit.tex
rm texout

cat <<EOF >> bg_fit.tex

\end{tiny}

\end{document}
EOF
