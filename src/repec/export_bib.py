import sqlite3
import json
import zlib
import nameparser
from titlecase import titlecase

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
        # Review of Financial Studies
        case "repec:oup:rfinst":
            # if not check_urls_rfs(results):
            #     raise RuntimeWarning("Some papers' urls are missing")
            # Some do not have file-url
            # len(results)=2427, n_has_file_url=2186
            with open(export_bib_file, "w", encoding="utf-8") as f:
                for res in results:
                    parse_redif_rfs(res[0], f)
        # Journal of Finance
        case "repec:bla:jfinan":
            # if not check_urls_jof(results):
            #     raise RuntimeWarning("Some papers' urls are missing")
            # Some do not have file-url
            with open(export_bib_file, "w", encoding="utf-8") as f:
                for res in results:
                    parse_redif_jof(res[0], f)


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


def check_urls_rfs(results: list):
    return check_urls_jfe(results)


def check_urls_jof(results: list):
    return check_urls_jfe(results)


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
                bib["title"] = titlecase(title)
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


def parse_redif_rfs(redif_data: bytes, f):
    redif = zlib.decompress(redif_data)
    redif = json.loads(redif)
    bib = dict()
    authors = []
    for rec in redif:
        match rec[0], "".join(rec[1:]):
            case "template-type", _:
                pass
            # TODO: RFS lists the Editor as an "author"...
            # I have no idea how to clean it.
            case "author-name", author:
                name = nameparser.HumanName(author)
                name = f"{name.last}, {name.first} {name.middle}"
                authors.append(name)
            case "file-url", url:
                if url.startswith("http://www.jstor.org/fcgi-bin"):
                    url = ""
                bib["url"] = url
            case "abstract", abstract:
                # Clean up the abstract of RFS articles
                abstract = "".join(abstract.splitlines())
                if (idx := abstract.rfind("The Author ")) != -1:
                    abstract = abstract[:idx]
                # fmt: off
                for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]:
                    txt = f"Received {month}"
                    if (idx := abstract.find(txt)) != -1:
                        abstract = abstract[:idx]
                    txt = f"Received{month}"
                    if (idx := abstract.find(txt)) != -1:
                        abstract = abstract[:idx]
                # fmt: on
                abstract = abstract.replace(
                    "Article published by Oxford University Press on behalf of the Society for Financial Studies in its journal, The Review of Financial Studies.",
                    "",
                )
                bib["abstract"] = abstract
            case "year", year:
                bib["year"] = year
            case "title", title:
                bib["title"] = titlecase(title)
            case k, v:
                bib[k] = v
    authors = [name for name in sorted(authors)]
    bib["author"] = " AND ".join(authors)
    # JFE missing journal fiel
    bib["journal"] = "Review of Financial Studies"

    citekey = authors[0].strip().split(",")[0]
    citekey += year
    citekey += title.split(" ")[0]
    citekey = citekey.lower()

    print(f"@article{{{citekey},", file=f)
    print("\n".join(f"{k} = {{ {v} }}," for k, v in bib.items()), file=f)
    print("}", file=f)


def parse_redif_jof(redif_data: bytes, f):
    redif = zlib.decompress(redif_data)
    redif = json.loads(redif)
    bib = dict()
    authors = []
    for rec in redif:
        match rec[0], "".join(rec[1:]):
            case "template-type", _:
                pass
            # JoF uses all uppercase for author names
            case "author-name", author:
                name = nameparser.HumanName(author)
                name.first = name.first.title()
                name.middle = name.middle.title()
                name.last = name.last.title()
                name = f"{name.last}, {name.first} {name.middle}"
                authors.append(name)
            case "file-url", url:
                # Not working
                if url.startswith("http://links.jstor.org/sici"):
                    url = ""
                bib["url"] = url
            case "abstract", abstract:
                abstract = "".join(abstract.splitlines())
                # non-breaking space to normal space
                abstract = abstract.replace("\u00A0", " ")
                # "Copyright XXXX by American Finance Association"
                if (idx := abstract.rfind("Copyright ")) != -1 and abstract.find(
                    " by American Finance Association"
                ) != -1:
                    abstract = abstract[:idx]
                bib["abstract"] = abstract
            case "year", year:
                bib["year"] = year
            case "title", title:
                title = titlecase(title.lower())
                title = title.replace("Nyse", "NYSE")
                title = title.replace("Otc", "OTC")
                title = title.replace("Capm", "CAPM")
                title = title.replace("Ipo", "IPO")
                title = title.replace("Seo", "SEO")
                bib["title"] = title
            # Drop the unnecessary
            case "x-bibl", _:
                pass
            case k, v:
                bib[k] = v
    authors = [name for name in sorted(authors)]
    bib["author"] = " AND ".join(authors)
    # JFE missing journal fiel
    bib["journal"] = "The Journal of Finance"

    citekey = authors[0].strip().split(",")[0]
    citekey += year
    citekey += title.split(" ")[0]
    citekey = citekey.lower()

    print(f"@article{{{citekey},", file=f)
    print("\n".join(f"{k} = {{ {v} }}," for k, v in bib.items()), file=f)
    print("}", file=f)


def format_last_name(name: str) -> str:
    for pre in [
        "de ",
        "von ",
        "van ",
        "van der ",
        "de la ",
        "de los ",
        "da ",
        "dos ",
    ]:
        if name.last.lower().startswith(pre):
            name.last = pre + name.last[len(pre) :]
    if name.last.lower() == "deyoung":
        name.last = "DeYoung"
    if name.last.lower() == "mcdonald":
        name.last = "McDonald"
