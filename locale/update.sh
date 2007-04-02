#! /bin/sh

BASEDIR="`dirname "$0"`/.."

pushd $BASEDIR > /dev/null

LANGDIR=locale

echo "Generating file-lists"
find "pymethlab" -iname "*.glade" | sort > "$LANGDIR/glade.sources"
echo "methlab" > "$LANGDIR/python.sources"
find "pymethlab" -iname "*.py" | sort >> "$LANGDIR/python.sources"

POTFILE="$LANGDIR/methlab.pot"
echo "Generating translation template $POTFILE"
xgettext -o "$POTFILE" -L Glade -f "$LANGDIR/glade.sources"
xgettext -j -o "$POTFILE" -L Python -f "$LANGDIR/python.sources"

rm "$LANGDIR/glade.sources" "$LANGDIR/python.sources"

popd > /dev/null
