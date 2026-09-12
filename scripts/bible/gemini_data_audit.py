#!/usr/bin/env python3
"""Gemini-Powered Data Audit — checks ALL Zolai data sources for accuracy.
Compares our dictionary, wiki grammar, training data, and Bible translations
against Gemini's Zolai knowledge. Logs every discrepancy for fixing.

Usage:
  python3 gemini_data_audit.py --all           # Run full audit
  python3 gemini_data_audit.py --dictionary    # Audit dictionary only
  python3 gemini_data_audit.py --grammar       # Audit grammar wiki only
  python3 gemini_data_audit.py --training      # Audit training data only
  python3 gemini_data_audit.py --bible         # Audit Bible translations only
  python3 gemini_data_audit.py --report        # Generate report from existing logs
"""

import asyncio
import argparse
import json
import re
import sys
import time
from pathlib import Path
from collections import defaultdict

WEB_API_PATH = '/home/peter/Documents/Project/pcore/pcore-webai/packages/gemini-webapi'


from gemini_cookies import get_gemini_client

DATA_ROOT = Path("/home/peter/Documents/Projects/zolai-ai/data")
WIKI_ROOT = Path("/home/peter/Documents/Projects/zolai-ai/zolai-wiki")
LOG_DIR = DATA_ROOT / "audit_logs"
LOG_DIR.mkdir(exist_ok=True)

MODEL = "gemini-3-flash"  # Fast model for bulk audit


async def gemini_query(prompt: str) -> str:
    """Query Gemini web and return cleaned response."""
    try:
        client = get_gemini_client()
        output = await client.generate_content(prompt=prompt, model=MODEL)
        text = output.text or ""
        if "<ElicitationsGroup" in text:
            text = text[:text.index("<ElicitationsGroup")].strip()
        return text.strip()
    except Exception as e:
        return f"ERROR: {e}"


def load_jsonl(path):
    """Load JSONL file."""
    data = []
    with open(path) as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def save_log(log_name, entries):
    """Save audit log as JSONL."""
    path = LOG_DIR / log_name
    with open(path, 'w') as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')
    print(f"  Saved {len(entries)} entries to {path}")


# ============================================================
# DICTIONARY AUDIT
# ============================================================

async def audit_dictionary():
    """Audit dictionary entries against Gemini knowledge."""
    print(f"\n{'='*60}")
    print("PHASE 1: DICTIONARY AUDIT")
    print(f"{'='*60}")

    entries = load_jsonl(DATA_ROOT / "dictionary/processed/dict_zo_en_master_v1.jsonl")
    
    # Sample 200 high-frequency words + 100 random for comprehensive check
    # First load Bible frequency
    bible_freq = {}
    with open(DATA_ROOT / "bible/ALL_WORDS_WITH_FREQUENCY.jsonl") as f:
        for line in f:
            e = json.loads(line)
            bible_freq[e.get('word', '')] = e.get('freq', 0)

    # Sort entries by Bible frequency (most important first)
    scored = []
    for e in entries:
        z = e.get('zolai', '').strip()
        if len(z) < 2 or re.search(r'[\x00-\x1f<>]', z):
            continue
        freq = bible_freq.get(z.lower(), 0)
        scored.append((freq, e))
    
    scored.sort(key=lambda x: -x[0])
    
    # Take top 150 high-freq + 50 random low-freq
    test_entries = [e for _, e in scored[:150]]
    import random
    low_freq = [e for f, e in scored if f <= 2 and len(e.get('zolai', '')) > 2]
    if len(low_freq) > 50:
        test_entries.extend(random.sample(low_freq, 50))
    else:
        test_entries.extend(low_freq)

    print(f"Testing {len(test_entries)} dictionary entries...")
    
    discrepancies = []
    batch_size = 10
    
    for i in range(0, len(test_entries), batch_size):
        batch = test_entries[i:i+batch_size]
        # Build batch prompt
        words = []
        for e in batch:
            z = e.get('zolai', '')
            our_en = e.get('english_clean', '') or str(e.get('english', ''))
            if isinstance(our_en, list):
                our_en = ', '.join(our_en)
            words.append(f"- {z}: our definition = {our_en[:80]}")
        
        prompt = f"""You are a Tedim Zolai language expert. Check these Zolai→English dictionary entries.
For each word, tell me:
1. Is our definition CORRECT or WRONG?
2. What is the correct English meaning?
3. Are there additional meanings we're missing?

Words to check:
{chr(10).join(words)}

Reply in this EXACT JSON format for each word:
WORD|CORRECT/WRONG|correct_meaning|missing_meanings
Example: pasian|CORRECT|God|
Example: gam|WRONG|earth/land|cosmos"""

        response = await gemini_query(prompt)
        
        # Parse response
        for line in response.split('\n'):
            line = line.strip()
            if '|' in line and line[0].isalpha():
                parts = line.split('|', 3)
                if len(parts) >= 3:
                    word = parts[0].strip()
                    verdict = parts[1].strip().upper()
                    correct = parts[2].strip() if len(parts) > 2 else ''
                    missing = parts[3].strip() if len(parts) > 3 else ''
                    
                    # Find matching entry
                    for e in batch:
                        if e.get('zolai', '').lower() == word.lower():
                            our_en = e.get('english_clean', '') or str(e.get('english', ''))
                            if isinstance(our_en, list):
                                our_en = ', '.join(our_en)
                            
                            if verdict == 'WRONG':
                                discrepancies.append({
                                    'phase': 'dictionary',
                                    'word': word,
                                    'our_definition': our_en[:100],
                                    'gemini_says': correct,
                                    'missing': missing,
                                    'severity': 'HIGH',
                                    'status': 'NEEDS_FIX'
                                })
                            elif missing:
                                discrepancies.append({
                                    'phase': 'dictionary',
                                    'word': word,
                                    'our_definition': our_en[:100],
                                    'gemini_says': correct or our_en,
                                    'missing': missing,
                                    'severity': 'MEDIUM',
                                    'status': 'NEEDS_UPDATE'
                                })
                            break
        
        # Rate limit: 1 request per 2 seconds
        await asyncio.sleep(2)
        
        if (i + batch_size) % 50 == 0:
            print(f"  Processed {min(i+batch_size, len(test_entries))}/{len(test_entries)} entries, {len(discrepancies)} discrepancies found...")

    save_log("dictionary_audit.jsonl", discrepancies)
    
    high = sum(1 for d in discrepancies if d['severity'] == 'HIGH')
    med = sum(1 for d in discrepancies if d['severity'] == 'MEDIUM')
    print(f"\n  DICTIONARY AUDIT COMPLETE: {high} HIGH, {med} MEDIUM discrepancies")
    return discrepancies


# ============================================================
# GRAMMAR WIKI AUDIT
# ============================================================

async def audit_grammar():
    """Audit wiki grammar files against Gemini knowledge."""
    print(f"\n{'='*60}")
    print("PHASE 2: GRAMMAR WIKI AUDIT")
    print(f"{'='*60}")

    grammar_files = list(WIKI_ROOT.glob("grammar/*.md"))
    print(f"Found {len(grammar_files)} grammar files")
    
    discrepancies = []
    
    # Key grammar rules to verify
    rules_to_check = [
        ("Word Order", "Zolai word order is SOV (Subject-Object-Verb). The verb ALWAYS comes last. Agreement markers (ka/na/a) go directly before the verb.", "A pai khin hi = He went. (A=past_subject, pai=go, khin=past, hi=declarative)"),
        ("Negation", "kei is the standard negation particle for ALL persons. lo is literary/formal and standalone (no agreement marker).", "Ka pai kei hi = I don't go. / Pai lo hi = Goes not. (NOT: A pai lo hi)"),
        ("Past Tense", "khin = past simple / experiential. ta = completive/realized aspect (NOT past!). ding = future.", "A pai khin hi = He went. / A pai ta hi = He finished going."),
        ("Questions", "hiam = yes/no question (formal). hia = yes/no question (informal). bang hang = content question.", "Na pai hiam? = Do you go? / Bang hang pai na hiam? = Why do you go?"),
        ("Pronouns", "hihte = they (respectful). amaute = they (standard). huate = those/them. u = elder brother/sister. nau = younger.", "Amaute pai khin hi = They went."),
        ("Ergative", "in = ergative marker for transitive agents. Optional with agreement markers.", "Pasian in leitung a piangsak hi = God created the earth."),
        ("Love/Companion", "it = love (verb). itna = love (noun). ki-it = love each other. sanggam = brother/companion (560x Bible).", "Amaute a u a nau a it hi = They love their brother."),
        ("Eating", "ne = general eating/drinking. nek = specific/conditional (if you eat that).", "Na ne hiam? = Do you eat?"),
        ("Work", "nasep = work/service (general). kammal = deed/action/commandment.", "Nasep a mankhin ta hi = The work is done."),
        ("Nature", "singkung = tree (living plant). sing = wood (material). lasak = sing OR take something.", "Nau a lasak hi = The younger sister sings."),
    ]
    
    for rule_name, correct_rule, example in rules_to_check:
        prompt = f"""You are a Tedim Zolai language expert. Verify this grammar rule:

RULE: {rule_name}
STATED RULE: {correct_rule}
EXAMPLE: {example}

Is this rule CORRECT? Are there any errors or missing information?
Reply: CORRECT|details or WRONG|correction"""

        response = await gemini_query(prompt)
        
        verdict = 'CORRECT' if response.upper().startswith('CORRECT') else 'NEEDS_CHECK'
        correction = response[7:].strip() if response.upper().startswith('WRONG|') else ''
        
        if verdict == 'NEEDS_CHECK':
            discrepancies.append({
                'phase': 'grammar',
                'rule': rule_name,
                'our_rule': correct_rule,
                'gemini_response': response[:200],
                'severity': 'HIGH',
                'status': 'NEEDS_VERIFY'
            })
        else:
            discrepancies.append({
                'phase': 'grammar',
                'rule': rule_name,
                'our_rule': correct_rule,
                'gemini_response': 'CONFIRMED',
                'severity': 'OK',
                'status': 'VERIFIED'
            })
        
        await asyncio.sleep(2)

    save_log("grammar_audit.jsonl", discrepancies)
    issues = [d for d in discrepancies if d['severity'] != 'OK']
    print(f"  GRAMMAR AUDIT COMPLETE: {len(issues)} issues, {len(discrepancies)-len(issues)} verified OK")
    return discrepancies


# ============================================================
# TRAINING DATA AUDIT
# ============================================================

async def audit_training():
    """Audit sample training sentences against Gemini."""
    print(f"\n{'='*60}")
    print("PHASE 3: TRAINING DATA AUDIT")
    print(f"{'='*60}")

    # Load sample from different training files
    samples = {}
    for fname in ['negation_exercises.jsonl', 'question_exercises.jsonl', 'pronoun_exercises.jsonl']:
        path = DATA_ROOT / "bible" / fname
        if path.exists():
            data = load_jsonl(path)[:10]  # Sample 10 from each
            samples[fname] = data
    
    # Also sample from verified phrases
    phrases_path = DATA_ROOT / "dictionary/processed/phrases_verified.jsonl"
    if phrases_path.exists():
        data = load_jsonl(phrases_path)[:10]
        samples['phrases'] = data
    
    discrepancies = []
    
    for source, entries in samples.items():
        print(f"  Checking {source}...")
        
        # Build batch prompt
        items = []
        for e in entries:
            if 'zo' in e and 'en' in e:
                items.append(f"ZOLAI: {e['zo'][:100]} → ENGLISH: {e['en'][:100]}")
            elif 'zolai' in e and 'english' in e:
                en = e.get('english', '')
                if isinstance(en, list):
                    en = ', '.join(en[:3])
                items.append(f"ZOLAI: {e['zolai'][:100]} → ENGLISH: {en[:100]}")
        
        if not items:
            continue
        
        prompt = f"""You are a Tedim Zolai language expert. Check these Zolai-English pairs.
For each pair, reply: CORRECT|details or WRONG|correction

{chr(10).join(items[:10])}"""
        
        response = await gemini_query(prompt)
        
        for line in response.split('\n'):
            line = line.strip()
            if '|' in line:
                parts = line.split('|', 1)
                verdict = parts[0].strip().upper()
                detail = parts[1].strip() if len(parts) > 1 else ''
                
                if 'WRONG' in verdict:
                    discrepancies.append({
                        'phase': 'training',
                        'source': source,
                        'content': detail[:200],
                        'severity': 'HIGH',
                        'status': 'NEEDS_FIX'
                    })
        
        await asyncio.sleep(2)

    save_log("training_audit.jsonl", discrepancies)
    print(f"  TRAINING AUDIT COMPLETE: {len(discrepancies)} discrepancies")
    return discrepancies


# ============================================================
# BIBLE TRANSLATION AUDIT
# ============================================================

async def audit_bible():
    """Audit key Bible translations against Gemini."""
    print(f"\n{'='*60}")
    print("PHASE 4: BIBLE TRANSLATION AUDIT")
    print(f"{'='*60}")

    # Load key verses for checking
    key_verses = []
    with open(DATA_ROOT / "bible/parallel_corpus_v1.jsonl") as f:
        for line in f:
            e = json.loads(line)
            ref = e.get('ref', '')
            # Check key verses from Genesis, Psalms, New Testament
            if ref.startswith(('GEN 1:', 'GEN 2:', 'PSA 23:', 'PSA 1:', 'JHN 1:', 'JHN 3:', 'MAT 5:', '1CO 13:', 'ROM 8:', 'PHI 4:')):
                key_verses.append(e)

    print(f"  Checking {len(key_verses)} key Bible verses...")
    
    discrepancies = []
    batch_size = 5
    
    for i in range(0, min(len(key_verses), 30), batch_size):
        batch = key_verses[i:i+batch_size]
        
        items = []
        for e in batch:
            ref = e.get('ref', '')
            zo = e.get('zo_tdb77', '')
            en = e.get('en_kJV', '')
            items.append(f"REFERENCE: {ref}\nENGLISH: {en[:150]}\nOUR ZOLAI: {zo[:150]}")
        
        prompt = f"""You are a Tedim Zolai Bible translation expert. Check these Bible translations.
For each verse, is our Zolai translation ACCURATE?

{chr(10).join(items)}

Reply for each verse:
REF|CORRECT/WRONG|correct_zolai_if_wrong|notes"""
        
        response = await gemini_query(prompt)
        
        for line in response.split('\n'):
            line = line.strip()
            if '|' in line and (line.startswith('GEN') or line.startswith('PSA') or line.startswith('JHN') or line.startswith('MAT') or line.startswith('1CO') or line.startswith('ROM') or line.startswith('PHI')):
                parts = line.split('|', 3)
                if len(parts) >= 2:
                    ref = parts[0].strip()
                    verdict = parts[1].strip().upper()
                    
                    if 'WRONG' in verdict:
                        correct = parts[2].strip() if len(parts) > 2 else ''
                        notes = parts[3].strip() if len(parts) > 3 else ''
                        discrepancies.append({
                            'phase': 'bible',
                            'reference': ref,
                            'our_translation': next((e.get('zo_tdb77', '')[:100] for e in batch if e.get('ref') == ref), ''),
                            'gemini_correction': correct,
                            'notes': notes,
                            'severity': 'HIGH',
                            'status': 'NEEDS_VERIFY'
                        })
        
        await asyncio.sleep(2)

    save_log("bible_audit.jsonl", discrepancies)
    print(f"  BIBLE AUDIT COMPLETE: {len(discrepancies)} discrepancies")
    return discrepancies


# ============================================================
# MASTER REPORT
# ============================================================

def generate_report(all_discrepancies):
    """Generate comprehensive audit report."""
    print(f"\n{'='*60}")
    print("MASTER AUDIT REPORT")
    print(f"{'='*60}")
    
    by_phase = defaultdict(list)
    for d in all_discrepancies:
        by_phase[d['phase']].append(d)
    
    report_lines = [
        f"# Zolai Data Audit Report",
        f"## Generated: {time.strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"### Summary",
        f"| Phase | HIGH | MEDIUM | OK | Total |",
        f"|-------|------|--------|-----|-------|",
    ]
    
    total_high = 0
    total_med = 0
    total_ok = 0
    
    for phase in ['dictionary', 'grammar', 'training', 'bible']:
        items = by_phase.get(phase, [])
        high = sum(1 for d in items if d.get('severity') == 'HIGH')
        med = sum(1 for d in items if d.get('severity') == 'MEDIUM')
        ok = sum(1 for d in items if d.get('severity') in ('OK', 'VERIFIED'))
        total_high += high
        total_med += med
        total_ok += ok
        report_lines.append(f"| {phase} | {high} | {med} | {ok} | {len(items)} |")
    
    report_lines.append(f"| **TOTAL** | **{total_high}** | **{total_med}** | **{total_ok}** | **{total_high+total_med+total_ok}** |")
    
    # Detailed findings per phase
    for phase in ['dictionary', 'grammar', 'training', 'bible']:
        items = by_phase.get(phase, [])
        issues = [d for d in items if d.get('severity') in ('HIGH', 'MEDIUM')]
        if issues:
            report_lines.append(f"\n### {phase.upper()} Issues ({len(issues)})")
            for d in issues[:20]:
                report_lines.append(f"- **{d.get('severity')}** [{d.get('status')}] {d.get('word', d.get('rule', d.get('reference', d.get('source', ''))))}: {d.get('our_definition', d.get('our_rule', d.get('content', d.get('our_translation', ''))))[:80]}")
                if d.get('gemini_says'):
                    report_lines.append(f"  → Gemini says: {d['gemini_says'][:80]}")
                if d.get('gemini_correction'):
                    report_lines.append(f"  → Correct: {d['gemini_correction'][:80]}")
                if d.get('gemini_response') and d['gemini_response'] != 'CONFIRMED':
                    report_lines.append(f"  → Gemini: {d['gemini_response'][:80]}")
    
    report_lines.append(f"\n### Data Quality Assessment")
    report_lines.append(f"- Dictionary: {total_high} wrong definitions need immediate fix")
    report_lines.append(f"- Grammar: {total_ok} rules verified by Gemini")
    report_lines.append(f"- Training: {total_med} training pairs need review")
    report_lines.append(f"- Bible: {total_high} translations need verification")
    
    report_text = '\n'.join(report_lines)
    report_path = LOG_DIR / "AUDIT_REPORT.md"
    with open(report_path, 'w') as f:
        f.write(report_text)
    
    print(f"\nReport saved to {report_path}")
    print(f"\nOVERALL: {total_high} HIGH issues, {total_med} MEDIUM issues, {total_ok} VERIFIED OK")
    
    return report_text


# ============================================================
# MAIN
# ============================================================

async def run_all():
    """Run full audit pipeline."""
    all_discrepancies = []
    
    d = await audit_dictionary()
    all_discrepancies.extend(d)
    
    g = await audit_grammar()
    all_discrepancies.extend(g)
    
    t = await audit_training()
    all_discrepancies.extend(t)
    
    b = await audit_bible()
    all_discrepancies.extend(b)
    
    generate_report(all_discrepancies)
    
    # Save master log
    save_log("all_discrepancies.jsonl", all_discrepancies)


async def main():
    parser = argparse.ArgumentParser(description="Gemini-powered Zolai data audit")
    parser.add_argument("--all", action="store_true", help="Run full audit")
    parser.add_argument("--dictionary", action="store_true", help="Audit dictionary only")
    parser.add_argument("--grammar", action="store_true", help="Audit grammar only")
    parser.add_argument("--training", action="store_true", help="Audit training data only")
    parser.add_argument("--bible", action="store_true", help="Audit Bible translations only")
    parser.add_argument("--report", action="store_true", help="Generate report from existing logs")
    args = parser.parse_args()
    
    if args.report:
        all_d = []
        for log_file in LOG_DIR.glob("*_audit.jsonl"):
            all_d.extend(load_jsonl(log_file))
        generate_report(all_d)
    elif args.all or not any([args.dictionary, args.grammar, args.training, args.bible]):
        await run_all()
    else:
        all_d = []
        if args.dictionary:
            all_d.extend(await audit_dictionary())
        if args.grammar:
            all_d.extend(await audit_grammar())
        if args.training:
            all_d.extend(await audit_training())
        if args.bible:
            all_d.extend(await audit_bible())
        if all_d:
            generate_report(all_d)


if __name__ == "__main__":
    asyncio.run(main())
