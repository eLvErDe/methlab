#! /bin/sh

PONAME="methlab.po"
LANGDIR=`dirname "$0"`
POTFILE="$LANGDIR/methlab.pot"

pofiles=`find . -name "$PONAME"`
for pofile in $pofiles; do
  echo "Merging $pofile with $POTFILE"
  msgmerge -U "$pofile" "$POTFILE"
done
