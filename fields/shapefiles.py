import os
from pprint import pprint


def shapefiles(state):
    # sort codes in list by priority
    # TODO: list relative paths to source data in this dict
    d = {'AR': ['CLU'],
         'AZ': ['UCRBGS', 'LCRVPD', 'CLU'],
         'CO': ['UCRB', 'CODSS', 'CLU'],
         'CT': ['CLU'],
         'DE': ['CLU'],
         'FL': ['FLSAID'],
         'GA': ['CLU'],
         'IA': ['CLU'],
         'ID': ['IDWRSP', 'IDWRTV', 'BRC', 'CLU'],
         'IL': ['CLU'],
         'IN': ['CLU'],
         'KS': ['CLU'],
         'KY': ['CLU'],
         'LA': ['CLU'],
         'MA': ['CLU'],
         'MD': ['CLU'],
         'ME': ['CLU'],
         'MI': ['CLU'],
         'MN': ['CLU'],
         'MO': ['CLU'],
         'MS': ['CLU'],
         'MT': ['MTDNRC', 'CLU'],
         'NC': ['CLU'],
         'ND': ['CLU'],
         'NE': ['NEDNR', 'CLU'],
         'NH': ['CLU'],
         'NJ': ['CLU'],
         'NY': ['CLU'],
         'OH': ['CLU'],
         'OK': ['CLU'],
         'OR': ['ORWD', 'CLU'],
         'PA': ['CLU'],
         'RI': ['CLU'],
         'SC': ['CLU'],
         'SD': ['CLU'],
         'TN': ['CLU'],
         'TX': ['TWDB', 'CLU'],
         'VA': ['CLU'],
         'VT': ['CLU'],
         'WV': ['CLU'],
         'WI': ['CLU'],
         'WY': ['UCRBGS', 'BRC', 'WYSWP']}

    return d[state]


if __name__ == '__main__':
    pass
# ========================= EOF ====================================================================
