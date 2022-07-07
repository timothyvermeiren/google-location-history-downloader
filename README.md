# google-location-history-downloader

Ubuntu:
sudo apt install postgresql-11-postgis-2.5

Postgres:
CREATE EXTENSION postgis;

Requirements for geopandas and fiona:

python -m pip install wheel
python -m pip install pipwin

python -m pipwin install numpy
python -m pipwin install pandas
python -m pipwin install shapely
python -m pipwin install gdal
python -m pipwin install fiona
python -m pipwin install pyproj
<!-- python -m pipwin install six -->
python -m pipwin install rtree
python -m pip install geopandas

And then it's easier to go for the rest:
python -m pip install -r requirements.txt

From: https://stackoverflow.com/questions/54734667/error-installing-geopandas-a-gdal-api-version-must-be-specified-in-anaconda