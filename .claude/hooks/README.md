# SessionStart-Hook: Klon-Aktualitaet

`session-start.sh` meldet beim Sessionstart, wie viele Commits der ausgecheckte
Stand hinter `origin/<Default-Branch>` liegt. Registriert ist er in
`.claude/settings.json`.

## Warum

Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren Ursache
nicht im Diff stand — die fehlenden Commits waren jeweils genau die, die das
Gate einfuehrten, an dem der Branch scheiterte. Gesucht wurde daraufhin in den
falschen Dateien: im eigenen Diff, der in Ordnung war.

Die Pruefung kostet eine Sekunde und ersetzt diese Fehlersuche.

Sie steht als manueller Befehl bereits in `CLAUDE.md` ("Vor der Arbeit").
Der Hook macht daraus etwas, an das niemand mehr denken muss.

## Verhalten

| Situation | Ausgabe |
| --- | --- |
| Stand ist aktuell (0 Commits hinter) | keine |
| N > 0 Commits hinter | Warnung mit N, Branchname und Einspiel-Befehl |
| kein Netz, kein Remote, DNS flattert, `fetch` laeuft in den Timeout | keine |
| detached HEAD | normale Pruefung (`HEAD` loest auf einen Commit auf) |
| leeres Repo, kein `origin`, kein `git` im PATH | keine |
| Default-Branch nicht ermittelbar | keine |

## Grundsaetze

**Der Hook blockiert die Session nie.** Kein `set -e`; jeder Fehlerpfad endet in
`exit 0` ohne Ausgabe. Ein Hook, der bei Netzproblemen die Arbeit anhaelt, wird
nach dem zweiten Mal abgeschaltet und schuetzt danach gar nichts. Ein
Sessionstart ohne Meldung heisst deshalb "aktuell **oder** nicht pruefbar" —
nie "blockiert".

**Der Default-Branch wird ermittelt, nicht angenommen.** Erst der lokal
hinterlegte `refs/remotes/origin/HEAD` (kostet kein Netz), sonst
`git ls-remote --symref origin HEAD`. Dieses Repo nutzt `master`; drei Server im
Portfolio tun das. Ein fest verdrahtetes `main` scheitert dort mit "couldn't
find remote ref main" — was wie ein Netzproblem aussieht und deshalb ignoriert
wird, waehrend der Klon weiter veraltet. Genau diese Annahme hat schon einmal
einen Branch 15 Commits alt werden lassen.

**Die Netzaufrufe sind hart befristet.** `ls-remote` 3 s, `fetch` 5 s, jeweils
per `timeout`-Binary und zusaetzlich per `http.lowSpeedLimit`/`lowSpeedTime`,
damit die Grenze auch ohne `timeout` im PATH greift. `GIT_TERMINAL_PROMPT=0` und
`ssh -o BatchMode=yes` verhindern, dass git bei fehlenden Credentials auf eine
Eingabe wartet, die im Sessionstart niemand geben kann.

Die Fristen sind ueber `CLAUDE_STALE_CLONE_FETCH_TIMEOUT` und
`CLAUDE_STALE_CLONE_LSREMOTE_TIMEOUT` (Sekunden) ueberschreibbar.

## Manuell pruefen

```bash
.claude/hooks/session-start.sh; echo "exit=$?"
```

Erwartung auf aktuellem Stand: keine Ausgabe, `exit=0`.

Gegenprobe — kuenstlich veralteter Stand meldet, aktueller Stand schweigt:

```bash
git stash -u 2>/dev/null
zweig=$(git symbolic-ref --quiet --short HEAD)
git checkout --quiet HEAD~3 && .claude/hooks/session-start.sh   # meldet 3
git checkout --quiet "$zweig" && .claude/hooks/session-start.sh # schweigt
git stash pop 2>/dev/null
```

## Kein Dependency-Setup

Der Hook installiert bewusst nichts. Die Toolchain kommt aus dem `[dev]`-Extra
von `pyproject.toml` (siehe `CLAUDE.md`), und ein Install im Sessionstart
verzoegert jede Session um ein Vielfaches dessen, was diese Pruefung kostet.
