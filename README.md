# flatten_geometry
Create a mosaic of non-overlapping geometries using PyQGIS internals


This repository holds code that accepts a prioritized list of shapefiles, splits them into a grid system, 
and adds them to a single shapefile. The intent is to maximize the coverage of the polygons over the surface while
not creating any overlapping areas. This code was used to create the agricultural fields polygon GIS coverage
now in use in the OpenET project. See https://onlinelibrary.wiley.com/doi/full/10.1111/1752-1688.12956

In its current state, the project uses the Military Grid Reference System to split shapefiles into small enough
pieces that the compute-intensive PyQGIS algorithm can complete.

In this example, I'll refer the project as I used it to compile a new (potential) fields database for Montana DNRC in 
February, 2024. I have two sources of data the USDA FSA Common Land Unit (CLU) and Montana Department of Natural
Resources and Conservation (DNRC) data sources. The CLU is a messy, frequently overlapping, but high-coverage dataset
that has many good agricultural field boundaries in it alongside property parcel and natural feature delineations.
The DNRC data is carefully digitized irrigated field boundaries with attributes describing the field irrigation
type, the intern who edited the geometry, and a confidence estimate of the liklihood of active irrigation in 2019/2020.
While the DNRC data is very high quality for the purposes of using it alongside satellite remote sensing estimates
of irrigation water use to tabulate water use volumes, the data is not comprehensive, that is, there are many small
fields in remote locations that were not included. The purpose of this approach is to add what we think are likely
irrigated fields from the CLU data using an automated process. 

The workflow is as follows:

1. Split the CLU and DNRC state-wide datasets into MGRS tiles using split_mgrs.py.
2. Use a raster land use/land cover dataset to perform zonal statistics on what polygons in the split data are
irrigated fields. For this, we used IrrMapper (https://www.mdpi.com/2072-4292/12/14/2328) 
and Cropland Data Layer (https://www.tandfonline.com/doi/full/10.1080/10106049.2011.562309). We use the code in our
DNRC repository to do so: https://github.com/MTDNRC-WRD/irrigation-dataset/future_work/field_properies.py. This code
makes it easy to load the split CLU data into Earth Engine, extract IrrMapper and CDL, and return data in .csv that
describes each field. This approach requires Earth Engine access. Note: An alternative approach would be to download CDL
rasters from CropScape (https://nassgeodata.gmu.edu/CropScape/) and use the zonal_cdl() function in 
fields/shape_ops.py to extract data indicating the crop coverage of each field  and filter out unwanted land classes. 
At this step the code in field_properties.py will filter the fields that will be excluded. 
In write_field_properties(), we used a threshold of fraction irrigated from 2017-2022 and ensured the field was 
majority agriculture according to CDL.
3.  