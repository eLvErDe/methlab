#! /bin/sh

POFILE=methlab.po
MOFILE=methlab.mo

pofiles=`find . -name "$POFILE"`
for pofile in $pofiles; do
  mofile=${pofile/$POFILE/$MOFILE}
  echo "Compiling $pofile to $mofile"
  msgfmt "$pofile" -o "$mofile"
done
