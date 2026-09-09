#!/usr/bin/env python3
"""
RAG→OpenRouter Bridge
Injects Bible context into OpenRouter API calls for accurate Zolai responses.

Usage:
    python3 rag_openrouter_bridge.py "Na pai hiam?"
    python3 rag_openrouter_bridge.py --interactive
    python3 rag_openrouter_bridge.py --test
"""
import json
import os
import sys
import re
from pathlib import Path
from typing import Optional

# Try to import requests
try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip install requests -q")
    import requests

# ============================================
# CONFIGURATION
# ============================================
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
if not OPENROUTER_API_KEY:
    env_file = Path(__file__).resolve().parents[3] / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                OPENROUTER_API_KEY = line.split("=", 1)[1].strip()
                break

# Best free model (from testing)
DEFAULT_MODEL = "nex-agi/nex-n2.5-pro:free"

# English→Zolai mapping for RAG lookup
EN_ZO_MAP = {
  "i": ["ka", "kei"],
  "you": ["na", "nang"],
  "he": ["a", "amah"],
  "she": ["a", "amah"],
  "we": ["i", "ko", "ei"],
  "they": ["amau", "amaute"],
  "go": ["pai"],
  "see": ["mu"],
  "eat": ["nek", "note"],
  "drink": ["dawn"],
  "know": ["thei"],
  "say": ["ci", "gen"],
  "give": ["pia"],
  "die": ["si"],
  "dead": ["si"],
  "create": ["bawl"],
  "make": ["bawl"],
  "god": ["pasian"],
  "lord": ["topa"],
  "king": ["kumpi"],
  "land": ["gam"],
  "life": ["tapa"],
  "son": ["tapa"],
  "water": ["tui"],
  "man": ["mi", "mipa"],
  "woman": ["numei"],
  "not": ["kei", "lo"],
  "negation": ["kei"],
  "question": ["hiam"],
  "future": ["ding"],
  "past": ["ciangin"],
  "plural": ["uh"],
  "and": ["leh"],
  "with": ["tawh"],
  "five": ["nga"],
  "grandmother": ["pi"],
  "palace": ["kumpi", "inn"],
  "house": ["inn"],
  "face": ["mai"],
  "front": ["mai"],
  "drink": ["dawn"],
  "born": ["piang"],
  "created": ["piangsak"],
  "died": ["si", "si hi"],
  "goes": ["pai hi"],
  "will go": ["pai ding hi"],
  "don't go": ["pai kei hi"],
  "don't": ["kei"],
  "do you go": ["na pai hiam"],
  "why": ["bang hang"],
  "where": ["kua"],
  "what": ["bang"],
  "yes/no": ["hiam"]
}


# Data paths
DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "bible"
CORPUS_FILE = DATA_DIR / "parallel_corpus_v1.jsonl"
VOCAB_FILE = DATA_DIR / "vocab_index_full.jsonl"
GRAMMAR_FILE = DATA_DIR / "grammar_patterns_v2.jsonl"
PHRASES_FILE = DATA_DIR / "phrases_v1.jsonl"

# ============================================
# SYSTEM PROMPT (Corrected)
# ============================================
SYSTEM_PROMPT = """You are a Tedim Zolai language expert. Answer questions about Zolai grammar, vocabulary, and translation.

CRITICAL RULES:
1. ZVS 2018 orthography ONLY — use pasian (NOT pathian), gam (NOT ram), tapa (NOT fapa), topa (NOT bawipa), kumpipa (NOT siangpahrang), tua (NOT cu/cun)
2. SOV word order: Subject-Object-Verb
3. Negation: kei for ALL persons (NOT lo for 3rd person)
4. Question: hiam at end of sentence (NOT ze)
5. Verb agreement markers: ka=I, na=you, a=he/she, i=we(incl), ko=we(excl)
6. Plural marker: uh (NOT "they" pronoun)
7. Die/dead: si (NOT negation)
8. Drink: dawn (NOT pi)
9. Five: nga (NOT pi)
10. Give: pia (NOT pi)
11. Grandmother: pi (NOT five/cubit)
12. King: kumpi (NOT palace)
13. They: amau/amaute (NOT uh)

GRAMMAR PATTERNS:
- Present: Subject + Verb + hi (Ka pai hi = I go)
- Future: Subject + Verb + ding + hi (Ka pai ding hi = I will go)
- Past: Subject + ciangin + Verb + hi (A pai ciangin hi = He went)
- Negation: Subject + kei + Verb + hi (Ka pai kei hi = I don't go)
- Question: Subject + Verb + hiam? (Na pai hiam? = Do you go?)
- Content question: bang hang + Verb + Subject + hiam? (Bang hang pai na hiam? = Why do you go?)
- Emphasis: Amah + a + Verb + hi (Amah a pai hi = HE goes)

RESPOND IN ZOLAI with English translation. Use Bible examples when available."""


class RAGOpenRouterBridge:
    """RAG bridge that injects Bible context into OpenRouter API calls."""

    def __init__(self):
        self.corpus = []
        self.vocab = {}
        self.grammar = []
        self.phrases = []
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy load all data files."""
        if self._loaded:
            return

        print("Loading data files...")

        # Load corpus
        if CORPUS_FILE.exists():
            with open(CORPUS_FILE) as f:
                for line in f:
                    self.corpus.append(json.loads(line))
            print(f"  Corpus: {len(self.corpus)} verses")

        # Load vocab
        if VOCAB_FILE.exists():
            with open(VOCAB_FILE) as f:
                for line in f:
                    w = json.loads(line)
                    self.vocab[w["word"]] = w
            print(f"  Vocab: {len(self.vocab)} words")

        # Load grammar
        if GRAMMAR_FILE.exists():
            with open(GRAMMAR_FILE) as f:
                for line in f:
                    self.grammar.append(json.loads(line))
            print(f"  Grammar: {len(self.grammar)} patterns")

        # Load phrases
        if PHRASES_FILE.exists():
            with open(PHRASES_FILE) as f:
                for line in f:
                    self.phrases.append(json.loads(line))
            print(f"  Phrases: {len(self.phrases)} phrases")

        self._loaded = True

    def translate_query_to_zolai(self, query: str) -> list:
        """Translate English query words to Zolai for better RAG lookup."""
        words = re.findall(r"[a-zA-Z''-]+", query.lower())
        zolai_words = []
        for word in words:
            if word in EN_ZO_MAP:
                zolai_words.extend(EN_ZO_MAP[word])
            else:
                zolai_words.append(word)
        return zolai_words

    def extract_zolai_words(self, text: str) -> list:
        """Extract Zolai words from text."""
        # Clean and split
        words = re.findall(r"[a-zA-Z''-]+", text.lower())
        # Filter out English stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "can", "shall", "must",
            "i", "you", "he", "she", "it", "we", "they", "me", "him",
            "her", "us", "them", "my", "your", "his", "its", "our",
            "their", "this", "that", "these", "those", "what", "which",
            "who", "whom", "where", "when", "why", "how", "not", "no",
            "yes", "and", "or", "but", "if", "then", "else", "so",
            "for", "of", "in", "on", "at", "to", "from", "by", "with",
        }
        # Also check English→Zolai mapping
        zolai_words = []
        for w in words:
            if w not in stop_words and len(w) > 1:
                zolai_words.append(w)
                if w in EN_ZO_MAP:
                    zolai_words.extend(EN_ZO_MAP[w])
        return list(set(zolai_words))  # Remove duplicates

    def lookup_vocab(self, word: str) -> Optional[dict]:
        """Look up a word in the vocabulary."""
        self._ensure_loaded()
        return self.vocab.get(word)

    def search_corpus(self, query: str, max_results: int = 5) -> list:
        """Search corpus for verses containing query words."""
        self._ensure_loaded()
        words = self.extract_zolai_words(query)
        if not words:
            return []

        results = []
        for verse in self.corpus:
            zo = (verse.get("zo_tdb77") or verse.get("zo_tedim2010") or "").lower()
            if not zo:
                continue

            # Check if any query words appear in the verse
            match_count = sum(1 for w in words if w in zo)
            if match_count > 0:
                results.append({
                    "ref": verse.get("ref", ""),
                    "zo": verse.get("zo_tdb77") or verse.get("zo_tedim2010") or "",
                    "en": verse.get("en_kJV") or "",
                    "match_score": match_count,
                })

        # Sort by match score
        results.sort(key=lambda x: -x["match_score"])
        return results[:max_results]

    def search_phrases(self, query: str, max_results: int = 3) -> list:
        """Search phrases for matching expressions."""
        self._ensure_loaded()
        words = self.extract_zolai_words(query)
        if not words:
            return []

        results = []
        for phrase in self.phrases:
            zo = phrase.get("zo", "").lower()
            if not zo:
                continue

            match_count = sum(1 for w in words if w in zo)
            if match_count > 0:
                results.append({
                    "zo": phrase.get("zo", ""),
                    "en": phrase.get("en", ""),
                    "match_score": match_count,
                })

        results.sort(key=lambda x: -x["match_score"])
        return results[:max_results]

    def build_rag_context(self, query: str) -> str:
        """Build RAG context from Bible data."""
        self._ensure_loaded()

        context_parts = []

        # 1. Vocabulary lookups
        words = self.extract_zolai_words(query)
        vocab_context = []
        for word in words[:10]:  # Limit to 10 words
            entry = self.lookup_vocab(word)
            if entry:
                trans = entry.get("translations", ["?"])[0]
                notes = entry.get("notes", "")
                vocab_context.append(f"- {word}: {trans}")
                if notes:
                    vocab_context.append(f"  Note: {notes}")

        if vocab_context:
            context_parts.append("VOCABULARY:\n" + "\n".join(vocab_context))

        # 2. Bible verse examples
        verses = self.search_corpus(query, max_results=3)
        if verses:
            verse_examples = []
            for v in verses:
                verse_examples.append(
                    f"- {v['ref']}: {v['zo']}\n  EN: {v['en']}"
                )
            context_parts.append("BIBLE EXAMPLES:\n" + "\n".join(verse_examples))

        # 3. Phrase matches
        phrases = self.search_phrases(query, max_results=3)
        if phrases:
            phrase_examples = []
            for p in phrases:
                phrase_examples.append(f"- {p['zo']} = {p['en']}")
            context_parts.append("PHRASES:\n" + "\n".join(phrase_examples))

        # 4. Grammar patterns (if query seems grammar-related)
        grammar_keywords = [
            "negation", "question", "tense", "future", "past",
            "plural", "singular", "pronoun", "verb", "particle",
            "kei", "lo", "hiam", "ding", "uh", "in", "a",
        ]
        if any(kw in query.lower() for kw in grammar_keywords):
            grammar_matches = []
            for g in self.grammar[:20]:  # Limit
                pattern = g.get("pattern", "")
                if any(kw in pattern.lower() for kw in query.lower().split()):
                    grammar_matches.append(
                        f"- {g.get('name', 'unknown')}: {pattern}"
                    )
            if grammar_matches:
                context_parts.append(
                    "GRAMMAR PATTERNS:\n" + "\n".join(grammar_matches[:5])
                )

        return "\n\n".join(context_parts) if context_parts else "No specific context found."

    def query_openrouter(
        self, user_query: str, model: str = DEFAULT_MODEL
    ) -> str:
        """Query OpenRouter with RAG context."""
        if not OPENROUTER_API_KEY:
            return "ERROR: OPENROUTER_API_KEY not set"

        # Build RAG context
        rag_context = self.build_rag_context(user_query)

        # Build messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Bible Context:\n{rag_context}\n\nQuestion: {user_query}",
            },
        ]

        # Call OpenRouter
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://zolai.space",
            "X-Title": "Zolai AI",
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 1024,
            "temperature": 0.3,
        }

        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if resp.status_code == 429:
                return "ERROR: Rate limit exceeded. Try again later."

            if resp.status_code != 200:
                return f"ERROR: {resp.status_code} - {resp.text[:200]}"

            data = resp.json()
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            return f"ERROR: {str(e)}"

    def test(self):
        """Run test queries."""
        test_queries = [
            "How do you say 'I go' in Zolai?",
            "What is the negation pattern?",
            "How do you ask a question?",
            "What does 'pasian' mean?",
            "Translate: He died.",
        ]

        print("=" * 60)
        print("RAG→OpenRouter Bridge Test")
        print("=" * 60)

        for query in test_queries:
            print(f"\n{'='*60}")
            print(f"Query: {query}")
            print("-" * 60)

            # Show RAG context
            rag_context = self.build_rag_context(query)
            print(f"\nRAG Context (first 500 chars):")
            print(rag_context[:500])

            # Query OpenRouter
            print(f"\nAI Response:")
            response = self.query_openrouter(query)
            print(response)

        print(f"\n{'='*60}")
        print("Test complete!")


def main():
    bridge = RAGOpenRouterBridge()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            bridge.test()
        elif sys.argv[1] == "--interactive":
            print("Zolai RAG→OpenRouter Bridge (interactive mode)")
            print("Type 'quit' to exit\n")
            while True:
                query = input("You: ").strip()
                if query.lower() in ("quit", "exit", "q"):
                    break
                if query:
                    response = bridge.query_openrouter(query)
                    print(f"\nAI: {response}\n")
        else:
            query = " ".join(sys.argv[1:])
            response = bridge.query_openrouter(query)
            print(response)
    else:
        print("Usage:")
        print("  python3 rag_openrouter_bridge.py 'Na pai hiam?'")
        print("  python3 rag_openrouter_bridge.py --interactive")
        print("  python3 rag_openrouter_bridge.py --test")


if __name__ == "__main__":
    main()
