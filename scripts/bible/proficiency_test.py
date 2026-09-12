#!/usr/bin/env python3
"""
Proficiency Test — Uses database (zolai.db) for all data.
"""
import sys
import os
import random
import json
import sqlite3
from pathlib import Path

# Add local package
sys.path.insert(0, os.environ.get("ZOLAI_AI_LOCAL", "/home/peter/Documents/Projects/zolai-ai/zolai-ai-local"))

DB_PATH = Path(os.environ.get("DATA", "data")) / "zolai.db"


def get_db():
    return sqlite3.connect(DB_PATH)


class ProficiencyTest:
    def __init__(self):
        self._loaded = False
        self.zolai_pairs = []  # (zolai, english)
        self.verses = []       # Bible verses
        self.vocab_map = {}    # word -> frequency
    
    def _ensure_loaded(self):
        if self._loaded:
            return
        print("Loading data from database...", file=sys.stderr)
        conn = get_db()
        c = conn.cursor()
        
        # Load high-frequency vocab pairs (Zolai → English)
        c.execute("""
            SELECT v.headword, d.english_clean, v.frequency
            FROM vocab v
            JOIN dictionary d ON d.zolai = v.headword
            WHERE v.frequency > 100
            AND d.source = 'bible_zo_en'
            AND v.headword != d.english_clean
            AND LENGTH(d.english_clean) > 2
            ORDER BY v.frequency DESC
        """)
        self.zolai_pairs = [(r[0], r[1], r[2]) for r in c.fetchall()]
        
        # Load Bible verses (short, good for translation)
        c.execute("""
            SELECT ref, zo_tdb77, en_kJV
            FROM bible_verses
            WHERE zo_tdb77 IS NOT NULL AND en_kJV IS NOT NULL
            AND LENGTH(zo_tdb77) BETWEEN 10 AND 150
        """)
        self.verses = [{"ref": r[0], "zo": r[1], "en": r[2]} for r in c.fetchall()]
        
        # Build vocab map for frequency lookup
        c.execute("SELECT headword, frequency FROM vocab WHERE frequency > 10")
        self.vocab_map = {r[0]: r[1] for r in c.fetchall()}
        
        conn.close()
        self._loaded = True
        print(f"Loaded: {len(self.zolai_pairs)} vocab pairs, {len(self.verses)} verses", file=sys.stderr)
    
    def _pick_vocab(self, n: int) -> list:
        self._ensure_loaded()
        if not self.zolai_pairs:
            return []
        # Weight by frequency
        weights = [max(1, p[2]) for p in self.zolai_pairs]
        return random.choices(self.zolai_pairs, weights=weights, k=min(n, len(self.zolai_pairs)))
    
    def _pick_verses(self, n: int) -> list:
        self._ensure_loaded()
        if not self.verses:
            return []
        return random.sample(self.verses, min(n, len(self.verses)))
    
    def _get_distractors(self, correct: str, exclude_word: str = "", pool: list = None, n: int = 3) -> list:
        if pool is None:
            pool = self.zolai_pairs
        distractors = []
        attempts = 0
        while len(distractors) < n and attempts < n * 10:
            w, eng, _ = random.choice(pool)
            if w == exclude_word or eng == correct:
                attempts += 1
                continue
            if eng not in distractors:
                distractors.append(eng)
            attempts += 1
        # Fill if not enough
        while len(distractors) < n:
            distractors.append(f"option_{len(distractors)}")
        return distractors
    
    def vocab_questions(self, n: int) -> list:
        """What does this Zolai word mean?"""
        items = self._pick_vocab(n)
        questions = []
        for zolai, correct, freq in items:
            if not zolai or not correct:
                continue
            distractors = self._get_distractors(correct, zolai)
            options = [correct] + distractors
            random.shuffle(options)
            questions.append({
                "type": "vocab",
                "question": f"What does the Zolai word '{zolai}' mean in English?",
                "options": options,
                "answer": options.index(correct),
                "word": zolai,
                "translation": correct,
                "frequency": freq,
            })
        return questions
    
    def sentence_questions(self, n: int) -> list:
        """Translate this sentence."""
        items = self._pick_verses(n)
        questions = []
        for v in items:
            zo, en, ref = v["zo"], v["en"], v["ref"]
            # Use other verse translations as distractors
            distractors = []
            other_verses = [x for x in self.verses if x["en"] != en]
            for ov in random.sample(other_verses, min(3, len(other_verses))):
                distractors.append(ov["en"])
            while len(distractors) < 3:
                distractors.append("No translation available")
            
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
    
    def grammar_questions(self, n: int) -> list:
        """Identify grammar pattern."""
        self._ensure_loaded()
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT pattern, description, function, examples
            FROM grammar_patterns
            WHERE examples IS NOT NULL AND examples != ''
            ORDER BY RANDOM() LIMIT ?
        """, (n,))
        patterns = c.fetchall()
        conn.close()
        
        questions = []
        for pattern, desc, func, examples in patterns:
            # Create a sample sentence using the pattern
            example_refs = json.loads(examples) if examples.startswith('[') else [examples]
            example_ref = example_refs[0] if example_refs else "GEN 1:1"
            
            # Get the verse
            c = get_db().cursor()
            c.execute("SELECT zo_tdb77, en_kJV FROM bible_verses WHERE ref = ?", (example_ref,))
            verse = c.fetchone()
            
            if verse:
                zo, en = verse
                # Distractors: other grammar patterns
                c2 = get_db().cursor()
                c2.execute("""
                    SELECT pattern FROM grammar_patterns 
                    WHERE pattern != ? ORDER BY RANDOM() LIMIT 3
                """, (pattern,))
                distractors = [r[0] for r in c2.fetchall()]
            else:
                zo, en = "Example sentence", "Example translation"
                distractors = ["other_pattern_1", "other_pattern_2", "other_pattern_3"]
            
            options = [pattern] + distractors
            random.shuffle(options)
            questions.append({
                "type": "grammar",
                "question": f"Identify the grammar pattern in this sentence:\n{zo}",
                "context": example_ref,
                "options": options,
                "answer": options.index(pattern),
                "pattern": pattern,
                "description": desc,
            })
        return questions
    
    def negation_questions(self, n: int) -> list:
        """Negation pattern questions."""
        self._ensure_loaded()
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT zo_tdb77, en_kJV, ref FROM bible_verses
            WHERE zo_tdb77 LIKE '%kei%' OR zo_tdb77 LIKE '%lo %'
            ORDER BY RANDOM() LIMIT ?
        """, (n,))
        verses = c.fetchall()
        conn.close()
        
        questions = []
        for zo, en, ref in verses:
            # Determine negation type
            neg_type = "kei" if "kei" in zo else "lo"
            distractors = [x for x in ["kei (all persons)", "lo (standalone)", "kei + ding (future)", "lo + ding (future)"] if x != neg_type]
            options = [neg_type] + distractors[:2]
            random.shuffle(options)
            questions.append({
                "type": "negation",
                "question": f"What negation pattern is used in this sentence?\n{zo}",
                "context": ref,
                "options": options,
                "answer": options.index(neg_type),
                "negation_type": neg_type,
            })
        return questions
    
    def generate_test(self, level: str, count: int) -> dict:
        """Generate test for a level."""
        levels = {
            "A1": {"vocab": 8, "sentence": 2, "grammar": 0, "negation": 0},
            "A2": {"vocab": 12, "sentence": 4, "grammar": 2, "negation": 2},
            "B1": {"vocab": 10, "sentence": 6, "grammar": 4, "negation": 4},
            "B2": {"vocab": 8, "sentence": 6, "grammar": 6, "negation": 6},
            "C1": {"vocab": 6, "sentence": 6, "grammar": 8, "negation": 6},
            "C2": {"vocab": 4, "sentence": 4, "grammar": 10, "negation": 8},
        }
        
        config = levels.get(level.upper(), levels["A1"])
        
        all_q = []
        all_q.extend(self.vocab_questions(config["vocab"]))
        all_q.extend(self.sentence_questions(config["sentence"]))
        all_q.extend(self.grammar_questions(config["grammar"]))
        all_q.extend(self.negation_questions(config["negation"]))
        
        random.shuffle(all_q)
        selected = all_q[:count]
        
        return {
            "level": level.upper(),
            "total": len(selected),
            "questions": selected,
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zolai Proficiency Test")
    parser.add_argument("--level", default="A1", choices=["A1", "A2", "B1", "B2", "C1", "C2"])
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()
    
    test = ProficiencyTest()
    
    if args.stats:
        test._ensure_loaded()
        print(f"Vocab pairs (freq>100): {len(test.zolai_pairs)}")
        print(f"Bible verses: {len(test.verses)}")
        print(f"Vocab entries (freq>10): {len(test.vocab_map)}")
        return
    
    result = test.generate_test(args.level, args.count)
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\nZolai Proficiency Test — Level {result['level']}")
        print("=" * 50)
        for i, q in enumerate(result['questions'], 1):
            print(f"\n{i}. {q['question']}")
            if q.get('context'):
                print(f"   Context: {q['context']}")
            for j, opt in enumerate(q['options']):
                mark = "✓" if j == q['answer'] else " "
                print(f"   {mark} {chr(65+j)}) {opt}")
        print(f"\nTotal: {result['total']} questions")


if __name__ == "__main__":
    main()
