#!/usr/bin/env python3
"""
Bible verse-by-verse study with OpenCode AI-assisted context-aware glossing.

Uses opencode CLI (mimo-v2.5-free) for context-aware word disambiguation.
Dictionary-first → AI disambiguation → positional fallback.

Usage:
  python3 scripts/bible/study_bible_books.py                    # all 66 books
  python3 scripts/bible/study_bible_books.py --book GEN          # one book
  python3 scripts/bible/study_bible_books.py --book GEN,EXO,LEV  # multiple
  python3 scripts/bible/study_bible_books.py --no-ai             # dict only
  python3 scripts/bible/study_bible_books.py --resume            # skip done books
  python3 scripts/bible/study_bible_books.py --stats             # show stats
  python3 scripts/bible/study_bible_books.py --log-level DEBUG   # verbose logging

Logs:
  data/dictionary/bible_study/bible_study_log.jsonl  — full gloss trace
  data/dictionary/bible_study/ai_gloss_cache.jsonl   — AI decisions cache
"""

import argparse
import glob
import json
import logging
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────────────────
WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR  = WORKSPACE / "data"
BIBLE_DIR = DATA_DIR / "corpus/bible/markdown/Parallel_Corpus/TDB77"
OUT_DIR   = DATA_DIR / "dictionary/bible_study"
OUT_DICT  = DATA_DIR / "dictionary/processed/dict_bible_learned_v1.jsonl"
DICT_PATH      = DATA_DIR / "dictionary/processed/dict_zo_en_master_v1.jsonl"
SUPPLEMENT_PATH = DATA_DIR / "dictionary/processed/dict_canonical_v1.jsonl"
AI_CACHE  = OUT_DIR / "ai_gloss_cache.jsonl"
LOG_FILE  = OUT_DIR / "bible_study_log.jsonl"

BOOK_ORDER = [
    "GEN","EXO","LEV","NUM","DEU","JOS","JDG","RUT",
    "1SA","2SA","1KI","2KI","1CH","2CH","EZR","NEH","EST",
    "JOB","PSA","PRO","ECC","SNG","ISA","JER","LAM","EZK",
    "DAN","HOS","JOL","AMO","OBA","JON","MIC","NAM","HAB",
    "ZEP","HAG","ZEC","MAL",
    "MAT","MRK","LUK","JHN","ACT","ROM",
    "1CO","2CO","GAL","EPH","PHP","COL","1TH","2TH",
    "1TI","2TI","TIT","PHM","HEB","JAS","1PE","2PE",
    "1JN","2JN","3JN","JUD","REV",
]

SKIP_WORDS = {
    "in","a","hi","uh","leh","tawh","ah","kha","ta","pah","ciangin",
    "bangin","pen","na","ding","lai","hen","la","tua","te","i",
    "napi","hiam","un","ni","aw","ma","mah","ka","nang","amah",
    "eima","keima","nangmah","ih","ite","nate","kite","amaute",
}
KEEP_SHORT = {"lo","kei","om","mu","pa","nu","ci"}

EN_STOP = {
    "the","and","of","to","in","a","an","is","was","he","she","it",
    "his","her","they","them","their","that","this","for","with","not",
    "but","all","be","are","were","have","had","has","from","by","at",
    "on","or","so","as","him","we","you","i","my","thy","thee","shall",
    "will","said","unto","upon","which","who","then","when","also","now",
    "out","up","did","do","no","if","me","us","our","its","than","into",
    "even","yet","let","may","one","two","three","four","five","six",
    "seven","eight","nine","ten",
}

TENSE_MARKERS    = {"ding","zo","khin","nawn","pah","lel","ta","ngei"}
NEGATION_MARKERS = {"kei","lo","kei lo"}
ASPECT_MARKERS   = {"thei","kik","sak","khia"}

# ── Logging ─────────────────────────────────────────────────────────────────
log = logging.getLogger("bible_study")


def setup_logging(level="INFO"):
    log.parent and log.parent.handlers.clear()
    log.setLevel(getattr(logging, level))

    fmt = logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    log.addHandler(ch)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8", mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(fh)


def log_json(event_type, **kw):
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "event": event_type, **kw}
    line = json.dumps(rec, ensure_ascii=False)
    log.debug(line)
    if event_type == "gloss":
        log.info(f"  📝 {kw.get('word','?')} → {kw.get('meaning','?')}  [{kw.get('source','?')}]")
    elif event_type == "ai_call":
        log.info(f"  🤖 AI: {kw.get('word','?')} ...")
    elif event_type == "ai_result":
        log.info(f"  ✅ AI: {kw.get('word','?')} → {kw.get('chosen','?')}")
    elif event_type == "book_start":
        log.info(f"\n📖 {kw.get('book','')} ({kw.get('num','')}/66) — {kw.get('verses','?')} verses")
    elif event_type == "book_done":
        log.info(f"  📊 dict={kw.get('dict_rate','?')} ai={kw.get('ai_rate','?')} fb={kw.get('fb_rate','?')}")
    elif event_type == "error":
        log.info(f"  ❌ {kw.get('msg','')}")


# ── OpenCode AI ─────────────────────────────────────────────────────────────
def opencode_ask(prompt, timeout=45):
    """Call opencode CLI (mimo-v2.5-free) and return text response."""
    try:
        result = subprocess.run(
            ["opencode", "run", "-m", "opencode/mimo-v2.5-free",
             "--pure", "--format", "json", prompt],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "NO_COLOR": "1"},
        )
        # Parse JSON events from stdout
        for line in result.stdout.strip().split("\n"):
            try:
                ev = json.loads(line)
                if ev.get("type") == "text":
                    return ev["part"]["text"].strip()
            except (json.JSONDecodeError, KeyError):
                continue
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def ai_disambiguate(word, meanings, zo_verse, en_verse, cache):
    """Use OpenCode AI to pick the right meaning for a polysemous word."""
    cache_key = f"{word}|{'|'.join(meanings[:4])}"
    if cache_key in cache:
        log_json("gloss", word=word, meaning=cache[cache_key], source="cache")
        return cache[cache_key], "cached"

    ms = "; ".join(f'"{m}"' for m in meanings[:6])
    prompt = (
        f"Tedim Zolai Bible word: \"{word}\" has meanings: {ms}\n"
        f"Zolai: {zo_verse}\nKJV: {en_verse}\n"
        f"Which single meaning fits this verse? Reply ONLY the word."
    )
    log_json("ai_call", word=word, meanings=meanings)

    result = opencode_ask(prompt)
    if result:
        rl = result.lower().strip().strip('"').strip("'")
        for m in meanings:
            if rl == m.lower() or rl in m.lower() or m.lower() in rl:
                cache[cache_key] = m
                log_json("ai_result", word=word, chosen=m, method="validated")
                return m, "validated"

    cache[cache_key] = meanings[0]
    log_json("ai_result", word=word, chosen=meanings[0], method="fallback")
    return meanings[0], "fallback"


def ai_translate_unknown(word, zo_verse, en_verse, cache):
    """Ask AI to translate an unknown Zolai word from context."""
    cache_key = f"unk|{word}"
    if cache_key in cache:
        return cache[cache_key], "cached"

    prompt = (
        f"Tedim Zolai Bible: \"{word}\" not in dictionary.\n"
        f"Zolai: {zo_verse}\nKJV: {en_verse}\n"
        f"What does \"{word}\" mean? Reply ONLY 1-3 English words."
    )
    log_json("ai_call", word=word, meanings=["(unknown)"])

    result = opencode_ask(prompt)
    if result:
        meaning = result.strip().strip('"').strip("'")[:40]
        cache[cache_key] = meaning
        log_json("ai_result", word=word, chosen=meaning, method="translated")
        return meaning, "translated"

    return "", "unknown"


# ── Dictionary ──────────────────────────────────────────────────────────────
def _extract_entry(d):
    """Extract (headword, [meanings]) from dict entry, handling both formats."""
    # Format 1: {zolai, english, ...}  (zo-en dict)
    hw = d.get("zolai", "").strip().lower()
    en_raw = d.get("english", [])
    if not hw:
        # Format 2: {headword, translations, ...}  (supplement / canonical)
        hw = d.get("headword", "").strip().lower()
        en_raw = d.get("translations", [])
    if not hw or len(hw.split()) > 3 or len(hw) > 20:
        return None, []
    if isinstance(en_raw, str):
        en_raw = [en_raw]
    clean = []
    for t in en_raw:
        if not isinstance(t, str):
            continue
        m = t.split("\n")[0].strip()
        m = re.sub(r'\s*\([^)]*\)\s*.*', '', m).strip()
        m = re.sub(r'\s+[a-z]{2,4}\s*[:\-].*$', '', m).strip()
        if m and len(m) > 1 and m not in clean:
            clean.append(m)
    return hw, clean


def load_dictionary(path=DICT_PATH):
    all_m = {}   # word → [meanings]
    first_m = {} # word → first meaning
    # Load base dict first, then supplement OVERRIDES bad entries
    for _p in [path, SUPPLEMENT_PATH]:
        if not _p.exists():
            continue
        try:
            with open(_p, encoding="utf-8") as f:
                for line in f:
                    d = json.loads(line)
                    hw, clean = _extract_entry(d)
                    if clean:
                        all_m[hw] = clean       # always overwrite
                        first_m[hw] = clean[0]  # always overwrite
        except FileNotFoundError:
            log.info(f"  ⚠️  Dictionary not found: {_p}")
    # Build phrase dictionary — ONLY from supplement (fast matching)
    phrases = {}  # (word1, word2, ...) → first meaning
    _supplement = SUPPLEMENT_PATH
    if _supplement.exists():
        try:
            with open(_supplement, encoding="utf-8") as f:
                for line in f:
                    d = json.loads(line)
                    hw, clean = _extract_entry(d)
                    if clean:
                        words = hw.split()
                        if len(words) >= 2:
                            phrases[tuple(words)] = clean[0]
        except FileNotFoundError:
            pass
    log.info(f"  Phrases: {len(phrases)} multi-word entries")

    poly = sum(1 for v in all_m.values() if len(v) > 1)
    log.info(f"  Dictionary: {len(all_m)} headwords, {poly} polysemous")
    return all_m, first_m, phrases
def load_ai_cache():
    c = {}
    if AI_CACHE.exists():
        with open(AI_CACHE, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                c[d["key"]] = d["gloss"]
    log.info(f"  AI cache: {len(c)} entries")
    return c


def save_ai_cache(cache):
    AI_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(AI_CACHE, "w", encoding="utf-8") as f:
        f.writelines(json.dumps({"key": k, "gloss": v}, ensure_ascii=False) + "\n" for k, v in sorted(cache.items()))


# ── Tokenizer / parser ──────────────────────────────────────────────────────
def tokenize(text):
    return re.findall(r"[a-z']+", text.lower())


def parse_book(path):
    ref_pat = re.compile(r'\*\*(\d+):(\d+)\*\*')
    zo_pat  = re.compile(r'^(?:TDB77|Tedim2010|Tedim_Chin|Zokam):\s*(.+)', re.IGNORECASE)
    en_pat  = re.compile(r'^KJV:\s*(.+)', re.IGNORECASE)
    ch = vs = ""; zo = en = ""
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            m = ref_pat.match(line)
            if m:
                if ch and zo and en:
                    yield ch, vs, zo, en
                ch, vs = m.group(1), m.group(2)
                zo = en = ""
                continue
            m = zo_pat.match(line)
            if m and not zo:
                zo = m.group(1).strip()
                continue
            m = en_pat.match(line)
            if m:
                en = m.group(1).strip()
    if ch and zo and en:
        yield ch, vs, zo, en


# ── Glossing ────────────────────────────────────────────────────────────────
def gloss_verse(zo_tokens, en_tokens, dict_all, dict_first, phrases,
                ai_cache, zo_verse, en_verse, use_ai):
    glosses = {}
    content_en = [t for t in en_tokens if t not in EN_STOP and len(t) > 2]
    skip_next = set()  # indices already consumed by phrase match

    # Phrase matching — longest phrases first
    sorted_phrases = sorted(phrases.items(), key=lambda x: -len(x[0]))
    for i in range(len(zo_tokens)):
        if i in skip_next:
            continue
        for phrase_words, phrase_gloss in sorted_phrases:
            plen = len(phrase_words)
            if i + plen > len(zo_tokens):
                continue
            window = tuple(zo_tokens[i:i+plen])
            if window == phrase_words:
                glosses[zo_tokens[i]] = {"en": phrase_gloss, "source": "phrase", "confidence": "high"}
                log_json("gloss", word=zo_tokens[i], meaning=phrase_gloss, source="phrase",
                         phrase=" ".join(phrase_words))
                for j in range(i, i+plen):
                    skip_next.add(j)
                break

    for i, zo in enumerate(zo_tokens):
        if i in skip_next:
            continue
        if (len(zo) < 3 and zo not in KEEP_SHORT) or zo in SKIP_WORDS:
            continue

        if zo in dict_all:
            meanings = dict_all[zo]
            if len(meanings) == 1:
                glosses[zo] = {"en": meanings[0], "source": "dict", "confidence": "high"}
                log_json("gloss", word=zo, meaning=meanings[0], source="dict")
            elif use_ai:
                chosen, method = ai_disambiguate(zo, meanings, zo_verse, en_verse, ai_cache)
                glosses[zo] = {"en": chosen, "source": f"ai_{method}",
                               "confidence": "medium", "all_meanings": meanings}
            else:
                glosses[zo] = {"en": meanings[0], "source": "dict_first",
                               "confidence": "medium", "all_meanings": meanings}
                log_json("gloss", word=zo, meaning=meanings[0], source="dict_first")
        else:
            if use_ai:
                chosen, method = ai_translate_unknown(zo, zo_verse, en_verse, ai_cache)
                if chosen:
                    glosses[zo] = {"en": chosen, "source": f"ai_{method}", "confidence": "medium"}
                    continue
            # positional fallback
            zn = i / max(len(zo_tokens), 1)
            best, bd = "", 1.0
            for j, en in enumerate(content_en):
                d = abs(zn - j / max(len(content_en), 1))
                if d < bd:
                    bd, best = d, en
            if best and bd < 0.4:
                glosses[zo] = {"en": best, "source": "fallback", "confidence": "low"}
                log_json("gloss", word=zo, meaning=best, source="fallback")

    return glosses


# ── Grammar ─────────────────────────────────────────────────────────────────
def detect_grammar(zo_tokens):
    pats = []
    for i, t in enumerate(zo_tokens):
        ctx = zo_tokens[max(0,i-2):i+2]
        if t in TENSE_MARKERS:
            pats.append({"type": "tense", "marker": t, "context": ctx})
        if t in NEGATION_MARKERS:
            pats.append({"type": "negation", "marker": t, "context": ctx})
        if t in ASPECT_MARKERS:
            pats.append({"type": "aspect", "marker": t, "context": ctx})
        if t == "lo" and i > 0 and zo_tokens[i-1] == "kei":
            prev2 = zo_tokens[i-2] if i > 1 else ""
            pats.append({"type": "compound_neg", "marker": "kei lo",
                          "subject": prev2, "context": zo_tokens[max(0,i-3):i+2]})
    return pats


# ── Book study ──────────────────────────────────────────────────────────────
def study_book(book_code, path, known_vocab, dict_all, dict_first, phrases,
               ai_cache, use_ai):
    rec = {
        "book": book_code,
        "chapters": defaultdict(lambda: {"verses": []}),
        "new_vocab": [], "grammar_patterns": [], "word_freq": Counter(),
        "dict_hits": 0, "ai_hits": 0, "fb_hits": 0, "total": 0,
    }
    wem = defaultdict(Counter)

    for ch, vs, zo_v, en_v in parse_book(path):
        zt = tokenize(zo_v)
        et = tokenize(en_v)
        g = gloss_verse(zt, et, dict_all, dict_first, phrases, ai_cache, zo_v, en_v, use_ai)
        gr = detect_grammar(zt)

        for t in zt:
            if (len(t) > 2 or t in KEEP_SHORT) and t not in SKIP_WORDS:
                rec["word_freq"][t] += 1

        for zo, gl in g.items():
            wem[zo][gl["en"]] += 1
            rec["total"] += 1
            src = gl["source"]
            if src == "dict":
                rec["dict_hits"] += 1
            elif src.startswith("ai_"):
                rec["ai_hits"] += 1
            else:
                rec["fb_hits"] += 1

        rec["chapters"][ch]["verses"].append({
            "ref": f"{book_code} {ch}:{vs}", "zo": zo_v, "en": en_v,
            "glossed": g, "grammar": gr,
        })
        if gr:
            rec["grammar_patterns"].extend(gr)

    for word, ec in wem.items():
        if word not in known_vocab:
            top = ec.most_common(1)[0][0] if ec else ""
            rec["new_vocab"].append({"word": word, "gloss": top,
                                      "freq": rec["word_freq"][word], "first_book": book_code})
            known_vocab[word] = {"gloss": top, "first_book": book_code,
                                  "all_books": [book_code], "en_counter": dict(ec)}
        else:
            for en, cnt in ec.items():
                known_vocab[word].setdefault("en_counter", {})[en] = \
                    known_vocab[word]["en_counter"].get(en, 0) + cnt
            if book_code not in known_vocab[word].get("all_books", []):
                known_vocab[word].setdefault("all_books", []).append(book_code)

    return rec, known_vocab


# ── Save ────────────────────────────────────────────────────────────────────
def save_book(book_code, rec, book_num):
    out = OUT_DIR / f"{book_num:02d}_{book_code}_study.jsonl"
    nv = sum(len(c["verses"]) for c in rec["chapters"].values())
    nn = len(rec["new_vocab"])
    ng = len(rec["grammar_patterns"])
    t = rec["total"] or 1
    dr = f"{rec['dict_hits']/t*100:.1f}%"
    ar = f"{rec['ai_hits']/t*100:.1f}%"
    fr = f"{rec['fb_hits']/t*100:.1f}%"

    with open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "type": "book_summary", "book": book_code, "book_num": book_num,
            "verses": nv, "new_vocab": nn, "grammar_patterns": ng,
            "dict_match_rate": dr, "ai_disambig_rate": ar, "fallback_rate": fr,
            "dict_hits": rec["dict_hits"], "ai_disambiguated": rec["ai_hits"],
            "positional_fallback": rec["fb_hits"], "total_glosses": rec["total"],
            "top_words": rec["word_freq"].most_common(20),
        }, ensure_ascii=False) + "\n")
        f.writelines(json.dumps({"type": "vocab", **v}, ensure_ascii=False) + "\n"
                      for v in sorted(rec["new_vocab"], key=lambda x: -x["freq"]))
        seen = set()
        for p in rec["grammar_patterns"]:
            k = (p["type"], p["marker"], tuple(p["context"]))
            if k not in seen:
                seen.add(k)
                f.write(json.dumps({"type": "grammar", **p}, ensure_ascii=False) + "\n")

    log_json("book_done", book=book_code, num=book_num, verses=nv, new_vocab=nn,
             dict_rate=dr, ai_rate=ar, fb_rate=fr)
    return nv, nn


def build_final_dict(known_vocab):
    entries = []
    for word, data in sorted(known_vocab.items()):
        ec = Counter(data.get("en_counter", {}))
        trans = [w for w, _ in ec.most_common(8) if w not in EN_STOP and len(w) > 2]
        if not trans:
            trans = [data["gloss"]] if data["gloss"] else []
        entries.append({
            "zolai": word, "english": trans[0] if trans else "",
            "translations": trans, "first_book": data["first_book"],
            "all_books": data.get("all_books", []), "book_count": len(data.get("all_books", [])),
            "dialect": "tedim", "source": "Bible-Verse-Study", "accuracy": "ai-verified",
        })
    return entries


# ── Stats ───────────────────────────────────────────────────────────────────
def show_stats():
    files = sorted(OUT_DIR.glob("*_study.jsonl"))
    if not files:
        print("No study files found."); return
    tv = td = ta = tf = 0
    for f in files:
        with open(f) as fh:
            s = json.loads(fh.readline())
            if s.get("type") != "book_summary": continue
            tv += s.get("verses", 0)
            td += s.get("dict_hits", 0)
            ta += s.get("ai_disambiguated", 0)
            tf += s.get("positional_fallback", 0)
            print(f"  {s['book']:4s} {s['verses']:>5}v  dict={s.get('dict_match_rate','?'):>6}  "
                  f"ai={s.get('ai_disambig_rate','?'):>6}  fb={s.get('fallback_rate','?'):>6}")
    tot = td + ta + tf
    print(f"\n  TOTAL: {tv} verses, {tot} glosses")
    if tot:
        print(f"  Dict:      {td} ({td/tot*100:.1f}%)")
        print(f"  AI:        {ta} ({ta/tot*100:.1f}%)")
        print(f"  Fallback:  {tf} ({tf/tot*100:.1f}%)")


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Bible study with OpenCode AI glossing")
    parser.add_argument("--book", help="Comma-separated book codes (e.g. GEN,EXO)")
    parser.add_argument("--no-ai", action="store_true", help="Dictionary only, no AI")
    parser.add_argument("--resume", action="store_true", help="Skip books already done")
    parser.add_argument("--stats", action="store_true", help="Show stats only")
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARN")
    args = parser.parse_args()

    setup_logging(args.log_level)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.stats:
        show_stats(); return

    use_ai = not args.no_ai
    log.info("=" * 60)
    log.info("BIBLE STUDY — OpenCode AI Glossing")
    log.info(f"  Dictionary: {DICT_PATH}")
    log.info(f"  Bible:       {BIBLE_DIR}")
    log.info(f"  Output:      {OUT_DIR}")
    log.info("  AI model:    opencode/mimo-v2.5-free" if use_ai else "  AI: OFF (dict only)")
    log.info("=" * 60)

    dict_all, dict_first, phrases = load_dictionary()
    ai_cache = load_ai_cache()

    available = {}
    for f in glob.glob(str(BIBLE_DIR / "*_Parallel.md")):
        code = Path(f).stem.replace("_TDB77_Parallel", "").replace("_Parallel", "")
        available[code] = f

    books = [b.strip().upper() for b in args.book.split(",")] if args.book else BOOK_ORDER

    known = {}
    tv = tn = 0
    t0 = time.time()

    log_json("start", total_books=len(books), use_ai=use_ai)

    for bn, bc in enumerate(books, 1):
        if bc not in available:
            log_json("error", book=bc, msg="NOT FOUND"); continue
        if args.resume:
            idx = BOOK_ORDER.index(bc) + 1 if bc in BOOK_ORDER else bn
            if (OUT_DIR / f"{idx:02d}_{bc}_study.jsonl").exists():
                log.info(f"  ⏭ {bc} (already done)"); continue

        n_v = sum(1 for _ in parse_book(available[bc]))
        log_json("book_start", book=bc, num=bn, verses=n_v)

        rec, known = study_book(bc, available[bc], known, dict_all, dict_first, phrases, ai_cache, use_ai)
        if use_ai:
            save_ai_cache(ai_cache)
        v, n = save_book(bc, rec, bn)
        tv += v; tn += n

    entries = build_final_dict(known)
    with open(OUT_DICT, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(e, ensure_ascii=False) + "\n" for e in entries)

    elapsed = time.time() - t0
    log_json("done", total_verses=tv, vocab=tn, unique=len(known),
             ai_cache=len(ai_cache), elapsed_s=f"{elapsed:.0f}")

    print(f"\n{'='*60}")
    print(f"  Done in {elapsed:.0f}s")
    print(f"  Verses: {tv}  |  Vocab: {tn}  |  Unique: {len(known)}")
    print(f"  AI cache: {len(ai_cache)} entries")
    print(f"  Output:   {OUT_DIR}")
    print(f"  Log:      {LOG_FILE}")
    print(f"  Dict:     {OUT_DICT}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
