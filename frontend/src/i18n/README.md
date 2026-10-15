# Languages (English, Hindi, Tamil)

SAT is written in English. The Hindi (`/hi/`) and Tamil (`/ta/`) versions are produced from the finished English pages: every sentence is looked up in a catalogue and replaced by its translation.

```
src/i18n/hi.json      Hindi:  {"units": {"English sentence": "हिन्दी वाक्य", ...}}
src/i18n/ta.json      Tamil:  same shape
src/i18n/hi.js.json   Hindi texts shown by scripts (buttons, counts, messages)
src/i18n/ta.js.json   Tamil texts shown by scripts
```

## Reviewing a translation
Open `hi.json` or `ta.json`. Each line is `"English": "translation"`. Fix any sentence you like and save. Keep the numbered markers (`<1>link text</1>`, `<1/>`) and `{placeholders}` exactly: the build refuses a translation whose markers do not match the English. Brand and product names stay in English letters.

## When the English changes
Run `python3 build.py --all-languages`. The warning "N sentences are not translated yet" lists what is missing, and those sentences show in English on the Hindi and Tamil pages until you add them. `python3 build.py --i18n-extract` writes every English sentence to `source.json` and every script text to `js-source.json`.

## Turning a language on and off
In `src/site.config.json`, `languages`:
* `enabled`: `false` leaves the language out of the site completely (no pages, no switcher).
* `indexable`: `false` keeps the pages visible to visitors but hidden from Google (`noindex`, not in the sitemap, no hreflang links). Set it to `true` only after a native reader has checked the translation. A language that is `indexable` must be 100% translated or the build stops.

The language menu does not store anything in the visitor's browser: the language is simply part of the page address.

## What is not translated
Text that the owner writes inside product files (names, pros, cons, verdicts) stays as written. It carries `translate="no"`.
