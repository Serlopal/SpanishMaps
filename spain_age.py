import geopandas as gpd
import pandas as pd

from bokeh.io import show
from bokeh.models import LogColorMapper
from bokeh.palettes import Viridis6 as palette
from bokeh.plotting import figure
import bokeh

# BOKEH_RESOURCES=inline


from shapely.geometry import Point


# load municipalities geo data
geo_data = gpd.read_file("Municipios_ETRS89_30N/municipios_etrs89_30n.shp")
# load population data
age_data = pd.read_csv("Censuses2011_2.csv", encoding="latin-1")
# extract zip code from municipality column
age_data["cp"] = age_data["Municipality of residence"].apply(lambda x: int(x.split(" ")[0]))

# merge into a global dataframe with population an geo data
data = geo_data.merge(age_data, how="left", left_on="codigo", right_on="cp")


print(data.columns)


# ----------- PLOT USING BOKEH --------------------
palette.reverse()

# extract data from geopandas format to bokeh
lat_data = []
lon_data = []
city_names = []
age_data = []
for index, row in data.iterrows():
	# build list of polygons artificially if there is only a single one or taking the multipolygon if there are several
	if type(row['geometry']).__name__ == "MultiPolygon":
		multi = row['geometry']
	else:
		multi = [row['geometry']]

	# number of polygons
	n_poly = len(multi)

	# for each polygon a city has
	for poly in multi:
		# accumulators for latitude and longitude vertex points
		lat_acc = []
		lon_acc = []
		# for each vertex in that poligon
		for pt in list(poly.exterior.coords):
			lon, lat = pt
			# add coordinates from that vertex to list that define polygon
			lat_acc.append(lat)
			lon_acc.append(lon)
		# add list for polygon to list of final polygon data
		lat_data.append(lat_acc)
		lon_data.append(lon_acc)
	# now add the name of city and avg age as many times as polygons the entry had
	city_names.extend([row["Municipality of residence"]] * n_poly)
	age_data.extend([row["Average age"]] * n_poly)

# set color pallette for bokeh
color_mapper = LogColorMapper(palette=palette)

# lon_data = lon_data[:1000]
# lat_data = lat_data[:1000]
# city_names = city_names[:1000]
# age_data = age_data[:1000]

# put data together into a single dict data structure
data = dict(
	x=lon_data,
	y=lat_data,
	name=city_names,
	rate=age_data,
	)

# choose tools to be display in the UI
TOOLS = "pan,wheel_zoom,reset,hover,save"

# create figure
p = figure(
	title="Spain demographic map: average age by municipality", tools=TOOLS,
	x_axis_location=None, y_axis_location=None,
	tooltips=[("Name", "@name"), ("Unemployment rate)", "@rate%"), ("(Long, Lat)", "($x, $y)")],
	output_backend="webgl",
	plot_width=1350,
	plot_height=900)
p.grid.grid_line_color = None
p.hover.point_policy = "follow_mouse"

p.patches('x', 'y', source=data,
			fill_color={'field': 'rate', 'transform': color_mapper},
			fill_alpha=0.7, line_color="white", line_width=0.5)

show(p)
