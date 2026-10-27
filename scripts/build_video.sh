#!/usr/bin/env bash
# Assemble the submission video: title card (problem + user) + recorded walkthrough + architecture card.
# Needs docs/demo/walkthrough.webm from scripts/record_demo.mjs. Output: docs/demo/final.mp4 (1280x720, 30fps, silent).
set -euo pipefail
cd "$(dirname "$0")/.."
D=docs/demo
node scripts/cards.mjs
still() { ffmpeg -loglevel error -y -loop 1 -i "$1" -t "$2" -r 30 -c:v libx264 -pix_fmt yuv420p -vf scale=1280:720 "$3"; }
still $D/_intro.png 14 $D/_intro.mp4
still $D/_arch.png 16 $D/_arch.mp4
ffmpeg -loglevel error -y -i $D/walkthrough.webm -c:v libx264 -pix_fmt yuv420p -r 30 -crf 20 -an $D/_walk.mp4
printf "file '_intro.mp4'\nfile '_walk.mp4'\nfile '_arch.mp4'\n" > $D/_list.txt
ffmpeg -loglevel error -y -f concat -safe 0 -i $D/_list.txt -c:v libx264 -pix_fmt yuv420p -r 30 -crf 20 $D/final.mp4
rm -f $D/_list.txt
ffprobe -v error -show_entries format=duration -of csv=p=0 $D/final.mp4
