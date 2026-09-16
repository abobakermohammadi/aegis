#!/bin/sh
# Run every check in the Aegis repository. Exit 0 only if all pass.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
fail=0

echo "== python: mission engine =="
python3 -m unittest discover aegis-engine -p "test_*.py" || fail=1

echo "== python: usage-optimizer router =="
python3 -m unittest discover usage-optimizer/scripts -p "test_*.py" || fail=1

echo "== python: second-brain-context graph builder =="
python3 -m unittest discover second-brain-context/scripts -p "test_*.py" || fail=1

echo "== python: cross-platform installer =="
python3 -m unittest discover installer-tests -p "test_*.py" || fail=1

echo "== installer: POSIX clean-environment smoke =="
smoke=$(mktemp -d)
if HOME="$smoke/home" ./install.sh --target "$smoke/home/skills" >/dev/null 2>&1 \
   && [ -f "$smoke/home/skills/aegis-ceo-skills/SKILL.md" ]; then
  echo "POSIX installer smoke: OK"
else
  echo "POSIX installer smoke: FAILED" >&2
  fail=1
fi
rm -rf "$smoke"

echo "== installer: Python clean-environment smoke =="
py_smoke=$(mktemp -d)
if python3 install.py --target "$py_smoke/skills" --engine-target "$py_smoke/engine" >/dev/null 2>&1 \
   && [ -f "$py_smoke/skills/aegis-ceo-skills/SKILL.md" ] \
   && [ -f "$py_smoke/engine/aegis.py" ]; then
  echo "Python installer smoke: OK"
else
  echo "Python installer smoke: FAILED" >&2
  fail=1
fi
rm -rf "$py_smoke"

echo "== docs: public project site source =="
for file in docs/index.html docs/404.html docs/sitemap.xml docs/.nojekyll; do
  if [ ! -e "$file" ]; then
    echo "missing site file: $file" >&2
    fail=1
  fi
done

if [ -f docs/index.html ]; then
  grep -q 'https://abobakermohammadi.github.io/aegis/' docs/index.html || {
    echo "site canonical URL missing" >&2
    fail=1
  }
  grep -q 'github.com/abobakermohammadi/aegis' docs/index.html || {
    echo "site public-repository link missing" >&2
    fail=1
  }
  grep -q './verify.sh' docs/index.html || {
    echo "site proof command missing" >&2
    fail=1
  }
  if grep -Eqi 'abobaker288882-crypto|aegis-ceo-office-site|SprachPrep|MAMELAT|NEWAPP|Sineklik' docs/index.html; then
    echo "site contains stale or unrelated project identity" >&2
    fail=1
  fi
fi

if [ -f docs/sitemap.xml ]; then
  grep -q '<loc>https://abobakermohammadi.github.io/aegis/</loc>' docs/sitemap.xml || {
    echo "site sitemap canonical route missing" >&2
    fail=1
  }
fi

if [ "$fail" -ne 0 ]; then
  echo "RESULT: FAILURES ABOVE" >&2
  exit 1
fi

echo "RESULT: all checks passed"
