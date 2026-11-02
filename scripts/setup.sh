#!/bin/sh
# talking-head-reel setup for macOS.
#   sh scripts/setup.sh            check only: says what is missing, changes nothing
#   sh scripts/setup.sh --install  installs what is missing: ffmpeg, whisper-cpp and uv with Homebrew, and the
#                                  whisper model ggml-small.en.bin (~466 MB) into ~/.cache/talking-head-reel/
# Homebrew and Google Chrome are never installed by this script; it prints how instead.
MODEL_DIR="$HOME/.cache/talking-head-reel"
MODEL="$MODEL_DIR/ggml-small.en.bin"
MODEL_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin"
INSTALL=0; [ "$1" = "--install" ] && INSTALL=1
missing=0

say() { printf '%-16s %s\n' "$1" "$2"; }

[ "$(uname)" = "Darwin" ] || { echo "This skill expects macOS (system fonts, Chrome, Homebrew)."; exit 1; }

if command -v brew >/dev/null 2>&1; then say "homebrew" "ok"; else
  say "homebrew" "MISSING: install it from https://brew.sh (the user runs that command), then rerun"; missing=1; fi

for pair in ffmpeg:ffmpeg ffprobe:ffmpeg whisper-cli:whisper-cpp uv:uv; do
  bin=${pair%%:*}; formula=${pair##*:}
  if command -v "$bin" >/dev/null 2>&1; then say "$bin" "ok ($(command -v "$bin"))"
  elif [ $INSTALL = 1 ] && command -v brew >/dev/null 2>&1; then
    say "$bin" "installing: brew install $formula"; brew install "$formula" >/dev/null && say "$bin" "installed"
  else say "$bin" "MISSING (brew install $formula)"; missing=1; fi
done

if [ -d "/Applications/Google Chrome.app" ] || [ -d "$HOME/Applications/Google Chrome.app" ]; then say "google chrome" "ok"
else say "google chrome" "MISSING: install Chrome (https://www.google.com/chrome or brew install --cask google-chrome)"; missing=1; fi

if [ -n "$WHISPER_MODEL" ] && [ -f "$WHISPER_MODEL" ]; then say "whisper model" "ok ($WHISPER_MODEL)"
elif [ -f "$MODEL" ]; then say "whisper model" "ok ($MODEL)"
elif [ -f "$HOME/models/whisper/ggml-small.en.bin" ]; then say "whisper model" "ok ($HOME/models/whisper/ggml-small.en.bin)"
elif [ $INSTALL = 1 ]; then
  mkdir -p "$MODEL_DIR" && say "whisper model" "downloading ~466 MB from huggingface.co (ggerganov/whisper.cpp)"
  curl -L --fail --progress-bar -o "$MODEL.part" "$MODEL_URL" && mv "$MODEL.part" "$MODEL" && say "whisper model" "ok ($MODEL)"
else say "whisper model" "MISSING ($MODEL, ~466 MB download)"; missing=1; fi

for f in "Avenir Next Condensed.ttc"; do
  if [ -f "/System/Library/Fonts/$f" ] || [ -f "/System/Library/Fonts/Supplemental/$f" ]; then say "system font" "ok ($f)"
  else say "system font" "missing $f: labels will fall back to another condensed sans"; fi
done

free=$(df -g "$HOME" | awk 'NR==2 {print $4}')
say "free disk" "${free} GB (a reel needs about 1 GB while it renders)"

if [ $missing = 1 ] && [ $INSTALL = 0 ]; then printf '\n%s\n' "Some pieces are missing. With the user's OK: sh scripts/setup.sh --install"; exit 2; fi
[ $missing = 1 ] && { printf '\n%s\n' "Still missing something above."; exit 2; }
printf '\n%s\n' "Ready. The first ./reel run also fetches its Python packages (numpy, playwright, opencv) through uv."
