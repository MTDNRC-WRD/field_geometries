import os
import sys
import numpy as np
import random
from collections import OrderedDict

import fiona
from rtree import index
from rasterstats import zonal_stats

pare = os.path.dirname(__file__)
proj = os.path.dirname(os.path.dirname(pare))
sys.path.append(pare)

MGRS_PATH = os.path.abspath(os.path.join(proj, 'mgrs', 'mgrs_shapefile', 'MGRS_TILE.shp'))

from shapely.geometry import shape, Polygon

PREREQUISITE_ATTRS = [('SOURCECODE', 'str')]
REQUIRED_ATTRS = [('OPENET_ID', 'str'), ('MGRS_TILE', 'str')]
ALL_ATTRS = PREREQUISITE_ATTRS + REQUIRED_ATTRS

from fields.vector.cdl import cdl_crops

states_attribute = ['WY']

EXCLUDE_LOG = os.path.join(os.getcwd(), 'excluded_fields.txt')
if not os.path.isfile(EXCLUDE_LOG):
    with open(EXCLUDE_LOG, 'w') as write:
        write.write('EXLUDED FIELDS LOG\n')


class BadAttributionException(Exception):
    pass


irrmapper_states = ['AZ', 'CA', 'CO', 'ID', 'MT', 'NM', 'NV', 'OR', 'UT', 'WA', 'WY']

east_states = ['ND', 'SD', 'NE', 'KS', 'OK', 'TX']

far_east = ['AR', 'CT', 'DE', 'FL', 'IL', 'GA', 'IN', 'KY', 'LA', 'MA', 'MD',
            'ME', 'MI', 'MN', 'MS', 'NC', 'NH', 'NJ', 'NY', 'OH', 'PA', 'RI', 'SC',
            'TN', 'VA', 'VT', 'WI', 'WV']

# l = [('gs://openet_geodatabase/field_boundaries_shapefiles_staged/{}.zip'.format(x.lower())) for x in far_east]
# print(' '.join(map(str, l)))

missing = ['AL']


def get_list(_dir):
    l = []
    for path, subdirs, files in os.walk(_dir):
        for name in files:
            p = os.path.join(path, name)
            if p not in l and p.endswith('.shp'):
                l.append(p)
    return l


def compile_shapes(out_shape, shapes):
    out_features = []
    out_geometries = []
    err = False
    first = True
    err_count = 0
    for _file, code in shapes:
        if first:
            with fiona.open(_file) as src:
                print(_file, src.crs)
                meta = src.meta
                meta['schema'] = {'type': 'Feature', 'properties': OrderedDict(
                    [('OBJECTID', 'int:9'), ('SOURCECODE', 'str')]), 'geometry': 'Polygon'}
                raw_features = [x for x in src]
            for f in raw_features:
                f['properties']['SOURCECODE'] = code
                try:
                    base_geo = Polygon(f['geometry']['coordinates'][0])
                    out_geometries.append(base_geo)
                    out_features.append(f)
                except Exception as e:
                    try:
                        base_geo = Polygon(f['geometry']['coordinates'][0])
                        out_geometries.append(base_geo)
                        out_features.append(f)
                    except Exception as e:
                        err_count += 1
            print('base geometry errors: {}'.format(err_count))
            first = False
        else:
            f_count = 0
            add_err_count = 0
            with fiona.open(_file) as src:
                print(_file, src.crs)
                for feat in src:
                    inter = False
                    f_count += 1
                    feat['properties']['SOURCECODE'] = code

                    try:
                        poly = Polygon(feat['geometry']['coordinates'][0])
                    except Exception as e:
                        try:
                            poly = Polygon(feat['geometry']['coordinates'][0][0])
                        except Exception as e:
                            add_err_count += 1
                            err = True
                            break
                    for _, out_geo in enumerate(out_geometries):
                        if poly.centroid.intersects(out_geo):
                            inter = True
                            break
                    if not inter and not err:
                        out_features.append(feat)
                        out_geometries.append(poly)

                    if f_count % 1000 == 0:
                        if f_count == 0:
                            pass
                        else:
                            print(f_count, '{} base features'.format(len(out_features)))
                print('added geometry errors: {}'.format(add_err_count))

    with fiona.open(out_shape, 'w', **meta) as output:
        ct = 0
        for feat in out_features:
            feat = {'type': 'Feature', 'properties': OrderedDict(
                [('OBJECTID', ct), ('SOURCECODE', feat['properties']['SOURCECODE'])]),
                    'geometry': feat['geometry']}
            if not feat['geometry']:
                print('None Geo, skipping')
            elif not shape(feat['geometry']).is_valid:
                print('Invalid Geo, skipping')
            else:
                output.write(feat)
                ct += 1
        print('wrote {}'.format(out_shape))


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


def split_by_mgrs(shapes, out_dir):
    """attribute source code, split into MGRS tiles"""
    out_features = []
    tiles = []
    idx = index.Index()
    in_features = []
    for _file, code in shapes:
        with fiona.open(_file) as src:
            print(_file, src.crs)
            meta = src.meta
            meta['schema'] = {'type': 'Feature', 'properties': OrderedDict(
                [('OBJECTID', 'int:9'), ('SOURCECODE', 'str')]), 'geometry': 'Polygon'}
            [in_features.append((code, f)) for f in src]

    with fiona.open(MGRS_PATH, 'r') as mgrs:
        [idx.insert(i, shape(tile['geometry']).bounds) for i, tile in enumerate(mgrs)]
        for code, f in in_features:
            try:
                point = shape(f['geometry']).centroid
                for j in idx.intersection(point.coords[0]):
                    if point.within(shape(mgrs[j]['geometry'])):
                        tile = mgrs[j]['properties']['MGRS_TILE']
                        if tile not in tiles:
                            tiles.append(tile)
                        break
                f['properties'] = OrderedDict([('SOURCECODE', code),
                                               ('MGRS_TILE', tile)])
                out_features.append(f)
            except AttributeError as e:
                print(e)

    codes = [x[1] for x in shapes]
    for code in codes:
        for tile in tiles:
            dir_ = os.path.join(out_dir, tile)
            if not os.path.isdir(out_dir):
                os.mkdir(out_dir)
            if not os.path.isdir(dir_):
                os.mkdir(dir_)
            file_name = '{}_{}'.format(tile, code)
            print(dir_, file_name)
            out_shape = os.path.join(dir_, '{}.shp'.format(file_name))
            with fiona.open(out_shape, 'w', **meta) as output:
                ct = 0
                for feat in out_features:
                    if feat['properties']['MGRS_TILE'] == tile and feat['properties']['SOURCECODE'] == code:
                        feat = {'type': 'Feature', 'properties': OrderedDict(
                            [('OBJECTID', ct), ('SOURCECODE', feat['properties']['SOURCECODE'])]),
                                'geometry': feat['geometry']}
                        if not feat['geometry']:
                            print('None Geo, skipping')
                        elif not shape(feat['geometry']).is_valid:
                            print('Invalid Geo, skipping')
                        else:
                            output.write(feat)
                            ct += 1
            if ct == 0:
                [os.remove(os.path.join(dir_, x)) for x in os.listdir(dir_) if file_name in x]
                print('Not writing {}'.format(file_name))
            else:
                print('wrote {}, {} features'.format(out_shape, ct))


def attribute_mgrs(in_shp, out_shape):
    id_ct = 0
    state = os.path.basename(in_shp).split('.')[0][:2]
    with fiona.open(in_shp, 'r') as src:
        print(in_shp)
        meta = src.meta
        schema = src.schema
        schema['properties'] = OrderedDict([x for x in REQUIRED_ATTRS])
        meta['schema'] = schema
        new_features = []
        idx = index.Index()

        with fiona.open(MGRS_PATH, 'r') as mgrs:
            [idx.insert(i, shape(tile['geometry']).bounds) for i, tile in enumerate(mgrs)]

            for i, f in enumerate(src):
                id_ct += 1
                _id = '{}_{}'.format(state, id_ct)
                try:
                    point = shape(f['geometry']).centroid
                    for j in idx.intersection(point.coords[0]):
                        if point.within(shape(mgrs[j]['geometry'])):
                            tile = mgrs[j]['properties']['MGRS_TILE']
                            break

                    f['properties'] = OrderedDict([('OPENET_ID', _id), ('MGRS_TILE', tile)])
                    new_features.append(f)
                except AttributeError:
                    pass

    null_mgrs = len([x for x in new_features if not x['properties']['MGRS_TILE']])
    null_openet_id = len([x for x in new_features if not x['properties']['OPENET_ID']])
    print('{} null in {},\n {} null in {} of {} features'.format(null_openet_id, 'OPENET_ID',
                                                                 null_mgrs, 'MGRS_TILE',
                                                                 len(new_features)))

    print('writing {}'.format(out_shape))
    with fiona.open(out_shape, 'w', **meta) as dst:
        for f in new_features:
            if not f['geometry']:
                print(f['id'], ' None Geo, skipping')
            elif not shape(f['geometry']).is_valid:
                print(f['id'], ' invalid, skipping')
            else:
                dst.write(f)


def attribute_working(in_dir, out_dir):
    files_ = [os.path.join(in_dir, '{}.shp'.format(x)) for x in states_attribute]
    # files_ = [os.path.join(in_dir, x) for x in os.listdir(in_dir) if x.endswith('.shp')]
    for _file in files_:
        id_ct = 0
        state = os.path.basename(_file).split('.')[0][:2]
        with fiona.open(_file, 'r') as src:
            print(_file)
            meta = src.meta
            schema = src.schema
            schema['properties'] = OrderedDict([x for x in ALL_ATTRS])
            meta['schema'] = schema

            props = src.meta['schema']['properties']
            check = [x[0] for x in PREREQUISITE_ATTRS if x[0] not in list(props.keys())]
            if check:
                raise BadAttributionException('{} does not have all attributes {}\n'
                                              'Edit the file and run again'.format(_file, PREREQUISITE_ATTRS))

            for attr in PREREQUISITE_ATTRS:
                count_null = len([f for f in src if not f['properties'][attr[0]]])
                print('{} null {} in {}'.format(count_null, attr[0], _file))

            new_features = []
            idx = index.Index()

            with fiona.open(MGRS_PATH, 'r') as mgrs:
                [idx.insert(i, shape(tile['geometry']).bounds) for i, tile in enumerate(mgrs)]

                for i, f in enumerate(src):
                    id_ct += 1
                    _id = '{}_{}'.format(state, id_ct)
                    source_code = f['properties']['SOURCECODE']
                    try:
                        point = shape(f['geometry']).centroid
                        for j in idx.intersection(point.coords[0]):
                            if point.within(shape(mgrs[j]['geometry'])):
                                tile = mgrs[j]['properties']['MGRS_TILE']
                                break

                        f['properties'] = OrderedDict([('OPENET_ID', _id), ('MGRS_TILE', tile),
                                                       ('SOURCECODE', source_code)])
                        new_features.append(f)
                    except AttributeError:
                        pass

        null_mgrs = len([x for x in new_features if not x['properties']['MGRS_TILE']])
        null_openet_id = len([x for x in new_features if not x['properties']['OPENET_ID']])
        out_file = os.path.join(out_dir, '{}.shp'.format(state))
        print('{} null in {},\n {} null in {} of {} features'.format(null_openet_id, 'OPENET_ID',
                                                                     null_mgrs, 'MGRS_TILE',
                                                                     len(new_features)))
        print('writing {}'.format(out_file))
        with fiona.open(out_file, 'w', **meta) as dst:
            if not f['geometry']:
                print(f['id'])
            for f in new_features:
                dst.write(f)


def fiona_merge_sourcecode(out_shp, file_list, state):
    meta = fiona.open(file_list[0]).meta
    meta['schema'] = {'type': 'Feature', 'properties': OrderedDict(
        [('OPENET_ID', 'str'), ('SOURCECODE', 'str'), ('MGRS_TILE', 'str')]),
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
                        [('OPENET_ID', '{}_{}'.format(state, ct)), ('SOURCECODE', source),
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


def clean_geometry_fiona(shapefile, out_):
    ct = 0
    none_geo = 0
    inval_geo = 0
    meta = fiona.open(shapefile).meta
    meta['schema'] = {'type': 'Feature', 'properties': OrderedDict(
        [('OPENET_ID', 'str'), ('SOURCECODE', 'str'), ('MGRS_TILE', 'str')]),
                      'geometry': 'Polygon'}

    with fiona.open(out_, 'w', **meta) as output:
        for feat in fiona.open(shapefile):
            if not feat['geometry']:
                none_geo += 1
            elif not shape(feat['geometry']).is_valid:
                inval_geo += 1
            else:
                area = shape(feat['geometry']).area
                if area == 0.0:
                    raise AttributeError
                output.write(feat)
                ct += 1
    tot = ct + none_geo + inval_geo
    print('{} valid {}, {} none, {} invalid, {} total'.format(shapefile, ct, none_geo, inval_geo, tot))


def popper_test(shp, out_shp, threshold=0.79, mgrs_limit=100,
                min_area=325000., min_thresh=0.78):
    meta = fiona.open(shp).meta
    meta['schema'] = {'type': 'Feature', 'properties': OrderedDict(
        [('MGRS_TILE', 'str'), ('popper', 'float')]),
                      'geometry': 'Polygon'}

    def popper(geometry):
        p = (4 * np.pi * geometry.area) / (geometry.boundary.length ** 2.)
        return p

    dct = {}
    ct = 0
    non_polygon = 0
    popper_ct = 0
    with fiona.open(shp, 'r') as src:
        for feat in src:
            ct += 1
            mgrs = feat['properties']['MGRS_TILE']
            geo = shape(feat['geometry'])
            if not isinstance(geo, Polygon):
                print(type(geo))
                non_polygon += 1
                continue
            popper_ = float(popper(geo))
            if threshold > popper_ > min_thresh and geo.area > min_area:
                feat['properties']['popper'] = popper_
                if mgrs not in dct.keys():
                    dct[mgrs] = [feat]
                else:
                    dct[mgrs].append(feat)
                popper_ct += 1
                if popper_ct % 1000 == 0:
                    print('{} potential polygons of {}, {} non-polygon geometries'.format(popper_ct, ct, non_polygon))
    with fiona.open(out_shp, 'w', **meta) as dst:
        write_ct = 0
        for mgrs in dct.keys():
            print(mgrs, len(dct[mgrs]))
            random.shuffle(dct[mgrs])
            for i, feat in enumerate(dct[mgrs]):
                if i < mgrs_limit:
                    try:
                        feat = {'type': 'Feature', 'properties': OrderedDict(
                            [('MGRS_TILE', mgrs), ('popper', feat['properties']['popper'])]),
                                'geometry': feat['geometry']}
                        dst.write(feat)
                        write_ct += 1
                    except:
                        pass
    print('{} passing objects, {} written, {}'.format(popper_ct, write_ct, out_shp))


if __name__ == '__main__':
    home = os.path.expanduser('~')
    alt_home = '/media/research'
    if os.path.isdir(alt_home):
        home = alt_home
    else:
        home = os.path.join(home, 'data')

    mgrs = os.path.join(home, 'IrrigationGIS', 'openET', 'MGRS')

    for s in ['FL']:
        no_exists = []
        try:
            data = os.path.join(home, 'IrrigationGIS/openET/FL/fl_said_crop_noPasture.shp')
            l = [(data, 'FLSAID')]
            split = os.path.join(mgrs, 'split', s)
            split_by_mgrs(l, split)
            tiles = [os.path.join(split, x) for x in os.listdir(split)]

            for tile in tiles:
                raster = os.path.join(home, 'IrrigationGIS', 'cdl', 'wgs', 'CDL_2017_{}.tif'.format(s))
                in_tile = os.path.join(tile, '{}_FLSAID.shp'.format(os.path.basename(tile)))
                target_d = os.path.join(mgrs, 'split_cropped', s)
                if not os.path.isdir(target_d):
                    os.mkdir(target_d)
                target_d = os.path.join(mgrs, 'split_cropped', s, os.path.basename(tile))
                if not os.path.isdir(target_d):
                    os.mkdir(target_d)
                out_tile = os.path.join(target_d, '{}_FLSAID.shp'.format(os.path.basename(tile)))
                print('cdl process on {}'.format(out_tile))
                no_exists.append(out_tile)
                zonal_cdl(in_tile, raster, out_tile, write_non_crop=False)

            cleaned = os.path.join(mgrs, 'split_cleaned', s)
            out_ = os.path.join(home, 'IrrigationGIS', 'openET', 'OpenET_GeoDatabase', '{}.shp'.format(s.upper()))
            split_files = [os.path.join(cleaned, x) for x in os.listdir(cleaned) if x.endswith('.shp')]
            fiona_merge_sourcecode(out_, split_files, s)
            check_geometry_fiona(out_)

        except Exception as e:
            print(s, e)

# ========================= EOF ================================================================================
