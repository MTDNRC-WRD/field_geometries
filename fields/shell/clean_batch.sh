#!/usr/bin/env bash
eval "$(conda shell.bash hook)"
conda activate qs
shopt -s nullglob 
export PREFIX=/usr
PREFIX=$CONDA_PREFIX
export QT_QPA_PLATFORM=offscreen
export PYTHONPATH=$PREFIX/share/qgis/python/plugins/processing:$PREFIX/share/qgis/python:$PYTHONPATH
EXT=shp
STATES=("MT")
for STATE in ${STATES[*]}; do
	baseDir="/media/research/IrrigationGIS/openET/MGRS/split_aea/$STATE"
	for path in $(find ${baseDir} -maxdepth 1 -mindepth 1 -type d); do
        	echo "clean_geometries $STATE "$(basename "${path}")""
		python /home/dgketchum/PycharmProjects/openet-tools/fields/vector/clean_geometries.py "$STATE" "$(basename "${path}")" False
done
done

