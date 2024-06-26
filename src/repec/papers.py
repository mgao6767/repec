# Copyright (c) 2019-2020, CPB Netherlands Bureau for Economic Policy Analysis
# Copyright (c) 2019-2020, Andrey Dubovik <andrei@dubovik.eu>

"""Routines for downloading and destructuring papers."""

# Load global packages
from urllib.parse import urlparse
import re
import sqlite3
import json
import zlib
import threading
import random
import math
import cld2
from collections import defaultdict

# Load local packages
from . import settings
from . import redif
from .misc import iserror, silent, parallel
from .sanitize import sanitize, sanitize_email
from .network import fetch, fetch_curl


def ttype(record):
    """Get template type."""
    tt = next(v for k, v in record if k == "template-type")
    return re.match(r"redif-(\S*)", tt.lower()).group(1)


@silent
def load(url):
    """Download ReDIF papers."""
    scheme = urlparse(url)[0]
    if scheme == "ftp":
        papers = redif.decode(fetch_curl(url))
    elif scheme in ["http", "https"]:
        content, encoding = fetch(url)
        papers = redif.decode(content, hint=[encoding])
    else:
        raise RuntimeError("Unknown scheme {}".format(scheme))
    papers = redif.load(papers)
    for p in papers:
        fields = set(k for k, v in p)
        for f in ["handle", "template-type"]:
            if f not in fields:
                raise RuntimeError("{} is missing".format(f))
    if len(papers) == 0:
        raise RuntimeError("Empty series")
    return papers


def filterjel(jel, alljel):
    """Verify a JEL code against the official list."""
    if jel in alljel:
        return jel
    elif jel[:2] in alljel:
        return jel[:2]


def parsejel(jel, alljel):
    """Parse JEL using ad-hoc rules."""
    jel = re.sub("([A-Z])[-., ]+([0-9])", r"\1\2", jel)
    jel = re.split("[^A-Z0-9]+", jel.upper())
    jel = [c[:3] for c in jel if re.match("[A-Z][0-9]+$", c)]
    jel = [filterjel(c, alljel) for c in jel]
    jel = sorted(set(c for c in jel if c))
    # Do not include JEL for papers that blindly follow the online example
    if jel == ["R00", "Z0"]:
        return []
    return jel


def parse_template(template):
    """Parse broken template specification."""
    m = re.search("edif-([a-z]+)", template, flags=re.I)
    return m.group(1).lower() if m else None


def parse_year(date):
    """Parse broken date specification."""
    m = re.search("(?<![0-9])[0-9]{4}", date)
    y = m.group(0) if m else None
    return int(y) if y and y != "0000" else None


def get_year(paper):
    """Get most relevant available year."""
    for f in ["year", "creation-date", "revision-date"]:
        years = [parse_year(d) for d in paper.get(f, [])]
        years = [y for y in years if y]
        if years:
            return min(years)
    return None


def detect_language(text):
    """Detect language using CLD2 library."""
    try:  # todo: figure out what's causing an occasional error
        _, _, details = cld2.detect(text)
        lang = details[0].language_code
    except ValueError:
        lang = "un"
    return lang if lang != "un" else None


def lang_and(*text, default=None):
    """Determine common language."""
    lang = set(detect_language(t) for t in text if t)
    if len(lang) == 1:
        lang = lang.pop()
        if lang:
            return lang
    return default


def replace_paper(c, paper, url, alljel):
    """Update a single paper record."""
    blob = json.dumps(paper, ensure_ascii=False).encode(encoding="utf-8")
    paper = redif.collect(paper)
    r = {}
    r["url"] = url
    r["handle"] = paper["handle"][0]
    r["template"] = parse_template(paper["template-type"][0])
    for f in ["title", "abstract", "journal", "volume", "issue", "pages"]:
        r[f] = paper.get(f, [None])[0]
    for f in ["title", "abstract", "journal"]:
        r[f] = sanitize(r[f])
    r["language"] = paper.get("language", ["none"])[0].lower()
    r["language"] = r["language"] if len(r["language"]) == 2 else None
    r["language"] = lang_and(r["title"], r["abstract"], default=r["language"])
    r["year"] = get_year(paper)
    r["redif"] = zlib.compress(blob, level=9)

    sql = "REPLACE INTO papers (" + ", ".join(k for k in r.keys()) + ")"
    sql += " VALUES (" + ", ".join(["?"] * len(r)) + ")"
    c.execute(sql, list(r.values()))
    pid = c.lastrowid

    if "author" in paper:
        authors = [a for a in paper["author"] if type(a) == defaultdict]
        authors = [
            (sanitize(a["name"][0]), sanitize_email(a.get("email", [None])[0]))
            for a in authors
        ]
        authors = [(pid, n, e) for n, e in authors if n]
        sql = "INSERT INTO authors (pid, name, email) VALUES (?, ?, ?)"
        c.executemany(sql, authors)
    if "classification-jel" in paper:
        jel = parsejel(paper["classification-jel"][0], alljel)
        jel = [(pid, c) for c in jel]
        c.executemany("INSERT INTO papers_jel (pid, code) VALUES (?, ?)", jel)


def update_papers_1(conn, lock, url, alljel):
    """Update papers from a single ReDIF document."""
    papers = load(url)
    with lock:
        c = conn.cursor()
        if iserror(papers):
            sql = "UPDATE listings SET status = 2, error = ? WHERE url = ?"
            c.execute(sql, (str(papers), url))
        else:
            sql = "UPDATE listings SET status = 0, error = NULL WHERE url = ?"
            c.execute(sql, (url,))
            for paper in papers:
                replace_paper(c, paper, url, alljel)
        c.close()
    return not iserror(papers)


def update_papers(conn, lock, status=1):
    """Update papers from all ReDIF documents."""
    c = conn.cursor()
    c.execute("SELECT code FROM jel WHERE parent IS NOT NULL")
    alljel = [r[0] for r in c.fetchall()]
    c.execute("SELECT url FROM listings WHERE status = ?", (status,))
    urls = [r[0] for r in c.fetchall()]
    urls = random.sample(urls, k=len(urls))  # to redistribute load
    c.close()

    def worker(u):
        return update_papers_1(conn, lock, u, alljel)

    size = settings.batch_size
    no_batches = math.ceil(len(urls) / size)
    status = 0
    for i in range(no_batches):
        print("Downloading batch {}/{}...".format(i + 1, no_batches))
        batch = urls[i * size : (i + 1) * size]
        bs = sum(parallel(worker, batch, threads=settings.no_threads_www))
        status += bs
        conn.commit()
        print(f"{bs} out of {len(batch)} records updated successfully")

    print(f"All batches: {status} out of {len(urls)} records" " updated successfully")


def update():
    """Update papers from all ReDIF documents (wrapper)."""
    conn = sqlite3.connect(settings.database, check_same_thread=False)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
    c.close()

    lock = threading.Lock()
    try:
        update_papers(conn, lock)
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
    conn.close()
