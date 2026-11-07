"""Module 3 - positional index builder (disk based, SPIMI style).

Build phase
  1. Read documents one by one, tokenize, collect  term -> {docID: [positions]}  in memory.
  2. When the in-memory block holds >= --block-size positions, write it to disk as a sorted
     block file and free the memory.  (So collections bigger than RAM can be indexed.)
  3. Merge all sorted blocks (k-way merge) into ONE postings file on disk. While merging,
     compute DF (number of documents) and CF (total occurrences) of every term and record
     where its postings line starts in the file (byte offset + length).

Output files (in the --out directory)
  postings.txt     secondary memory: one line per term  ->  term <TAB> DF <TAB> CF <TAB> d:p,p;d:p ...
  vocabulary.tsv   term <TAB> DF <TAB> CF <TAB> byte_offset <TAB> byte_length   (loaded into RAM by the searcher)
  docs.tsv         docID <TAB> title <TAB> number_of_tokens
"""
import argparse, heapq, os, shutil, sys, time
from collections import defaultdict

from preprocess import tokenize
from loaders import iter_documents


def write_block(mem, path):
    with open(path, "w", encoding="utf-8") as f:
        for term in sorted(mem):
            payload = ";".join(f"{d}:{','.join(map(str, ps))}" for d, ps in mem[term].items())
            f.write(f"{term}\t{payload}\n")


def block_iter(path, idx):
    with open(path, encoding="utf-8") as f:
        for line in f:
            term, payload = line.rstrip("\n").split("\t", 1)
            yield term, idx, payload


def merge_blocks(block_paths, out_dir):
    postings_path = os.path.join(out_dir, "postings.txt")
    vocab_path = os.path.join(out_dir, "vocabulary.tsv")
    merged = heapq.merge(*[block_iter(p, i) for i, p in enumerate(block_paths)])
    n_terms = 0
    with open(postings_path, "wb") as pf, open(vocab_path, "w", encoding="utf-8") as vf:

        def emit(term, parts):
            payload = ";".join(parts)
            df = payload.count(";") + 1              # one "doc:positions" entry per document
            cf = payload.count(",") + df             # total number of positions = occurrences
            line = f"{term}\t{df}\t{cf}\t{payload}\n".encode("utf-8")
            offset = pf.tell()
            pf.write(line)
            vf.write(f"{term}\t{df}\t{cf}\t{offset}\t{len(line)}\n")

        cur, parts = None, []
        for term, _, payload in merged:
            if term != cur:
                if cur is not None:
                    emit(cur, parts)
                    n_terms += 1
                cur, parts = term, []
            parts.append(payload)
        if cur is not None:
            emit(cur, parts)
            n_terms += 1
    return n_terms


def build(input_path, out_dir, block_size=2_000_000, limit=None):
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "_blocks")
    os.makedirs(tmp, exist_ok=True)
    mem, mem_pos, blocks = defaultdict(lambda: defaultdict(list)), 0, []
    n_docs = n_tokens = 0

    def flush():
        nonlocal mem_pos
        path = os.path.join(tmp, f"block_{len(blocks):04d}.txt")
        write_block(mem, path)
        blocks.append(path)
        mem.clear()
        mem_pos = 0

    with open(os.path.join(out_dir, "docs.tsv"), "w", encoding="utf-8") as docs_f:
        for doc_id, (title, text) in enumerate(iter_documents(input_path), start=1):
            if limit and doc_id > limit:
                break
            tokens = tokenize(text)
            for pos, tok in enumerate(tokens, start=1):      # positions start at 1
                mem[tok][doc_id].append(pos)
            mem_pos += len(tokens)
            n_docs, n_tokens = doc_id, n_tokens + len(tokens)
            clean_title = " ".join(str(title).split())
            docs_f.write(f"{doc_id}\t{clean_title}\t{len(tokens)}\n")
            if mem_pos >= block_size:
                flush()
            if doc_id % 1000 == 0:
                print(f"  ... {doc_id} documents processed", flush=True)
        if mem:
            flush()
    if not blocks:
        sys.exit("No documents found - check the --input path.")
    n_terms = merge_blocks(blocks, out_dir)
    shutil.rmtree(tmp)
    size_mb = os.path.getsize(os.path.join(out_dir, "postings.txt")) / 1e6
    print(f"Done in {time.time() - t0:.1f}s")
    print(f"  documents      : {n_docs}")
    print(f"  total tokens   : {n_tokens}")
    print(f"  vocabulary     : {n_terms} terms (kept in main memory when searching)")
    print(f"  temp blocks    : {len(blocks)} merged")
    print(f"  postings file  : {size_mb:.2f} MB on disk  -> {os.path.join(out_dir, 'postings.txt')}")


def main():
    ap = argparse.ArgumentParser(description="Build a disk-based positional index")
    ap.add_argument("--input", required=True, help="folder of .txt files OR Wikipedia XML dump (.xml/.bz2/.gz)")
    ap.add_argument("--out", default="index_out", help="output directory (default: index_out)")
    ap.add_argument("--block-size", type=int, default=2_000_000,
                    help="positions kept in RAM before a block is written to disk (default 2,000,000)")
    ap.add_argument("--limit", type=int, default=None, help="index only the first N documents")
    a = ap.parse_args()
    build(a.input, a.out, a.block_size, a.limit)


if __name__ == "__main__":
    main()
