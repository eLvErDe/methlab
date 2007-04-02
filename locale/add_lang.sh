#! /bin/sh

LANGDIR=`dirname $0`
POTFILE="$LANGDIR/methlab.pot"

if [ "$#" == "0" ]; then
  echo "Usage: $0 <lang> [lang]..."
fi

while [ -n "$1" ]; do
  langdir="$LANGDIR/$1"
  lang="$1"
  echo "Creating $langdir"
  mkdir "$langdir"
  echo "Copying template to $langdir"
  cp "$POTFILE" "$langdir/methlab.po"
  echo "Adding $langdir to the repository"
  svn add "$langdir"
  echo "Settings svn:ignore property on $langdir"
  echo "*.mo" > "$LANGDIR/svn-ignore.tmp"
  svn propset svn:ignore "$langdir" -F "$LANGDIR/svn-ignore.tmp"
  rm "$LANGDIR/svn-ignore.tmp"
  shift
done
