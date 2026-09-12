#!/usr/bin/env python3
"""Zolai Proficiency Test — A1 to C2 levels.

Generates multiple-choice questions from SQLite database
(vocab, dictionary, bible_verses) for real, high-frequency
Zolai words and short Bible sentences.
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
DB_PATH = WORKSPACE / "data" / "zolai.db"

# Minimum frequency for vocab to be used in questions
MIN_FREQ = 100

# Level configs: (vocab, sent, gram, neg, ctx, err, comp)
LEVELS = {
    "A1": dict(
        desc="Beginner", vocab=10, sent=2, gram=0,
        neg=0, ctx=0, err=0, comp=0,
    ),
    "A2": dict(
        desc="Elementary", vocab=20, sent=5, gram=3,
        neg=2, ctx=0, err=0, comp=0,
    ),
    "B1": dict(
        desc="Intermediate", vocab=30, sent=10, gram=5,
        neg=0, ctx=5, err=0, comp=0,
    ),
    "B2": dict(
        desc="Upper-Intermediate", vocab=25, sent=10,
        gram=5, neg=0, ctx=5, err=5, comp=0,
    ),
    "C1": dict(
        desc="Advanced", vocab=20, sent=10, gram=5,
        neg=0, ctx=5, err=5, comp=5,
    ),
    "C2": dict(
        desc="Mastery", vocab=15, sent=5, gram=0,
        neg=0, ctx=5, err=5, comp=10,
    ),
}

# Grammar pattern labels
GRAMMAR_PATTERNS = [
    ("SOV", "Subject-Object-Verb"),
    ("hiam", "Yes/no question marker"),
    ("kei", "Negation particle"),
    ("ding", "Future tense marker"),
    ("in", "Ergative marker"),
    ("hi", "Declarative particle"),
    ("leh", "Conjunction (and/then)"),
    ("tawh", "Comitative (with)"),
    ("a", "Agreement marker"),
    ("amah", "Pronoun (emphasis)"),
    ("na", "Noun marker / possessive"),
    ("sung", "Inside / locative"),
    ("a leh", "Conditional (if)"),
    ("ta", "Completive aspect"),
    ("lai", "Progressive aspect"),
    ("ki", "Reflexive marker"),
    ("tua", "That (conjunction)"),
    ("si", "Negative imperative"),
    ("te", "Past tense"),
    ("ci", "Quotative (said)"),
]


def _open_db():
    """Open a read-only connection to the SQLite database."""
    conn = sqlite3.connect(
        f"file:{DB_PATH}?mode=ro", uri=True
    )
    conn.row_factory = sqlite3.Row
    return conn


def load_high_freq_vocab():
    """Load high-frequency vocab from DB (frequency > MIN_FREQ).

    Returns list of (word, english, frequency) tuples,
    sorted by frequency descending.
    """
    conn = _open_db()
    try:
        cur = conn.execute(
            "SELECT headword, english, frequency "
            "FROM vocab "
            "WHERE frequency > ? "
            "ORDER BY frequency DESC",
            (MIN_FREQ,),
        )
        rows = cur.fetchall()
        return [
            (r["headword"], r["english"], r["frequency"])
            for r in rows
            if r["headword"] and r["english"]
        ]
    finally:
        conn.close()


def load_dict_pairs():
    """Load Zolai→English pairs from dictionary DB.

    Returns list of (zolai, english_clean) tuples.
    """
    conn = _open_db()
    try:
        cur = conn.execute(
            "SELECT zolai, english_clean "
            "FROM dictionary "
            "WHERE english_clean IS NOT NULL "
            "AND english_clean != ''"
        )
        rows = cur.fetchall()
        return [
            (r["zolai"], r["english_clean"])
            for r in rows
            if r["zolai"] and r["english_clean"]
        ]
    finally:
        conn.close()


def load_short_verses():
    """Load short Bible verses (3-12 words) from DB.

    Returns list of dicts with zo_tdb77, en_kJV, ref.
    """
    conn = _open_db()
    try:
        cur = conn.execute(
            "SELECT ref, zo_tdb77, en_kJV "
            "FROM bible_verses "
            "WHERE zo_tdb77 IS NOT NULL "
            "AND en_kJV IS NOT NULL "
            "AND zo_tdb77 != '' "
            "AND en_kJV != '' "
            "AND (length(zo_tdb77) "
            "     - length(replace(zo_tdb77, ' ', '')) + 1) "
            "BETWEEN 3 AND 12"
        )
        rows = cur.fetchall()
        return [
            {
                "ref": r["ref"],
                "zo_tdb77": r["zo_tdb77"],
                "en_kJV": r["en_kJV"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def load_all_verses():
    """Load all Bible verses from DB for distractor generation."""
    conn = _open_db()
    try:
        cur = conn.execute(
            "SELECT ref, zo_tdb77, en_kJV "
            "FROM bible_verses "
            "WHERE en_kJV IS NOT NULL "
            "AND en_kJV != ''"
        )
        rows = cur.fetchall()
        return [
            {
                "ref": r["ref"],
                "zo_tdb77": r["zo_tdb77"] or "",
                "en_kJV": r["en_kJV"],
            }
            for r in rows
        ]
    finally:
        conn.close()


def _is_zolai_word(word):
    """Check if a word looks like Zolai (not pure English).

    Returns True if the word is likely a Zolai headword
    rather than an English dictionary entry.
    """
    if not word:
        return False
    wl = word.lower().strip()
    skip_prefixes = (
        "& ", "(", ")", '"', "'", "adv", "v.", "n.", "adj",
    )
    if any(wl.startswith(p) for p in skip_prefixes):
        return False
    eng_suffixes = (
        "tion", "ment", "ness", "ity", "ous", "ive", "ing",
        "ed", "ful", "less", "able", "ible", "ence", "ance",
        "ism", "ist", "ize", "ise", "ly", "al",
    )
    if any(wl.endswith(s) for s in eng_suffixes):
        return False
    common_english = {
        "the", "and", "for", "are", "but", "not", "you",
        "all", "can", "had", "her", "was", "one", "our",
        "out", "has", "his", "how", "its", "may", "new",
        "now", "old", "see", "way", "who", "did", "got",
        "let", "say", "she", "too", "use", "from", "that",
        "with", "have", "this", "will", "your", "each",
        "make", "like", "long", "look", "many", "most",
        "over", "such", "take", "than", "them", "then",
        "what", "when", "come", "could", "been", "were",
        "some", "very", "just", "know", "also",
    }
    if wl in common_english:
        return False
    return True


def tokenize(text):
    """Split text into word tokens."""
    clean = text.replace(";", "").replace(",", "")
    clean = clean.replace(".", "").replace("'", "")
    return [w for w in clean.split() if w]


class ProficiencyTest:
    """Zolai proficiency test generator."""

    def __init__(self, level="A1"):
        self.level = level.upper()
        if self.level not in LEVELS:
            print(f"Unknown level: {level}")
            print("Valid: " + ", ".join(LEVELS.keys()))
            sys.exit(1)
        self.cfg = LEVELS[self.level]
        self.vocab_data = []
        self.dict_pairs = []
        self.short_verses = []
        self.all_verses = []
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy-load data from DB on first use."""
        if self._loaded:
            return
        print("Loading data from database...", file=sys.stderr)
        self.vocab_data = load_high_freq_vocab()
        self.dict_pairs = load_dict_pairs()
        self.short_verses = load_short_verses()
        self.all_verses = load_all_verses()
        self._loaded = True
        # Build zolai_pairs from vocab table only
        # (clean, high-frequency Zolai words)
        self.zolai_pairs = []
        seen = set()
        for word, eng, freq in self.vocab_data:
            key = word.lower().strip()
            if key not in seen and eng and len(str(eng)) > 1:
                seen.add(key)
                self.zolai_pairs.append(
                    (word, str(eng), freq)
                )
        print(
            f"  Loaded: {len(self.vocab_data)} vocab "
            f"(freq>{MIN_FREQ}), "
            f"{len(self.short_verses)} short verses, "
            f"{len(self.all_verses)} total verses",
            file=sys.stderr,
        )

    def _pick_random_vocab(self, n):
        """Pick n random high-frequency vocab entries.

        Returns tuples of (word, english, frequency).
        """
        self._ensure_loaded()
        if not self.zolai_pairs:
            return []
        return random.sample(
            self.zolai_pairs, min(n, len(self.zolai_pairs))
        )

    def _pick_random_sentences(self, n):
        """Pick n random short Bible verses."""
        self._ensure_loaded()
        if not self.short_verses:
            return []
        return random.sample(
            self.short_verses, min(n, len(self.short_verses))
        )

    def vocab_questions(self, n):
        """Multiple choice: what does this Zolai word mean?"""
        items = self._pick_random_vocab(n)
        questions = []
        for word_info in items:
            if not isinstance(word_info, tuple):
                continue
            word = word_info[0]
            correct = str(word_info[1])
            if not word or not correct:
                continue
            if len(correct) > 60:
                correct = correct[:57] + "..."
            distractors = self._get_distractors_from_pairs(
                word, correct, self.zolai_pairs
            )
            options = [correct] + distractors
            random.shuffle(options)
            questions.append({
                "type": "vocab",
                "question": (
                    "What does the Zolai word "
                    f"'{word}' mean in English?"
                ),
                "options": options,
                "answer": options.index(correct),
                "word": word,
                "translation": correct,
            })
        return questions

    def sentence_questions(self, n):
        """Multiple choice: translate this sentence."""
        items = self._pick_random_sentences(n)
        questions = []
        for v in items:
            zo = v.get("zo_tdb77", "")
            en = v.get("en_kJV", "")
            ref = v.get("ref", "?")
            distractors = self._get_sentence_distractors(
                en, self.all_verses
            )
            options = [en] + distractors
            random.shuffle(options)
            questions.append({
                "type": "sentence",
                "question": f"Translate: {zo}",
                "context": ref,
                "options": options,
                "answer": options.index(en),
                "zo": zo,
                "en": en,
            })
        return questions

    def grammar_questions(self, n):
        """Multiple choice: identify the grammar pattern."""
        questions = []
        used = set()
        while len(questions) < n and len(questions) < len(
            GRAMMAR_PATTERNS
        ):
            items = self._pick_random_sentences(1)
            if not items:
                break
            v = items[0]
            zo = v.get("zo_tdb77", "")
            ref = v.get("ref", "?")
            pat_idx = random.randint(
                0, len(GRAMMAR_PATTERNS) - 1
            )
            if pat_idx in used:
                continue
            used.add(pat_idx)
            pat_code, pat_desc = GRAMMAR_PATTERNS[pat_idx]
            all_pats = list(GRAMMAR_PATTERNS)
            random.shuffle(all_pats)
            options = [pat_desc]
            for code, desc in all_pats:
                if desc != pat_desc and len(options) < 4:
                    options.append(desc)
            random.shuffle(options)
            questions.append({
                "type": "grammar",
                "question": (
                    f"Identify the grammar pattern in: "
                    f"{zo}"
                ),
                "context": ref,
                "options": options,
                "answer": options.index(pat_desc),
                "pattern": pat_code,
            })
        return questions

    def negation_questions(self, n):
        """Multiple choice: what is the negative form?"""
        self._ensure_loaded()
        questions = []
        pairs = [
            (
                "Ka pai hi.",
                "Ka pai kei hi.",
                "I don't go",
            ),
            (
                "Na pai hi.",
                "Na pai kei hi.",
                "You don't go",
            ),
            (
                "A pai hi.",
                "A pai kei hi.",
                "He/she doesn't go",
            ),
            (
                "Ki pai hi.",
                "Ki pai kei hi.",
                "They don't go",
            ),
            (
                "Ka ne hi.",
                "Ka ne kei hi.",
                "I don't eat",
            ),
            (
                "Na ne hi.",
                "Na ne kei hi.",
                "You don't eat",
            ),
            (
                "A ne hi.",
                "A ne kei hi.",
                "He/she doesn't eat",
            ),
            (
                "Ka cia hi.",
                "Ka cia kei hi.",
                "I don't speak",
            ),
            (
                "Na cia hi.",
                "Na cia kei hi.",
                "You don't speak",
            ),
            (
                "A cia hi.",
                "A cia kei hi.",
                "He/she doesn't speak",
            ),
            (
                "Ka tam hi.",
                "Ka tam kei hi.",
                "I don't work",
            ),
            (
                "Na tam hi.",
                "Na tam kei hi.",
                "You don't work",
            ),
        ]
        random.shuffle(pairs)
        for pos, neg, en in pairs[:n]:
            distractors = [
                "ka " + pos.split()[-3] + " lo hi.",
                "a " + pos.split()[-3] + " ding hi.",
                "ka " + pos.split()[-3] + " si hi.",
            ]
            distractors = [
                d.replace("ka a ", "a ") for d in distractors
            ]
            options = [neg] + distractors[:3]
            random.shuffle(options)
            questions.append({
                "type": "negation",
                "question": (
                    f"What is the negative form of: {pos}"
                ),
                "hint": en,
                "options": options,
                "answer": options.index(neg),
            })
        return questions

    def context_questions(self, n):
        """Same word, different meaning in context."""
        self._ensure_loaded()
        polysemous = [
            ("hi", "declarative / to be", "He is tall."),
            ("in", "ergative / in", "He went in."),
            ("a", "agreement / possessive", "His house."),
            ("ci", "quotative / to tell", "He told me."),
            ("gam", "town / to dare", "The town."),
            ("gam", "to dare / town", "He dares."),
            ("mu", "to see / land", "See the land."),
            ("mu", "land / to see", "Look at this."),
            ("nek", "to eat / food", "Eat the food."),
            ("nek", "food / to eat", "The food is good."),
            ("sung", "inside / bag", "In the bag."),
            ("sung", "bag / inside", "Go inside."),
            ("topa", "Lord / boss", "The Lord God."),
            ("topa", "boss / Lord", "The boss said."),
        ]
        random.shuffle(polysemous)
        questions = []
        used_words = set()
        for word, meanings, example in polysemous:
            if len(questions) >= n:
                break
            if word in used_words:
                continue
            used_words.add(word)
            parts = meanings.split(" / ")
            if len(parts) < 2:
                continue
            correct = parts[0]
            distractors = [
                p for p in parts[1:]
            ] + ["(no meaning)"]
            while len(distractors) < 3:
                distractors.append("(unknown)")
            options = [correct] + distractors[:3]
            random.shuffle(options)
            questions.append({
                "type": "context",
                "question": (
                    f"In '{example}', what does "
                    f"'{word}' mean here?"
                ),
                "options": options,
                "answer": options.index(correct),
            })
        return questions

    def error_correction(self, n):
        """Find the grammar error."""
        errors = [
            {
                "wrong": "A pai lo hi.",
                "correct": "Pai lo hi.",
                "explanation": (
                    "3rd person 'lo' doesn't take 'a'"
                ),
            },
            {
                "wrong": "A pai lo ding.",
                "correct": "Pai lo ding.",
                "explanation": (
                    "'lo' + future doesn't take 'a'"
                ),
            },
            {
                "wrong": "Ka pai hiam?",
                "correct": "Na pai hiam?",
                "explanation": (
                    "2nd person question uses 'na'"
                ),
            },
            {
                "wrong": "Bang hang na pai hiam?",
                "correct": (
                    "Bang hang pai na hiam?"
                ),
                "explanation": (
                    "Content question: verb before subject"
                ),
            },
            {
                "wrong": "Ka an ne hi.",
                "correct": "Ka ne hi.",
                "explanation": (
                    "Verb 'ne' doesn't need article"
                ),
            },
            {
                "wrong": "A ne kei hi.",
                "correct": "A ne kei hi.",
                "explanation": "This is actually correct",
            },
            {
                "wrong": "Na pai kei a leh...",
                "correct": "Na pai kei a leh...",
                "explanation": "This is actually correct",
            },
            {
                "wrong": "Lungdam na!",
                "correct": "Lungdam!",
                "explanation": (
                    "Greeting doesn't take 'na' particle"
                ),
            },
            {
                "wrong": "Ka pai si hi.",
                "correct": "Ka pai kei hi.",
                "explanation": (
                    "Negation uses 'kei', not 'si'"
                ),
            },
            {
                "wrong": "A gam hi.",
                "correct": "Gam hi.",
                "explanation": (
                    "3rd person drops 'a' in statements"
                ),
            },
        ]
        random.shuffle(errors)
        questions = []
        for item in errors[:n]:
            opts = [
                item["correct"],
                item["wrong"],
                item["correct"] + " lo",
                item["wrong"] + " lo",
            ]
            opts = list(set(opts))[:4]
            while len(opts) < 4:
                opts.append(item["correct"] + " hi")
            random.shuffle(opts)
            questions.append({
                "type": "error",
                "question": (
                    "Which sentence has a grammar error?"
                ),
                "options": opts,
                "answer": opts.index(item["wrong"]),
                "correction": item["correct"],
                "explanation": item["explanation"],
            })
        return questions

    def comprehension(self, n):
        """Full verse translation."""
        items = self._pick_random_sentences(n)
        questions = []
        for v in items:
            zo = v.get("zo_tdb77", "")
            en = v.get("en_kJV", "")
            ref = v.get("ref", "?")
            distractors = self._get_sentence_distractors(
                en, self.all_verses
            )
            options = [en] + distractors[:3]
            random.shuffle(options)
            questions.append({
                "type": "comprehension",
                "question": (
                    f"Translate fully: {zo}"
                ),
                "context": ref,
                "options": options,
                "answer": options.index(en),
                "zo": zo,
                "en": en,
            })
        return questions

    def _get_distractors_from_pairs(
        self, correct_word, correct_translation, pairs,
        count=3,
    ):
        """Pick 3 wrong translations from zolai_pairs.

        Prefers entries with similar frequency to the
        correct word (same tier).
        """
        # Find the frequency of the correct word
        correct_freq = 0
        for p in pairs:
            if len(p) >= 3 and p[0] == correct_word:
                correct_freq = p[2]
                break
        candidates = []
        for p in pairs:
            word = p[0]
            trans = str(p[1])
            freq = p[2] if len(p) >= 3 else 0
            if (
                word != correct_word
                and trans != correct_translation
                and len(trans) > 2
            ):
                candidates.append((word, trans, freq))
        # Sort by proximity to correct frequency
        candidates.sort(
            key=lambda x: abs(x[2] - correct_freq)
        )
        return [c[1] for c in candidates[:count]]

    def _get_sentence_distractors(self, correct, corpus):
        """Pick 3 wrong English sentences."""
        candidates = []
        for v in corpus:
            en = v.get("en_kJV", "")
            if en and en != correct and len(en) > 5:
                candidates.append(en)
            if len(candidates) >= 30:
                break
        random.shuffle(candidates)
        return candidates[:3]

    def generate(self, count=None):
        """Generate all questions for this level."""
        self._ensure_loaded()
        c = self.cfg
        questions = []
        questions.extend(
            self.vocab_questions(c["vocab"])
        )
        questions.extend(
            self.sentence_questions(c["sent"])
        )
        if c["gram"] > 0:
            questions.extend(
                self.grammar_questions(c["gram"])
            )
        if c["neg"] > 0:
            questions.extend(
                self.negation_questions(c["neg"])
            )
        if c["ctx"] > 0:
            questions.extend(
                self.context_questions(c["ctx"])
            )
        if c["err"] > 0:
            questions.extend(
                self.error_correction(c["err"])
            )
        if c["comp"] > 0:
            questions.extend(
                self.comprehension(c["comp"])
            )
        random.shuffle(questions)
        if count:
            questions = questions[:count]
        return questions

    def run_interactive(self):
        """Run test interactively."""
        self._ensure_loaded()
        questions = self.generate()
        total = len(questions)
        score = 0
        print()
        print("═══ Zolai Proficiency Test ═══")
        print(f"Level: {self.level} — {self.cfg['desc']}")
        print(f"Questions: {total}")
        print()
        for i, q in enumerate(questions, 1):
            print(f"Q{i}/{total}: {q['question']}")
            if q.get("context"):
                print(f"  ({q['context']})")
            if q.get("hint"):
                print(f"  Hint: {q['hint']}")
            for j, opt in enumerate(q["options"]):
                print(f"  {j + 1}) {opt}")
            print()
            ans = input("Your answer (1-4): ").strip()
            try:
                idx = int(ans) - 1
                if idx == q["answer"]:
                    score += 1
                    print("✅ Correct!")
                else:
                    correct_opt = q["options"][q["answer"]]
                    print(
                        f"❌ Wrong. "
                        f"Answer: {correct_opt}"
                    )
                    if q.get("explanation"):
                        print(
                            f"   {q['explanation']}"
                        )
            except (ValueError, IndexError):
                print("❌ Invalid input")
            print()
        # Final score
        pct = (score / total * 100) if total > 0 else 0
        print("═══ Results ═══")
        print(f"Score: {score}/{total} ({pct:.0f}%)")
        if pct >= 90:
            print(
                f"🏆 Excellent! Level {self.level} passed!"
            )
        elif pct >= 70:
            print(
                f"👍 Good. Level {self.level} passed!"
            )
        elif pct >= 50:
            print("📚 Keep practicing!")
        else:
            print("💪 Try a lower level first.")

    def run_json(self):
        """Output questions as JSON."""
        self._ensure_loaded()
        questions = self.generate()
        output = {
            "level": self.level,
            "description": self.cfg["desc"],
            "total": len(questions),
            "questions": questions,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Zolai Proficiency Test"
    )
    parser.add_argument(
        "--level",
        default="A1",
        choices=list(LEVELS.keys()),
        help="Test level (A1-C2)",
    )
    parser.add_argument(
        "--count", type=int, help="Number of questions"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactively",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show level statistics",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    if args.stats:
        print("═══ Zolai Proficiency Test — Levels ═══")
        print()
        total = 0
        for level, cfg in LEVELS.items():
            q = (
                cfg["vocab"] + cfg["sent"] + cfg["gram"]
                + cfg["neg"] + cfg["ctx"] + cfg["err"]
                + cfg["comp"]
            )
            total += q
            parts = []
            if cfg["vocab"]:
                parts.append(f"vocab={cfg['vocab']}")
            if cfg["sent"]:
                parts.append(f"sent={cfg['sent']}")
            if cfg["gram"]:
                parts.append(f"gram={cfg['gram']}")
            if cfg["neg"]:
                parts.append(f"neg={cfg['neg']}")
            if cfg["ctx"]:
                parts.append(f"ctx={cfg['ctx']}")
            if cfg["err"]:
                parts.append(f"err={cfg['err']}")
            if cfg["comp"]:
                parts.append(f"comp={cfg['comp']}")
            detail = ", ".join(parts)
            print(
                f"  {level:3s} — {cfg['desc']:22s} "
                f"({q:2d} questions) "
                f"[{detail}]"
            )
        print()
        print(f"  Total across all levels: {total}")
        print()
        # Data stats from DB
        print("═══ Data Sources (SQLite) ═══")
        try:
            conn = _open_db()
            cur = conn.execute(
                "SELECT COUNT(*) FROM vocab "
                f"WHERE frequency > {MIN_FREQ}"
            )
            print(
                f"  High-freq vocab "
                f"(>{MIN_FREQ}): {cur.fetchone()[0]:,}"
            )
            cur = conn.execute(
                "SELECT COUNT(*) FROM dictionary"
            )
            print(
                f"  Dictionary: {cur.fetchone()[0]:,}"
            )
            cur = conn.execute(
                "SELECT COUNT(*) FROM bible_verses"
            )
            print(
                f"  Bible verses: {cur.fetchone()[0]:,}"
            )
            conn.close()
        except Exception as e:
            print(f"  Database error: {e}")
        print()
        return

    test = ProficiencyTest(level=args.level)
    if args.interactive:
        test.run_interactive()
    elif args.json:
        questions = test.generate(count=args.count)
        output = {
            "level": test.level,
            "description": test.cfg["desc"],
            "total": len(questions),
            "questions": questions,
        }
        print(
            json.dumps(
                output, indent=2, ensure_ascii=False
            )
        )
    else:
        questions = test.generate(count=args.count)
        print(
            f"Generated {len(questions)} questions "
            f"for level {args.level}"
        )
        for i, q in enumerate(questions, 1):
            print(f"\nQ{i}: {q['question']}")
            if q.get("context"):
                print(f"  ({q['context']})")
            for j, opt in enumerate(q["options"]):
                print(f"  {j + 1}) {opt}")
            print(f"  → Answer: {q['answer'] + 1}")


if __name__ == "__main__":
    main()
