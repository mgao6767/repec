# Load global packages
import re

def decode(rdf):
    '''Decode ReDIF document'''
    def decode(encoding):
        rslt = rdf.decode(encoding)
        if rslt.lower().find('template-type') == -1:
            raise RuntimeError('Decoding Error')
        return rslt

    encodings = ['windows-1252', 'utf-8', 'utf-16', 'latin-1']
    if rdf[:3] == b'\xef\xbb\xbf':
        encodings = ['utf-8-sig'] + encodings
    for enc in encodings:
        try:
            return decode(enc)
        except:
            continue
    raise RuntimeError('Decoding Error')

def split(lst, sel):
    '''Split a list using a selector function'''
    group = []
    groups = [group]
    for el in lst:
        if sel(el):
            group = []
            groups.append(group)
        group.append(el)
    return groups

def load(rdf):
    '''Load ReDIF document'''
    # Repair line endings
    rdf = re.sub('\r(?!\n)', '\r\n', rdf, flags = re.M)

    # Drop comments
    rdf = re.sub('^#.*\n?', '', rdf, flags = re.M)

    # Split fields
    rdf = re.split('(^[a-zA-Z0-9\-#]+:\s*)', rdf, flags = re.M)[1:]
    rdf = [l.strip() for l in rdf]
    rdf = [(rdf[i].rstrip(':').lower(), rdf[i+1]) for i in range(0, len(rdf), 2)]

    # Split templates
    rdf = split(rdf, lambda x: x[0] == 'template-type')[1:]
    return rdf
