#!/usr/bin/env python3
# ruff: noqa: E501
"""Zolai Proficiency Test — A1 to C2 levels.

Generates multiple-choice questions from Bible corpus,
vocabulary index, and dictionary data.
"""
import json
import random
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
CORPUS = (
    WORKSPACE / "data" / "bible"
    / "parallel_corpus_v1.jsonl"
)
VOCAB = (
    WORKSPACE / "data" / "bible"
    / "vocab_index_full.jsonl"
)
DICT_FILE = (
    WORKSPACE / "data" / "dictionary" / "processed"
    / "dict_zo_en_master_v1.jsonl"
)

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
    ("cu", "While / during"),
    ("si", "Negative imperative"),
    ("te", "Past tense"),
    ("ci", "Quotative (said)"),
]


def load_corpus():
    """Load parallel Bible verses."""
    data = []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
    return data


def load_vocab():
    """Load vocabulary index."""
    data = []
    with open(VOCAB, encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
    return data


def load_dict():
    """Load Zolai→English dictionary."""
    data = []
    with open(DICT_FILE, encoding="utf-8") as f:
        for line in f:
            data.append(json.loads(line))
    return data


def tokenize(text):
    """Split text into word tokens."""
    # Remove punctuation and split
    clean = text.replace(";", "").replace(",", "")
    clean = clean.replace(".", "").replace("'", "")
    return [w for w in clean.split() if w]


def get_translation(word, dict_data):
    """Look up English translation for a Zolai word."""
    wl = word.lower()
    for entry in dict_data:
        if entry.get("zolai", "").lower() == wl:
            eng = entry.get("english", [])
            if isinstance(eng, list) and eng:
                return str(eng[0])
            elif eng:
                return str(eng)
    return None


def get_vocab_translations(word, vocab_data):
    """Get translation from vocab index."""
    for entry in vocab_data:
        if entry.get("word", "").lower() == word.lower():
            trans = entry.get("translations", [])
            if isinstance(trans, list) and trans:
                return str(trans[0])
    return None


class ProficiencyTest:
    """Zolai proficiency test generator."""

    def __init__(self, level="A1"):
        self.level = level.upper()
        if self.level not in LEVELS:
            print(f"Unknown level: {level}")
            print("Valid: " + ", ".join(LEVELS.keys()))
            sys.exit(1)
        self.cfg = LEVELS[self.level]
        self.corpus = []
        self.vocab = []
        self.dict_data = []
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy-load data on first use."""
        if self._loaded:
            return
        print("Loading data...", file=sys.stderr)
        self.corpus = load_corpus()
        self.vocab = load_vocab()
        self.dict_data = load_dict()
        self._loaded = True
        # Build vocab lookup
        self.vocab_map = {}
        for v in self.vocab:
            w = v.get("word", "")
            if w:
                self.vocab_map[w.lower()] = v
        # Build dict lookup
        self.dict_map = {}
        for d in self.dict_data:
            w = d.get("zolai", "")
            if w:
                self.dict_map[w.lower()] = d

    def _pick_random_vocab(self, n):
        """Pick n random vocab entries with translations."""
        self._ensure_loaded()
        good = []
        for v in self.vocab:
            trans = v.get("translations", [])
            if isinstance(trans, list) and trans:
                t = str(trans[0]).strip()
                if t and len(t) > 2:
                    good.append(v)
        if not good:
            # Fallback: use dict
            for d in self.dict_data:
                eng = d.get("english", [])
                if isinstance(eng, list) and eng:
                    good.append({
                        "word": d.get("zolai", ""),
                        "translations": eng,
                        "frequency": 0,
                    })
        return random.sample(good, min(n, len(good)))

    def _pick_random_sentences(self, n):
        """Pick n random Bible verses with translations."""
        self._ensure_loaded()
        # Filter to short/medium verses
        good = []
        for v in self.corpus:
            zo = v.get("zo_tdb77", "")
            en = v.get("en_kJV", "")
            if not zo or not en:
                continue
            zo_words = tokenize(zo)
            if 3 <= len(zo_words) <= 15:
                good.append(v)
        return random.sample(good, min(n, len(good)))

    def vocab_questions(self, n):
        """Multiple choice: what does this Zolai word mean?"""
        items = self._pick_random_vocab(n)
        questions = []
        for item in items:
            word = item.get("word", "")
            trans_list = item.get("translations", [])
            if isinstance(trans_list, list):
                correct = str(trans_list[0]) if trans_list else "?"
            else:
                correct = str(trans_list)
            # Truncate long translations
            if len(correct) > 60:
                correct = correct[:57] + "..."
            # Pick 3 wrong answers
            distractors = self._get_distractors(
                correct, self.vocab, key="translations"
            )
            options = [correct] + distractors
            random.shuffle(options)
            questions.append({
                "type": "vocab",
                "question": (
                    "What does the Zolai word "
                    f"'{word}' mean?"
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
            # Pick 3 wrong English translations
            distractors = self._get_sentence_distractors(
                en, self.corpus
            )
            options = [en] + distractors
            random.shuffle(options)
            questions.append({
                "type": "sentence",
                "question": (
                    f"Translate: {zo}"
                ),
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
            # Pick a random pattern
            pat_idx = random.randint(
                0, len(GRAMMAR_PATTERNS) - 1
            )
            if pat_idx in used:
                continue
            used.add(pat_idx)
            pat_code, pat_desc = GRAMMAR_PATTERNS[pat_idx]
            # Create 4 options: correct + 3 wrong
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
            # Clean up distractors
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
        # Words with multiple meanings
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
            # Pad to 4 options
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
            # Get distractors from other verses
            distractors = self._get_sentence_distractors(
                en, self.corpus
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

    def _get_distractors(
        self, correct, data, key="translations"
    ):
        """Pick 3 wrong answers from vocab data."""
        candidates = []
        for item in data:
            trans = item.get(key, [])
            if isinstance(trans, list):
                t = str(trans[0]) if trans else ""
            else:
                t = str(trans)
            if t and t != correct and len(t) > 2:
                candidates.append(t)
            if len(candidates) >= 20:
                break
        random.shuffle(candidates)
        return candidates[:3]

    def _get_sentence_distractors(self, correct, corpus):
        """Pick 3 wrong English sentences."""
        candidates = []
        for v in corpus:
            en = v.get("en_kJV", "")
            if en and en != correct:
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
            print(f"🏆 Excellent! Level {self.level} passed!")
        elif pct >= 70:
            print(f"👍 Good. Level {self.level} passed!")
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
        # Data stats
        print("═══ Data Sources ═══")
        try:
            c = load_corpus()
            print(f"  Bible verses: {len(c):,}")
        except FileNotFoundError:
            print("  Bible verses: NOT FOUND")
        try:
            v = load_vocab()
            print(f"  Vocabulary: {len(v):,}")
        except FileNotFoundError:
            print("  Vocabulary: NOT FOUND")
        try:
            d = load_dict()
            print(f"  Dictionary: {len(d):,}")
        except FileNotFoundError:
            print("  Dictionary: NOT FOUND")
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
            print(
                f"\nQ{i}: {q['question']}"
            )
            if q.get("context"):
                print(f"  ({q['context']})")
            for j, opt in enumerate(q["options"]):
                print(f"  {j + 1}) {opt}")
            print(f"  → Answer: {q['answer'] + 1}")


if __name__ == "__main__":
    main()
