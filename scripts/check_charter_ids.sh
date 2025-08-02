#!/usr/bin/env bash
set -e
# Fail if any string like x^x-??? is NOT two digits
if grep -R --line-number -E 'x\^x-[0-9]{1}[^0-9]' agent | grep -v 'x^x-[0-9][0-9]' ; then
  echo "❌  Charter ID must be two digits, e.g. x^x-17"; exit 1
fi
