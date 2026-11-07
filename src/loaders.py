"""Module 2 - document loaders. Each loader yields (title, plain_text) one document at a time,
so the whole collection never has to fit in memory.

Supported inputs
  * a folder of .txt files (one document per file)
  * a Wikipedia XML dump (.xml, .xml.bz2 or .xml.gz) - single file with all articles
"""
import bz2, gzip, os, re
import xml.etree.ElementTree as ET


def iter_txt_folder(folder):
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith(".txt"):
            with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as f:
                yield name, f.read()


def _open_binary(path):
    if path.lower().endswith(".bz2"):
        return bz2.open(path, "rb")
    if path.lower().endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


def clean_wiki(t):
    """Very small MediaWiki-markup cleaner (templates, refs, links, tables, html)."""
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"<ref[^>]*?/>", " ", t)
    t = re.sub(r"<ref[^>]*?>.*?</ref>", " ", t, flags=re.S)
    for _ in range(6):                                   # nested {{templates}}
        t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
    t = re.sub(r"\{\|.*?\|\}", " ", t, flags=re.S)       # tables
    t = re.sub(r"\[\[(?:file|image|category|ಚಿತ್ರ|ವರ್ಗ)[^\]]*\]\]", " ", t, flags=re.I)
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)   # [[a|b]] -> b
    t = re.sub(r"\[https?://[^\s\]]+\s*([^\]]*)\]", r"\1", t)  # external links
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"'{2,}", "", t)
    t = re.sub(r"^=+\s*(.*?)\s*=+\s*$", r"\1", t, flags=re.M)
    return t


def iter_wiki_xml(path):
    """Stream articles (namespace 0, no redirects) out of a Wikipedia dump."""
    title, ns, text, redirect = None, None, "", False
    with _open_binary(path) as f:
        for _, elem in ET.iterparse(f, events=("end",)):
            tag = elem.tag.rsplit("}", 1)[-1]
            if tag == "title":
                title = elem.text or ""
            elif tag == "ns":
                ns = elem.text
            elif tag == "redirect":
                redirect = True
            elif tag == "text":
                text = elem.text or ""
            elif tag == "page":
                if ns == "0" and not redirect and text:
                    yield title, clean_wiki(text)
                title, ns, text, redirect = None, None, "", False
                elem.clear()


def iter_documents(path):
    """Pick the right loader: directory -> txt folder, file -> wiki XML dump."""
    if os.path.isdir(path):
        yield from iter_txt_folder(path)
    else:
        yield from iter_wiki_xml(path)
