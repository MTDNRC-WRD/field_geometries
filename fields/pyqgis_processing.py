# ===============================================================================
# Copyright 2019 dgketchum
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


"""
Clean vector geometries according to data source priority, return single shapefile with SOURCECODE attribution:

    # Requirements:
    
    - project layer to EPSG 102008, NA Albers Equal Area Conic:
        +proj=aea +lat_1=20 +lat_2=60 +lat_0=40 +lon_0=-96 +x_0=0 +y_0=0 +ellps=GRS80 +datum=NAD83 +units=m +no_defs 
        
    - remove duplicate geometries from priority layers
    - remove self-overlaps from priority layers
    - remove slivers from self-overlap elimination
    - remove duplicate geometries from added layers
    - remove self-overlaps from added layers
    - clip away existing geometries from added layer, DIFFERENCE
    - identify slivers where $area/($perimeter^2) < 0.01
    - eliminate sliver geometries, merging with greatest shared perimeter, maintain original SOURCECODE
    - add non-intersecting geometries where $area > 2023.5 sq m (0.5 acres)
    
The environment requires access to the conda install of QGIS 3:
    
    'conda create -n qs python=3.7'
    'conda install -c conda-forge qgis'
   
"""

import sys
import os

PATHS = [
    '/home/dgketchum/miniconda3/envs/qs/share/qgis/python',
    '/home/dgketchum/miniconda3/envs/qs/share/qgis/python/plugins', ]

[sys.path.insert(0, x) for x in PATHS]

from qgis.core import *
from qgis.PyQt.QtCore import QVariant
from qgis.analysis import QgsNativeAlgorithms
from qgis.core import (QgsVectorLayer,
                       QgsApplication,
                       QgsField,
                       QgsProject,
                       QgsExpression,
                       QgsExpressionContext,
                       QgsExpressionContextUtils,
                       QgsFeatureRequest,
                       QgsProcessingFeedback,
                       QgsVectorLayer,
                       QgsProcessingException,
                       edit)

import processing
from processing.core import *
from processing.core.Processing import Processing
from processing.tools import dataobjects


class CleanGeometry:

    def __init__(self, files, codes, popper_ratio_min=0.05, min_area=2025., v_clean=False, out_file=None):
        super(CleanGeometry, self).__init__()
        self.ratio = popper_ratio_min
        self.area = min_area
        self.out = out_file
        self.files = files
        self.codes = codes
        self.v_clean = v_clean

        self.base = None
        self.working = None
        self.code = None

        self.tmp_valid = os.path.join(os.path.dirname(__file__), 'temp_valid.shp')
        self.tmp_error = os.path.join(os.path.dirname(__file__), 'temp_error.shp')

        self.processing_id = 1
        self.ingest_id = 1
        self.to_eliminate = []

        QgsApplication.setPrefixPath('/usr', True)
        self.app = QgsApplication([], True)
        self.app.initQgis()
        self.app.processingRegistry().addProvider(QgsNativeAlgorithms())

        Processing.initialize()

        self.project = QgsProject.instance()
        self.project.setCrs(QgsCoordinateReferenceSystem.fromEpsgId(102008))

    def clean_geometries(self):
        first = True
        for f, c in zip(self.files, self.codes):
            print('processing {}'.format(f))
            self.code = c
            if not os.path.exists(f):
                raise FileNotFoundError('{} not found'.format(f))
            self._load_layer(f)
            self._remove_overlaps()
            self._apply_unique_id()
            self._to_singlepart()

            if first:
                self._apply_source_code()
                self.base = self._get_working()
                first = False
            else:
                self._apply_source_code()
                self._difference()
                self._to_singlepart()
                self._apply_unique_id()
                self._identify_eliminate()
                self._eliminate()
                self._to_singlepart()
                self._apply_unique_id()
                self._merge_working_and_layer()

        self._identify_eliminate()
        self._remove()
        self.processing_id = 1
        self._apply_unique_id()
        self._write_shapefile()
        print('wrote {}\n'.format(self.out))
        self.close()

    def _remove(self):
        ct = 0
        before = self.working.featureCount()
        rm_attr = 5 if self.v_clean else 4

        with edit(self.working):
            for feature in self.working.getFeatures():
                attrs = feature.attributes()
                if attrs[rm_attr]:
                    ct += 1
                    self.working.deleteFeature(feature.id())
        after = self.working.featureCount()
        print(before, 'before', ct, ' deleted', after, 'after')

    def _eliminate(self):

        select = []
        elim_attr = 5 if self.v_clean else 4
        for feature in self.working.getFeatures():
            attrs = feature.attributes()
            if attrs[elim_attr]:
                select.append(attrs[0])

        self.working.selectByIds(select, QgsVectorLayer.AddToSelection)
        params = {'INPUT': self.working,
                  'MODE': 2,
                  'OUTPUT': "memory:eliminated"}
        result = processing.run('qgis:eliminateselectedpolygons', params)

        params = {'LAYERS': result['OUTPUT'],
                  'CRS': 'EPSG:102008',
                  'OUTPUT': "memory:merged"}
        result = processing.run("qgis:mergevectorlayers", params)
        self.working = result['OUTPUT']
        self.working.removeSelection()

    def _identify_eliminate(self):
        pr = self.working.dataProvider()
        pr.addAttributes([QgsField("sliver", QVariant.Double), QgsField("area", QVariant.Double),
                          QgsField("eliminate", QVariant.Bool)])

        self.working.updateFields()
        expression_1 = QgsExpression('(4 * pi() * area($geometry))/(perimeter($geometry) ^ 2)')

        expression_2 = QgsExpression('$area')

        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.working))

        slivers = 0
        low_area = 0
        with edit(self.working):
            ct = 0
            keep = 0
            for i, f in enumerate(self.working.getFeatures(), start=self.processing_id):
                context.setFeature(f)
                f['sliver'] = expression_1.evaluate(context)
                f['area'] = expression_2.evaluate(context)

                if f['sliver'] < self.ratio:
                    f['eliminate'] = True
                    ct += 1
                    slivers += 1
                elif f['area'] < self.area:
                    f['eliminate'] = True
                    ct += 1
                    low_area += 1
                else:
                    f['eliminate'] = False
                    keep += 1
                self.working.updateFeature(f)
            try:
                self.processing_id = i
            except UnboundLocalError:
                pass

            print('{} slivers, {} low area'.format(slivers, low_area))
            print('{} to remove, {} to keep'.format(ct, keep))

    def _to_singlepart(self):
        params = {'INPUT': self.working,
                  'OUTPUT': 'memory:Single'}
        result = processing.run('native:multiparttosingleparts', params)
        self.working = result['OUTPUT']

    def _difference(self):
        """ the most problematic method, change buffer distance to adjust """

        params = {'INPUT': self.working,
                  'OVERLAY': self.base,
                  'OUTPUT': 'memory:Diff'}
        try:
            result = processing.run('qgis:difference', params)
            self.working = result['OUTPUT']

        except QgsProcessingException:
            print('check validity on base {}'.format(self.code))
            self.base = self._check_validity(self.base)
            params = {'input': self.base,
                      'type': 4,
                      'distance': -0.1,
                      'layer': -1,
                      'tolerance': 1.0,
                      'output': self.tmp_valid}
            processing.run('grass7:v.buffer', params)
            self.base = QgsVectorLayer(self.tmp_valid, 'in', 'ogr')

        params = {'INPUT': self.working,
                  'OVERLAY': self.base,
                  'OUTPUT': 'memory:Diff'}
        result = processing.run('qgis:difference', params)
        self.working = result['OUTPUT']

    def _write_shapefile(self):
        self.layer = self._get_working()
        crs = self.layer.crs()
        crs.createFromId(102008)
        self.layer.setCrs(crs)
        self.layer.selectAll()
        params = {'INPUT': self.working, 'OUTPUT': self.out}
        processing.run("qgis:saveselectedfeatures", params)
        return None

    def _merge_working_and_layer(self):
        layers = [self.base, self.working]
        params = {'LAYERS': layers,
                  'CRS': 'EPSG:102008',
                  'OUTPUT': "memory:merged"}
        result = processing.run("qgis:mergevectorlayers", params)
        self.base = result['OUTPUT']
        self.working = result['OUTPUT']

    def _get_working(self):
        self.working.selectAll()
        params = {'INPUT': self.working, 'OUTPUT': 'memory:None'}
        return processing.run("qgis:saveselectedfeatures", params)['OUTPUT']

    def _remove_overlaps(self):

        params = {'INPUT': self.working,
                  'OUTPUT': 'memory:Union'}
        context = dataobjects.createContext()
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometrySkipInvalid)
        feedback = QgsProcessingFeedback()
        result = processing.run('qgis:union', params, context=context, feedback=feedback)

        params = {'INPUT': result['OUTPUT'],
                  'OUTPUT': 'memory:DeleteDupes'}
        result = processing.run('qgis:deleteduplicategeometries', params)

        self.working = result['OUTPUT']
        print(self.working.featureCount(), ' features')

    def _apply_unique_id(self):
        pr = self.working.dataProvider()
        pr.addAttributes([QgsField("id", QVariant.Int)])

        self.working.updateFields()

        context = QgsExpressionContext()
        context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(self.working))

        with edit(self.working):
            ct = 0
            for i, f in enumerate(self.working.getFeatures(), start=self.processing_id):
                f['id'] = i
                self.working.updateFeature(f)
            try:
                self.processing_id = i
            except UnboundLocalError:
                pass

    def _apply_source_code(self):
        formula = "'{}'".format(self.code)
        params = {'INPUT': self.working,
                  'FIELD_NAME': 'SOURCECODE',
                  'FIELD_TYPE': 2,
                  'FIELD_LENGTH': 10,
                  'FIELD_PRECISION': 0,
                  'NEW_FIELD': True,
                  'OUTPUT': 'memory:Sourcecode',
                  'FORMULA': formula}
        result = processing.run('qgis:fieldcalculator', params)
        self.working = result['OUTPUT']

    def _strip_fields(self):
        fields = [i for i, x in enumerate(self.working.dataProvider().fields())]
        self.working.dataProvider().deleteAttributes(fields)
        self.working.updateFields()

    def _load_layer(self, file_):
        layer = QgsVectorLayer(file_, 'in', 'ogr')

        self.project.addMapLayer(layer)
        fields = [i for i, x in enumerate(layer.dataProvider().fields())]
        layer.dataProvider().deleteAttributes(fields)
        layer.updateFields()

        if self.v_clean:
            self.working = self._v_clean(layer, )
        else:
            self.working = layer

    def _v_clean(self, layer, min_area=2023.0):
        """
        0 break: break lines at each intersection
        1 snap: snap lines to vertex in threshold
        2 rmdangle: remove dangles, threshold ignored if < 0
        3 chdangle: change the type of boundary dangle to line, threshold ignored if < 0, input line type is ignored
        4 rmbridge: remove bridges connecting area and island or 2 islands
        5 chbridge: change the type of bridges connecting area and island or 2 islands from boundary to line
        6 rmdupl: remove duplicate lines (pay attention to categories!)
        7 rmdac: remove duplicate area centroids ('type' option ignored)
        8 bpol: break (topologically clean) polygons (imported from non topological format, like ShapeFile). Boundaries are broken on each point shared between 2 and more polygons where angles of segments are different
        9 prune: remove vertices in threshold from lines and boundaries, boundary is pruned only if topology is not damaged (new intersection, changed attachement of centroid), first and last segment of the boundary is never changed
        10 rmarea: remove small areas, the longest boundary with adjacent area is removed
        11 rmline: remove all lines or boundaries of zero length, threshold is ignored
        12 rmsa: remove small angles between lines at nodes

        Parameters
        ----------
        layer
        min_area

        Returns
        -------

        """
        params = {'-b': False,
                  # '-c': True,
                  'GRASS_MIN_AREA_PARAMETER': min_area,
                  'GRASS_OUTPUT_TYPE_PARAMETER': 0,
                  'GRASS_REGION_PARAMETER': None,
                  'GRASS_VECTOR_DSCO': '',
                  'GRASS_VECTOR_EXPORT_NOCAT': False,
                  'GRASS_VECTOR_LCO': '',
                  'error': self.tmp_error,
                  'input': layer,
                  'output': self.tmp_valid,
                  'threshold': [1],
                  'tool': [0],
                  'type': [4]}
        processing.run('grass7:v.clean', params)
        layer = QgsVectorLayer(self.tmp_valid, 'in', 'ogr')
        return layer

    def _check_validity(self, layer):

        def check_alg(layer):
            params = {'ERROR_OUTPUT': 'memory:Temp',
                      'IGNORE_RING_SELF_INTERSECTION': False,
                      'INPUT_LAYER': layer,
                      'INVALID_OUTPUT': 'memory:Temp2',
                      'METHOD': 1,
                      'VALID_OUTPUT': 'memory:Valid'}
            result = processing.run('qgis:checkvalidity', params)
            inval_qgis_ = result['INVALID_COUNT']

            params = {'ERROR_OUTPUT': 'memory:Temp',
                      'IGNORE_RING_SELF_INTERSECTION': False,
                      'INPUT_LAYER': result['VALID_OUTPUT'],
                      'INVALID_OUTPUT': 'memory:Temp2',
                      'METHOD': 2,
                      'VALID_OUTPUT': 'memory:Valid'}
            result = processing.run('qgis:checkvalidity', params)
            inval_geos_ = result['INVALID_COUNT']
            total_errors = inval_qgis_ + inval_geos_
            return result, total_errors

        result, errors = check_alg(layer)
        if errors > 0:
            print('{} errors'.format(errors))
            layer = self._v_clean(result['VALID_OUTPUT'], 2000.0)
            result, errors = check_alg(layer)
        return result['VALID_OUTPUT']

    def list_algorithms(self):
        for alg in QgsApplication.processingRegistry().algorithms():
            print(alg.id(), "->", alg.displayName())
        processing.algorithmHelp('grass7:v.clean')
        processing.algorithmHelp('grass7:v.buffer')

    def close(self):
        self.app.exitQgis()
        self.app.exit()


if __name__ == '__main__':
    home = os.path.expanduser('~')
    pass
# ========================= EOF ====================================================================
