# Copyright (c) 2019-2020, CPB Netherlands Bureau for Economic Policy Analysis
# Copyright (c) 2019-2020, Andrey Dubovik <andrei@dubovik.eu>

"""Text and html sanitization routines."""

# Load packages
import re
from lxml.html import tostring, html5parser
import warnings

# Define global settings
BLOCKTAGS = ["div", "p", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"]

EMAIL = re.compile("['a-z0-9._-]+@[a-z0-9._-]+.[a-z]+")


def remove_cc(text):
    r"""Remove control characters (except for \t, \r, \n)."""
    cc = "[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x9f]"
    return re.sub(cc, "", text)


def sanitize_entity(text):
    """Remove whitespace characters from HTML entities."""

    def strip(m):
        return re.sub(r"\s", "", m.group(0))

    return re.sub(r"&#x?[0-9a-f\s]+;", strip, text, flags=re.I)


def ishtml(text):
    """Guess whether text has html in it."""
    text = text.lower()
    for t in BLOCKTAGS:
        if text.find(f"<{t}>") != -1:
            return True
    if text.find("</") != -1 or text.find("/>") != -1:
        return True
    if re.search("&#?x?[0-9a-z]+;", text):
        return True
    return False


def html2text(html):
    """Render html as text, convert line breaks to spaces."""
    if not ishtml(html):
        return re.sub(r"\s+", " ", html.strip())
    parser = html5parser.HTMLParser(namespaceHTMLElements=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        html = html5parser.fromstring(html, parser=parser)
    for b in BLOCKTAGS:
        for e in html.xpath(f"//{b}"):
            e.text = " " + e.text if e.text else ""
            if len(e) > 0:
                lc = e[-1]
                lc.tail = (lc.tail if lc.tail else "") + " "
            else:
                e.text = e.text + " "
    text = tostring(html, method="text", encoding="utf-8")
    return re.sub(r"\s+", " ", text.decode().strip())


def isna(token):
    """Check if it's an N/A token."""
    if re.sub(r"\W", "", token).lower() == "na":
        return True
    else:
        return False


def isvalid(token):
    """Check if token contains alpha characters."""
    if re.match(r"^[\W0-9]*$", token):
        return False
    else:
        return True


def sanitize(text):
    """Remove control characters, drop HTML tags, etc."""
    if type(text) != str:
        return text
    text = remove_cc(text)
    text = sanitize_entity(text)
    text = html2text(text)
    if isna(text) or not isvalid(text):
        return None
    return text


def sanitize_email(email):
    """Get a clean email address."""
    email = sanitize(email)
    if type(email) != str:
        return email
    m = EMAIL.search(email.lower())
    return m.group() if m else None
