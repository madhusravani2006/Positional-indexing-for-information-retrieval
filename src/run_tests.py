"""Runs the 5 test cases + 10 rare terms and saves everything (UTF-8) to output.txt.
Usage:  python run_tests.py --index index_out --out output.txt
Test terms are picked automatically from your index, so it works for any language/dataset."""
import argparse
from searcher import PositionalIndex, fmt_entry, Tee, stats_text


def find_adjacent_pair(ix, pool=40):
    top = [t for t in sorted(ix.vocab, key=lambda t: -ix.vocab[t][0])[:pool] if len(t) >= 3]
    P = {t: ix.postings(t) for t in top}
    for a in top:
        for b in top:
            if a == b: continue
            for d in set(P[a]) & set(P[b]):
                pb = set(P[b][d])
                if any(p + 1 in pb for p in P[a][d]):
                    return a, b
    return top[0], top[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="index_out")
    ap.add_argument("--out", default="output.txt")
    a = ap.parse_args()
    ix, out = PositionalIndex(a.index), Tee(a.out)
    title = lambda d: f"d{d} = {ix.docs[d][0]}"

    out("=" * 70); out("INDEX STATISTICS"); out("=" * 70); out(stats_text(ix)); out()

    rare = ix.rare_terms(10)
    common = max(ix.vocab, key=lambda t: ix.vocab[t][1])
    pa, pb = find_adjacent_pair(ix)

    out("=" * 70); out("TEST CASE 1: rare term (appears once in the whole collection)"); out("=" * 70)
    out(fmt_entry(ix, rare[0])); out()

    out("=" * 70); out("TEST CASE 2: most frequent term (highest CF) - output truncated for display"); out("=" * 70)
    out(fmt_entry(ix, common, max_docs=3, max_pos=10)); out()

    out("=" * 70); out("TEST CASE 3: term that is NOT in the vocabulary"); out("=" * 70)
    out(fmt_entry(ix, "zzzzqqqq")); out()

    out("=" * 70); out(f'TEST CASE 4: phrase query "{pa} {pb}" (uses term positions)'); out("=" * 70)
    res = ix.phrase(f"{pa} {pb}")
    out(f"{len(res)} document(s) contain the phrase")
    for d, st in list(res.items())[:8]: out(f"  {title(d)}  starts at positions {st}")
    out()

    out("=" * 70); out(f"TEST CASE 5: proximity query  '{pa}' within 5 words of '{pb}'"); out("=" * 70)
    res = ix.proximity(pa, pb, 5)
    out(f"{len(res)} document(s) match")
    for d, pr in list(res.items())[:8]: out(f"  {title(d)}  (pos_a, pos_b) = {pr[:6]}")
    out()

    out("=" * 70); out("10 RARE TERMS WITH THEIR POSITIONAL INDEX"); out("=" * 70)
    for i, t in enumerate(rare, 1):
        out(f"[{i}] {fmt_entry(ix, t)}")
    out(); out(f"[postings read from disk during these tests: {ix.disk_reads}]")
    out.close()


if __name__ == "__main__":
    main()
