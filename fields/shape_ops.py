import os
import sys
from collections import OrderedDict

import fiona
from rasterstats import zonal_stats

pare = os.path.dirname(__file__)
proj = os.path.dirname(os.path.dirname(pare))
sys.path.append(pare)

MGRS_PATH = os.path.abspath(os.path.join(proj, 'mgrs', 'mgrs_shapefile', 'MGRS_TILE.shp'))

from shapely.geometry import shape

PREREQUISITE_ATTRS = [('SOURCECODE', 'str')]
REQUIRED_ATTRS = [('OPENET_ID', 'str'), ('MGRS_TILE', 'str')]
ALL_ATTRS = PREREQUISITE_ATTRS + REQUIRED_ATTRS

from fields.cdl import cdl_crops

states_attribute = ['WY']


def zonal_cdl(in_shp, in_raster, out_shp=None,
              select_codes=None, write_non_crop=False):
    ct = 1
    geo = []
    bad_geo_ct = 0
    with fiona.open(in_shp) as src:
        meta = src.meta
        for feat in src:
            try:
                _ = feat['geometry']['type']
                geo.append(feat)
            except TypeError:
                bad_geo_ct += 1

    input_feats = len(geo)
    temp_file = out_shp.replace('.shp', '_temp.shp')
    with fiona.open(temp_file, 'w', **meta) as tmp:
        for feat in geo:
            tmp.write(feat)

    meta['schema'] = {'type': 'Feature', 'properties': OrderedDict(
        [('FID', 'int:9'), ('CDL', 'int:9')]), 'geometry': 'Polygon'}

    stats = zonal_stats(temp_file, in_raster, stats=['majority'], nodata=0.0, categorical=False)

    if select_codes:
        include_codes = select_codes
    else:
        include_codes = [k for k in cdl_crops().keys()]

    ct_inval = 0
    with fiona.open(out_shp, mode='w', **meta) as out:
        for attr, g in zip(stats, geo):
            try:
                cdl = int(attr['majority'])
            except TypeError:
                cdl = 0

            if attr['majority'] in include_codes and not write_non_crop:
                feat = {'type': 'Feature',
                        'properties': {'FID': ct,
                                       'CDL': cdl},
                        'geometry': g['geometry']}
                if not feat['geometry']:
                    ct_inval += 1
                elif not shape(feat['geometry']).is_valid:
                    ct_inval += 1
                else:
                    out.write(feat)
                    ct += 1

            elif write_non_crop and cdl not in include_codes:
                feat = {'type': 'Feature',
                        'properties': {'FID': ct,
                                       'CDL': cdl},
                        'geometry': g['geometry']}
                if not feat['geometry']:
                    ct_inval += 1
                elif not shape(feat['geometry']).is_valid:
                    ct_inval += 1
                else:
                    out.write(feat)
                    ct += 1

        print('{} in, {} out, {} invalid, {}'.format(input_feats, ct - 1, ct_inval, out_shp))
        d_name = os.path.dirname(out_shp)
        [os.remove(os.path.join(d_name, x)) for x in os.listdir(d_name) if 'temp' in x]


def fiona_merge_sourcecode(out_shp, file_list):
    meta = fiona.open(file_list[0]).meta
    meta['schema'] = {'type': 'Feature', 'properties': OrderedDict(
        [('OBJECTID', 'str'), ('SOURCECODE', 'str'), ('MGRS_TILE', 'str')]),
                      'geometry': 'Polygon'}

    with fiona.open(out_shp, 'w', **meta) as output:
        ct = 0
        none_geo = 0
        inval_geo = 0
        for s in file_list:
            mgrs = s.split('/')[-1].strip('.shp')
            print(mgrs)
            for feat in fiona.open(s):
                if not feat['geometry']:
                    none_geo += 1
                elif not shape(feat['geometry']).is_valid:
                    inval_geo += 1
                else:
                    area = shape(feat['geometry']).area
                    if area == 0.0:
                        raise AttributeError
                    ct += 1
                    source = feat['properties']['SOURCECODE']
                    feat = {'type': 'Feature', 'properties': OrderedDict(
                        [('OBJECTID', '{}'.format(ct)), ('SOURCECODE', source),
                         ('MGRS_TILE', mgrs)]),
                            'geometry': feat['geometry']}
                    output.write(feat)

    print('wrote {}, {}, {} none, {} invalid'.format(out_shp, ct, none_geo, inval_geo))


def check_geometry_fiona(shapefile):
    ct = 0
    none_geo = 0
    inval_geo = 0
    for feat in fiona.open(shapefile):
        if not feat['geometry']:
            none_geo += 1
        elif not shape(feat['geometry']).is_valid:
            inval_geo += 1
        else:
            area = shape(feat['geometry']).area
            if area == 0.0:
                raise AttributeError
            ct += 1
    tot = ct + none_geo + inval_geo
    print('{} valid {}, {} none, {} invalid, {} total'.format(shapefile, ct, none_geo, inval_geo, tot))


if __name__ == '__main__':
    home = os.path.expanduser('~')
    alt_home = '/media/research'
    if os.path.isdir(alt_home):
        home = alt_home
    else:
        home = os.path.join(home, 'data')

    root = os.path.join(home, 'IrrigationGIS/Montana/statewide_irrigation_dataset/future_work_15FEB2024')

    mgrs = os.path.join(root, 'MGRS')

    cleaned = os.path.join(mgrs, 'split_cleaned')
    out_ = os.path.join(root, 'output', 'potential_fields_MT_20FEB2024.shp')
    split_files = [os.path.join(cleaned, x) for x in os.listdir(cleaned) if x.endswith('.shp')]
    fiona_merge_sourcecode(out_, split_files)
    check_geometry_fiona(out_)


# ========================= EOF ================================================================================
