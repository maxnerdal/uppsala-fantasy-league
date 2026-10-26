# Uppsala Fantasy League

Ligatidningen för Uppsala Fantasy League: en Yahoo Fantasy NBA-liga (12 lag, H2H-kategorier, keeper) som spelats sedan 2011.

En AI-journalist skriver en artikel varje måndag om veckan som gått, plus specialare om draften, trades och slutspelet. Artiklarna publiceras på [uppsalafantasyleague.se](https://uppsalafantasyleague.se) (kommer snart).

## Innehåll

| Sökväg | Vad |
|---|---|
| `content/articles/` | Artiklar. `status: utkast` eller `publicerad` i frontmatter. |
| `content/managers/` | En profil per lag: manager, lore och historik genererad ur ligans data. |
| `content/history.md` | Alla säsonger sedan 2011, tidigare medlemmar och kuriosa. |
| `data/` | Ligahistorik och draftdata hämtad från Yahoo. |
| `scripts/` | Läser ligans publika Yahoo-sidor. |
| `.claude/skills/ufl-reporter/` | Journalistens instruktioner: röst, artikelstruktur, hur all-play räknas. |

## Vara med

Är du manager i ligan? Rätta din profil, lägg till lore eller tipsa om en story genom att öppna en issue eller en pull request.

## Köra själv

Kräver [uv](https://docs.astral.sh/uv/). Öppna repot i Claude Code och be om veckans artikel, eller kör skripten direkt:

```sh
uv run scripts/yahoo_nba.py league --week 1 --details
uv run scripts/ufl_history.py --from-year 2026 --to-year 2026
uv run scripts/ufl_profiles.py
```

Utan uv: `pip install requests beautifulsoup4` och kör med `python3`.
