# Copyright (c) 2019-2020, CPB Netherlands Bureau for Economic Policy Analysis
# Copyright (c) 2019-2020, Andrey Dubovik <andrei@dubovik.eu>

"""A patch to add missing journal names from series names.

This patch is not yet integrated into the main code.
"""

# Load local packages
from . import settings
from .misc import dbconnection, collect
from . import redif
from .repec import ftp_get


@dbconnection(settings.database)
def fetch_handles(conn):
    """Return a set of handle prefixes that miss journal names."""
    sql = "SELECT handle FROM papers" " WHERE template = 'article' AND journal IS NULL"
    handles = conn.execute(sql).fetchall()
    return set(":".join(h[0].split(":")[:3]) for h in handles)


@dbconnection(settings.database)
def fetch_files(conn, handles):
    """Return a set of files containing given handles."""
    sql = "SELECT file FROM series WHERE handle = ?"
    c = conn.cursor()
    files = set()
    for handle in handles:
        for (file,) in c.execute(sql, (handle,)):
            files.add(file)
    return files


def collect_names(files):
    """Download files and collect handle -> name associations."""
    handles = {}
    for i, file in enumerate(files):
        print(f"[{i+1}/{len(files)}] {file}...")
        try:
            rdf = redif.load(redif.decode(ftp_get(settings.repec_ftp + file)))
            for record in rdf:
                record = collect(record)
                if "name" in record:
                    # Account for inconsistent capitalization across records
                    handle = record["handle"][0].lower()
                    newname = record["name"][0]
                    oldname = handles.setdefault(handle, newname)
                    if newname != oldname:
                        print(
                            f'Conflicting names: "{oldname}" vs. "{newname}"'
                            f" in {handle}"
                        )
        except Exception:
            print(f"Skipping {file} due to errors")
    return handles


def merge(handles, names):
    """Intersect handles and names correcting for capitalization."""
    return {h: names[h.lower()] for h in handles if h.lower() in names}


@dbconnection(settings.database)
def ensure_indices(conn):
    """Create necessary indices if missing."""
    sql = """
        CREATE INDEX IF NOT EXISTS papers_tejoha
        ON papers (template, journal, handle);
    """
    conn.execute(sql)


@dbconnection(settings.database)
def update_names(conn, names):
    """Update journal names from series names."""
    sql = """
        UPDATE papers SET journal = ?
        WHERE template = 'article' AND journal IS NULL AND handle GLOB '{}*'
    """
    c = conn.cursor()
    for handle, name in names.items():
        c.execute(sql.format(handle), (name,))


def main():
    """Run the whole update."""
    ensure_indices()
    handles = fetch_handles()
    files = fetch_files(handles=handles)
    names = collect_names(files)
    names = merge(handles, names)
    update_names(names=names)


if __name__ == "__main__":
    main()
