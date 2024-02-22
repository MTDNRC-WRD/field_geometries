#!/usr/bin/env bash
eval "$(conda shell.bash hook)"
conda activate qs
shopt -s nullglob 
export PREFIX=/usr
PREFIX=$CONDA_PREFIX
export QT_QPA_PLATFORM=offscreen
export PYTHONPATH=$PREFIX/share/qgis/python/plugins/processing:$PREFIX/share/qgis/python:$PYTHONPATH
EXT=shp
STATE=("MT")
#baseDir="/home/dgketchum/data/IrrigationGIS/Montana/statewide_irrigation_dataset/future_work_15FEB2024/MGRS/split_filtered_aea"
baseDir="/media/research/IrrigationGIS/Montana/statewide_irrigation_dataset/future_work_15FEB2024/MGRS/split_filtered_aea"
for path in $(find ${baseDir} -maxdepth 1 -mindepth 1 -type d); do
        echo "clean_geometries $STATE  "$(basename "${path}")""
  python /home/dgketchum/PycharmProjects/flatten_geometry/fields/clean_geometries.py "$STATE" "$(basename "${path}")" False
  done

