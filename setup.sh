#!/bin/bash

set -e

if [ "$(uname)" != "Linux" ]; then
  echo "Not on Linux!"
  echo "Maybe you're not in your VM?"
  exit
fi

# dir name from stackoverflow 59895
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

NAME="$(basename $DIR)"
NAME=${NAME##*_}
SF=~/shared
CLASS=COMSC322
CF=$SF/$CLASS

if [ ! -e $SF ]; then
  echo "Shared folder not found."
  exit
fi

if [ ! -d $CF ]; then
  if [ -e $CF ]; then
    echo "Expected $CF to be a folder, but it isn't!"
    echo "Aborting!"
    exit 1
  fi
  echo "Creating class folder for $CLASS."
  mkdir $CF
fi

if [ -e $CF/$NAME ]; then
  echo "It looks like $NAME was already set up."
  echo "If you want to set it up again, rename or delete its directory."
  echo "(It's in $CF/$NAME)"
  exit
fi

cp -iPR $DIR $CF/$NAME
cd $CF/$NAME
git init
git config user.name "comscstudent"
git config user.email "comscstudent@example.com"
git add .
git commit -m "Initial commit of $NAME"
git config --unset user.name
git config --unset user.email

if [ -e README.md ]; then
  echo
  less -P " ?f%f - %pB\% - Use arrows to scroll and 'q' to quit. " --quit-if-one-screen README.md
fi

echo
echo "*** $NAME should now be ready in $CF/$NAME ***"
