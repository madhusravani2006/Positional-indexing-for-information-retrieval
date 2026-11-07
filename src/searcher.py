"""Module 4 - searcher. Only the VOCABULARY (term -> DF, CF, offset, length) and the small
document table are held in main memory. A term's postings are fetched from the postings
file on disk with seek()+read() when (and only when) they are needed.

Commands
  lookup   TERM [TERM ...]      show  <term, DF, CF; doc: positions ...>
  phrase   "w1 w2 w3"           documents containing the exact phrase
  prox     "a /k b"             a and b within k words of each other
  bool     "a AND b", "a OR b", "a AND NOT b"
  rare     --n 10               N rare terms (CF = 1) with their positional index
  stats                         index statistics
Add  --out FILE  to also save the output (UTF-8) to a file.
"""
import argparse, os, sys

from preprocess import tokenize

if hasattr(sys.stdout, "reconfigure"):                       # make Kannada print safely on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class PositionalIndex:
    def __init__(self, index_dir):
        self.vocab = {}                                      # term -> (df, cf, offset, length)
        with open(os.path.join(index_dir, "vocabulary.tsv"), encoding="utf-8") as f:
            for line in f:
                t, df, cf, off, ln = line.rstrip("\n").split("\t")
                self.vocab[t] = (int(df), int(cf), int(off), int(ln))
        self.docs = {}                                       # docID -> (title, length)
        with open(os.path.join(index_dir, "docs.tsv"), encoding="utf-8") as f:
            for line in f:
                i, title, n = line.rstrip("\n").split("\t")
                self.docs[int(i)] = (title, int(n))
        self.pf = open(os.path.join(index_dir, "postings.txt"), "rb")   # stays on disk
        self.disk_reads = 0

    def postings(self, term):
        """Read ONE postings line from disk -> {docID: [positions]}"""
        entry = self.vocab.get(term)
        if not entry:
            return {}
        _, _, offset, length = entry
        self.pf.seek(offset)
        raw = self.pf.read(length).decode("utf-8").rstrip("\n")
        self.disk_reads += 1
        payload = raw.split("\t", 3)[3]
        out = {}
        for item in payload.split(";"):
            d, ps = item.split(":")
            out[int(d)] = [int(x) for x in ps.split(",")]
        return out

    # ---------------- retrieval ----------------
    def phrase(self, text):
        words = tokenize(text)
        if not words or any(w not in self.vocab for w in words):
            return {}
        plist = {w: self.postings(w) for w in set(words)}
        docs = set(plist[words[0]])
        for w in words[1:]:
            docs &= set(plist[w])
        hits = {}
        for d in sorted(docs):
            starts = [p for p in plist[words[0]][d]
                      if all((p + i) in set(plist[w][d]) for i, w in enumerate(words) if i)]
            if starts:
                hits[d] = starts
        return hits

    def proximity(self, a, b, k):
        pa, pb = self.postings(a), self.postings(b)
        hits = {}
        for d in sorted(set(pa) & set(pb)):
            pairs = [(x, y) for x in pa[d] for y in pb[d] if 0 < abs(x - y) <= k]
            if pairs:
                hits[d] = pairs
        return hits

    def boolean(self, query):
        """AND / OR / NOT (capitals). AND-only queries run smallest postings list first."""
        parts, all_docs = query.split(), sorted(self.docs)
        ids = lambda w: sorted(self.postings(tokenize(w)[0])) if tokenize(w) else []
        if "OR" not in parts:
            pos, neg, negate = [], [], False
            for p in parts:
                if p == "AND": continue
                if p == "NOT": negate = True; continue
                (neg if negate else pos).append(p); negate = False
            pos.sort(key=lambda w: self.vocab.get(tokenize(w)[0], (0,))[0] if tokenize(w) else 0)
            res = None
            for w in pos:
                res = ids(w) if res is None else sorted(set(res) & set(ids(w)))
                if not res: break
            res = all_docs if res is None else res
            for w in neg:
                res = [d for d in res if d not in set(ids(w))]
            return res
        res, op, negate = None, "AND", False
        for p in parts:
            if p in ("AND", "OR"): op = p
            elif p == "NOT": negate = True
            else:
                cur = [d for d in all_docs if d not in set(ids(p))] if negate else ids(p)
                negate = False
                res = cur if res is None else (sorted(set(res) & set(cur)) if op == "AND" else sorted(set(res) | set(cur)))
        return res or []

    def rare_terms(self, n=10, min_len=3):
        cands = sorted(t for t, (df, cf, _, _) in self.vocab.items()
                       if cf == 1 and len(t) >= min_len and not t[0].isdigit())
        if len(cands) <= n:
            cands = sorted(self.vocab, key=lambda t: (self.vocab[t][1], t))[:n]
            return cands
        return [cands[i * len(cands) // n] for i in range(n)]      # evenly spread sample


def fmt_entry(ix, term, max_docs=10, max_pos=20):
    """<term, DF=.., CF=..; d1: p1, p2; d7: p ...>  - truncates very long lists for display."""
    if term not in ix.vocab:
        return f"<{term}>  NOT IN VOCABULARY"
    df, cf, _, _ = ix.vocab[term]
    parts = []
    for i, (d, ps) in enumerate(ix.postings(term).items()):
        if max_docs and i >= max_docs:
            parts.append(f"... (+{df - max_docs} more documents)")
            break
        shown = ps if not max_pos or len(ps) <= max_pos else ps[:max_pos]
        more = "" if len(shown) == len(ps) else f", ... (+{len(ps) - len(shown)} more)"
        parts.append(f"d{d}: {', '.join(map(str, shown))}{more}")
    return f"<{term}, DF={df}, CF={cf};\n    " + ";\n    ".join(parts) + ">"


class Tee:
    """print() + optional copy into a UTF-8 file"""
    def __init__(self, path=None):
        self.f = open(path, "w", encoding="utf-8") if path else None
    def __call__(self, s=""):
        print(s)
        if self.f: self.f.write(s + "\n")
    def close(self):
        if self.f: self.f.close()


def stats_text(ix):
    tokens = sum(n for _, n in ix.docs.values())
    size = os.path.getsize(ix.pf.name) / 1e6
    return (f"documents: {len(ix.docs)} | tokens: {tokens} | vocabulary: {len(ix.vocab)} terms (in RAM)\n"
            f"postings file on disk: {size:.2f} MB")


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--index", default="index_out", help="index directory (default index_out)")
    common.add_argument("--out", default=None, help="also save output to this UTF-8 file")
    common.add_argument("--full", action="store_true", help="do not truncate long postings when printing")
    ap = argparse.ArgumentParser(description="Search the disk-based positional index")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lookup", parents=[common]).add_argument("terms", nargs="+")
    sub.add_parser("phrase", parents=[common]).add_argument("query")
    sub.add_parser("prox", parents=[common]).add_argument("query", help='e.g. "word1 /3 word2"')
    sub.add_parser("bool", parents=[common]).add_argument("query")
    r = sub.add_parser("rare", parents=[common]); r.add_argument("--n", type=int, default=10); r.add_argument("--min-len", type=int, default=3)
    sub.add_parser("stats", parents=[common])
    a = ap.parse_args()

    ix, out = PositionalIndex(a.index), Tee(a.out)
    md, mp = (0, 0) if a.full else (10, 20)
    title = lambda d: f"d{d} = {ix.docs[d][0]}"
    if a.cmd == "lookup":
        for t in a.terms:
            tk = tokenize(t)
            out(fmt_entry(ix, tk[0] if tk else t, md, mp)); out()
    elif a.cmd == "phrase":
        res = ix.phrase(a.query)
        out(f'Phrase "{a.query}" -> {len(res)} document(s)')
        for d, st in res.items(): out(f"  {title(d)}  starts at positions {st}")
    elif a.cmd == "prox":
        x, k, y = a.query.split()
        k, x, y = int(k.lstrip("/")), tokenize(x)[0], tokenize(y)[0]
        res = ix.proximity(x, y, k)
        out(f"'{x}' within {k} words of '{y}' -> {len(res)} document(s)")
        for d, pr in res.items(): out(f"  {title(d)}  (pos_a, pos_b) = {pr}")
    elif a.cmd == "bool":
        res = ix.boolean(a.query)
        out(f"Boolean [{a.query}] -> {len(res)} document(s)")
        for d in res[:50]: out(f"  {title(d)}")
        if len(res) > 50: out(f"  ... (+{len(res) - 50} more)")
    elif a.cmd == "rare":
        for t in ix.rare_terms(a.n, a.min_len):
            out(fmt_entry(ix, t, md, mp)); out()
    else:
        out(stats_text(ix))
    out(f"[postings read from disk: {ix.disk_reads}]")
    out.close()


if __name__ == "__main__":
    main()
