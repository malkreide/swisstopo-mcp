#!/usr/bin/env bash
# SessionStart-Hook: meldet beim Sessionstart, wie viele Commits der
# ausgecheckte Stand hinter origin/<Default-Branch> liegt.
#
# WARUM dieser Hook existiert: .claude/hooks/README.md
#
# OBERSTE REGEL: Dieser Hook blockiert die Session NIE.
#   - kein `set -e` / `set -o pipefail` — ein fehlschlagender Befehl darf den
#     Sessionstart nicht mit abreissen
#   - jeder Fehlerpfad endet in `still_raus` (exit 0, keine Ausgabe)
#   - jeder Netzaufruf ist hart befristet und lauft nicht-interaktiv
# Ein Hook, der bei Netzproblemen die Arbeit anhaelt, wird nach dem zweiten Mal
# abgeschaltet und schuetzt danach gar nichts.

# Sekunden. Ueberschreibbar, falls ein Netz mal grundsaetzlich langsamer ist.
FETCH_TIMEOUT="${CLAUDE_STALE_CLONE_FETCH_TIMEOUT:-5}"
LSREMOTE_TIMEOUT="${CLAUDE_STALE_CLONE_LSREMOTE_TIMEOUT:-3}"

still_raus() { exit 0; }

# Nicht-interaktiv: ohne diese beiden wartet git bei fehlenden Credentials auf
# eine Eingabe, die im Sessionstart niemand geben kann — der Hook haenge dann
# bis zum Timeout statt sofort durchzugehen.
export GIT_TERMINAL_PROMPT=0
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -o BatchMode=yes}"

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || still_raus

command -v git >/dev/null 2>&1                     || still_raus
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || still_raus
# Leeres Repo: HEAD zeigt auf nichts, ein Vergleich ist sinnlos.
git rev-parse --verify --quiet HEAD >/dev/null 2>&1 || still_raus
# Kein Remote `origin` — nichts, wogegen sich vergleichen liesse.
git remote get-url origin >/dev/null 2>&1           || still_raus

# Jeder Netzaufruf doppelt befristet: `timeout` kappt den Prozess, die
# http-Bremsen greifen auch dort, wo kein `timeout`-Binary vorhanden ist.
git_netz() {
  local grenze="$1"
  shift
  local -a befehl=(
    git -c "http.lowSpeedLimit=1000" -c "http.lowSpeedTime=${grenze}" "$@"
  )
  if command -v timeout >/dev/null 2>&1; then
    timeout "${grenze}" "${befehl[@]}"
  else
    "${befehl[@]}"
  fi
}

# Default-Branch ermitteln, NICHT annehmen. `main` ist portfolioweit nicht der
# Normalfall — dieses Repo selbst nutzt `master`, und genau diese Annahme hat
# schon einmal einen Branch 15 Commits alt werden lassen.
zweig=""
# 1. lokal hinterlegter origin/HEAD — kostet kein Netz
zweig="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)"
zweig="${zweig#origin/}"
# 2. sonst den Remote fragen, befristet
if [ -z "${zweig}" ]; then
  zweig="$(
    git_netz "${LSREMOTE_TIMEOUT}" ls-remote --symref origin HEAD 2>/dev/null |
      sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p' |
      head -n 1
  )"
fi
# 3. nicht ermittelbar -> schweigen. Lieber keine Meldung als eine ueber den
#    falschen Branch.
[ -n "${zweig}" ] || still_raus

git_netz "${FETCH_TIMEOUT}" fetch --quiet origin "${zweig}" 2>/dev/null || still_raus

# Funktioniert auch bei detached HEAD: HEAD loest dort auf einen Commit auf.
hinter="$(git rev-list --count "HEAD..FETCH_HEAD" 2>/dev/null)" || still_raus
# Nur Ziffern durchlassen; alles andere ist eine Fehlermeldung, kein Zaehlwert.
case "${hinter}" in
  ''|*[!0-9]*) still_raus ;;
esac
# Bei 0 schweigt der Hook.
[ "${hinter}" -gt 0 ] || still_raus

printf '%s\n' \
  "⚠️  Klon veraltet: ${hinter} Commit(s) hinter origin/${zweig}." \
  "" \
  "    Fehlende Commits fuehren Gates ein, an denen die CI scheitert, ohne dass" \
  "    die Ursache im Diff steht. Vor der Arbeit einspielen:" \
  "" \
  "        git fetch origin ${zweig} && git merge origin/${zweig}   # oder rebase" \
  "" \
  "    (Hintergrund: .claude/hooks/README.md)"

exit 0
