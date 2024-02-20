# ===============================================================================
# Copyright 2020 dgketchum
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ===============================================================================

import os
import sys

parent = os.path.dirname(__file__)
sys.path.append(parent)
from pyqgis_processing import CleanGeometry
from shapefiles import shapefiles

import click

ERROR_LOG = os.path.abspath(os.path.join(parent, 'error_log.txt'))
if not os.path.isfile(ERROR_LOG):
    with open(ERROR_LOG, 'w') as write:
        write.write('ERROR LOG\n')


@click.command()
@click.argument('state')
@click.argument('direct')
@click.argument('overwrite')
def main(state, direct, overwrite=False):

    d = '/home/dgketchum/data/IrrigationGIS'
    if not os.path.isdir(d):
        d = '/media/research/IrrigationGIS'

    if direct not in ['13UBP']:
        return None

    split = os.path.join(d, 'openET/MGRS/split_aea/{}/{}/'.format(state, direct))
    cleaned = os.path.join(d, 'openET/MGRS/split_cleaned_aea/{}/'.format(state, direct))

    f = [os.path.join(split, x) for x in os.listdir(split) if x.endswith('.shp')]
    codes = [x.split('_')[-1].strip('.shp') for x in f]

    # sort the codes by priority
    tup_ = [(f_, c) for f_, c in zip(f, codes)]
    values = [x for x in shapefiles(state)]
    sort = {v: i for i, v in enumerate(values)}
    tup_ = sorted(tup_, key=lambda x: sort[x[1]])
    order_files, order_codes = [x[0] for x in tup_], [x[1] for x in tup_]

    out_shape = os.path.join(cleaned, '{}.shp'.format(direct))
    if not os.path.isdir(cleaned):
        os.mkdir(cleaned)
    if not os.path.exists(out_shape):
        print('writing', out_shape)

        try:
            geos = CleanGeometry(order_files, order_codes, v_clean=False, out_file=out_shape)
            geos.clean_geometries()
        except Exception as e:
            with open(ERROR_LOG, 'a') as write_file:
                write_file.write('{} {} {}, retrying with v_clean\n'.format(state, direct, e))
            print('{} {} {}, retrying with v_clean\n'.format(state, direct, e))
            geos = CleanGeometry(order_files, order_codes, v_clean=True, out_file=out_shape)
            geos.clean_geometries()
    else:
        print('{} exists, skipping'.format(out_shape))


if __name__ == '__main__':
    main()
# ========================= EOF ====================================================================
