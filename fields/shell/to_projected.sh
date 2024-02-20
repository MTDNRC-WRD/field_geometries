#!/usr/bin/env bash
eval "$(conda shell.bash hook)"
conda activate qs
shopt -s nullglob 
export PREFIX=/usr
PREFIX=$CONDA_PREFIX
export QT_QPA_PLATFORM=offscreen
export PYTHONPATH=$PREFIX/share/qgis/python/plugins/processing:$PREFIX/share/qgis/python:$PYTHONPATH
EXT=shp
srcDir="/home/dgketchum/data/IrrigationGIS/openET/MGRS/split_cropped"
dstDir="/home/dgketchum/data/IrrigationGIS/openET/MGRS/split_aea"
states=("WI")
for state in ${states[*]}; do
	stateDir="$srcDir/$state"
	for path in $(find ${stateDir} -maxdepth 1 -mindepth 1 -type d); do
        	cd "$path"
		mgrs="$(basename "${path}")"
		mkdir -p "$dstDir/$state/$mgrs"
		for i in $path/*; do
			if [ "${i}" != "${i%.${EXT}}" ];then
        			echo "$i to $dstDir/$state/$mgrs/$(basename "${i}")"
				ogr2ogr -f "ESRI Shapefile" -s_srs EPSG:4326 -t_srs "+proj=aea +lat_0=40 +lon_0=-96 +lat_1=20 +lat_2=60 +x_0=0 +y_0=0 +ellps=GRS80 						+towgs84=0,0,0,0,0,0,0 +units=m +no_defs" "$dstDir/$state/$mgrs/$(basename "${i}")" "$i"
			fi
done
done
done

