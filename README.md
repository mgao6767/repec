# RePEc Database Manager

Download, cleanup, and somewhat structure the [RePEc dataset](http://repec.org/) into an SQLite database.

## Quick Start

Install `repec`.

```bash
pip install repec
```

Initialize database `repec.db` and update urls.

```bash
repec init
repec update --repec
```

Update listings of selected journals, e.g. JF, JFE, RFS.

```bash
repec update --listings-of-handle repec:bla:jfinan
repec update --listings-of-handle repec:eee:jfinec
repec update --listings-of-handle repec:oup:rfinst
```

Download papers.

```bash
repec update --papers
```

Export bibliography (for selected journals).

```bash
repec export-bib --handle repec:eee:jfinec
```

## Database

The SQLite database will contain the following tables.

| Table      | Description                                 |
| ---------- | ------------------------------------------- |
| repec      | A list of ReDIF files from RePEc FTP.       |
| series     | Content of ReDIF files from RePEc FTP.      |
| remotes    | A list of URLs that host RePEc data.        |
| listings   | File listings from the sites in `remotes`.  |
| papers     | Titles, abstracts, etc. of economic papers. |
| authors    | Author names.                               |
| jel        | JEL codes.                                  |
| papers_jel | Correspondence between `papers` and `jel`.  |

## Non-standard Dependencies

The scripts use [cld2-cffi](https://github.com/GregBowyer/cld2-cffi) for automatic language detection, and [curl](https://curl.se/) for downloading from FTP sites. `curl` is used instead of `requests`, because `requests` cannot handle some of the FTP sites out there.

## Update Process

```bash
repec update
```

First, the names of all the available ReDIF files are downloaded from the RePEc FTP and saved in table `repec`.

Second, all the files from table `repec` are downloaded from the RePEc FTP and are used to fill in table `series`. Among other data, table `series` will contain URLs where the data on particular series can be found. Unique URLs are then saved in table `remotes`.

Third, all unique URLs will be visited to collect the listings of the final ReDIF documents. These listings are saved in table `listings`.

Fourth, all the files from table `listings` are downloaded, processed, and saved in tables `papers`, `authors`, and `papers_jel`.

If an update is interrupted during the last stage, you can run

```bash
repec update --papers
```

and the update should resume from where it has stopped.

Incremental updates are currently not supported, however it is possible to perform a full update on an existing database. Paper records that are obsolete, i.e. those that can no longer be reached from the initial list of series from the RePEc FTP, are not pruned. This is done on purpose as on some days some participating websites work, and on other days they don't.

Downloaded records are saved as is in `papers.redif` (z-compressed). Additionally, the records are cleaned up and partially destructured into the respective fields. The cleanup steps include, among other:

- stripping html tags;
- language auto-detection (using [cld2-cffi](https://github.com/GregBowyer/cld2-cffi));
- jel codes extraction.