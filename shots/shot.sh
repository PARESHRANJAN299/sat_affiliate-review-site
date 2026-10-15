#!/bin/bash
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
S=/private/tmp/claude-501/-Users-datapoem-Documents-backend-system-design-architecture-dataengineering/29b63b3b-72d7-49ca-a894-d46377c9db92/scratchpad/site/shots
"$C" --headless=new --disable-gpu --hide-scrollbars --window-size=$(( $1 < 500 ? 500 : $1 )),$(( $4 + 100 )) --virtual-time-budget=5000 --screenshot=$S/$5.png "http://localhost:8765/_v.html?w=$1&p=$2&y=$3&h=$4" >/dev/null 2>&1
