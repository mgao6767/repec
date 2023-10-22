import sqlite3
import json
import zlib

# Load local packages
from . import settings


def export(handle: str = "", export_bib_file=settings.export_bib):
    """Export bibliorgraphy"""
    assert len(handle) > 0
    conn = sqlite3.connect(settings.database, check_same_thread=False)
    c = conn.cursor()
    c.execute(f'select redif from papers where lower(handle) like "{handle}%"')
    results = c.fetchall()
    c.close()
    if len(results) == 0:
        raise RuntimeWarning("No papers in database matching the handle")

    match handle.lower():
        # Journal of Financial Economics
        case "repec:eee:jfinec":
            if not check_urls_jfe(results):
                raise RuntimeWarning("Some papers' urls are missing")
            with open(export_bib_file, "w", encoding="utf-8") as f:
                for res in results:
                    parse_redif_jfe(res[0], f)


def check_urls_jfe(results: list):
    """Check all records contain file-url"""
    n_has_file_url = 0
    for res in results:
        redif = zlib.decompress(res[0])
        redif = json.loads(redif)
        for rec in redif:
            if rec[0] == "file-url":
                n_has_file_url += 1
                break
    return n_has_file_url == len(results)


def parse_redif_jfe(redif_data: bytes, f):
    redif = zlib.decompress(redif_data)
    redif = json.loads(redif)
    bib = dict()
    authors = []
    for rec in redif:
        match rec[0], "".join(rec[1:]):
            case "template-type", _:
                pass
            case "author-name", author:
                authors.append(author)
            case "file-url", url:
                bib["url"] = url
            case "abstract", abstract:
                bib["abstract"] = abstract
            case "keywords", keywords:
                bib["keywords"] = ", ".join([w.strip() for w in keywords.split("\n")])
            case "year", year:
                bib["year"] = year
            case "title", title:
                bib["title"] = title
            case k, v:
                bib[k] = v
    authors = [name for name in sorted(authors)]
    bib["author"] = " AND ".join(authors)
    # JFE missing journal fiel
    bib["journal"] = "Journal of Financial Economics"

    citekey = authors[0].strip().split(",")[0]
    citekey += year
    citekey += title.split(" ")[0]
    citekey = citekey.lower()

    print(f"@article{{{citekey},", file=f)
    print("\n".join(f"{k} = {{ {v} }}," for k, v in bib.items()), file=f)
    print("}", file=f)
