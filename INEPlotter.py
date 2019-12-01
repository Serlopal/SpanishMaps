import plotly.graph_objects as go
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from urllib.request import urlopen
import json
import geopandas
import numpy as np
import os
from unidecode import unidecode
import urllib.request
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin
import os
import re
from unidecode import unidecode


class INEMapPlotter:
	def __init__(self):

		self.geo_data_file_path = "data/espana-municipios-geojson-carto/shapefiles_espana_municipios.geojson"
		self.data_folder = "data_population"
		self.processed_data_folder = "data_population_processed"
		self.processed_data_file = "processed_data.csv"
		self.data_bucket = []
		self.id_cols = [("f_codmun", lambda x: int(x))]
		self.csv_format = {"sep": ";", "error_bad_lines": False, "skiprows": 6, 'dtype': str, 'header': None}
		self.processed_data = None

		self.geo_data = self.load_geojson_data()
		# self.geo_data = self.load_shapefile_data(geo_data_file_path, id_cols, property_cols)

	def plot_data(self, base_url, year, sex="both", reprocess=False, redownload=False):
		processed_data_file_path = os.path.join(self.processed_data_folder, self.processed_data_file)

		if not os.path.exists(processed_data_file_path) or reprocess:
			self.download_data(base_url, redownload=redownload)
			self.process_data()

		pdata = pd.read_csv(processed_data_file_path)

		colorscale = [[0.0, "rgb(165,0,38)"],
					 [0.1111111111111111, "rgb(215,48,39)"],
					 [0.2222222222222222, "rgb(244,109,67)"],
					 [0.3333333333333333, "rgb(253,174,97)"],
					 [0.4444444444444444, "rgb(254,224,144)"],
					 [0.5555555555555556, "rgb(224,243,248)"],
					 [0.6666666666666666, "rgb(171,217,233)"],
					 [0.7777777777777778, "rgb(116,173,209)"],
					 [0.8888888888888888, "rgb(69,117,180)"],
					 [1.0, "rgb(49,54,149)"]]

		pdf = pdata[pdata.sex == sex]

		plotter.draw_choropleth(ids=pdf["zip_code"],
								z=pdf[str(float(year))],
								text=pdf["city"],
								zmin=10000,
								zmax=100000,
		                        colorscale=colorscale,
		                        marker_opacity=0.8,
								marker_line_width=0.1,
								reversescale=True)

	def download_data(self, base_url, redownload):

		print("**************************************")
		print("******	 DOWNLOAD DATA    ***********")
		print("**************************************")
		data_format = "CSV separado por ;"

		contents = urllib.request.urlopen(base_url).read()
		soup = BeautifulSoup(contents, 'lxml')

		for link in soup.findAll('a', {'title': 'Descarga ficheros'}):

			# get file name that we are downloading
			file_name = None
			for item in link.next_siblings:
				if isinstance(item, Tag) and item['class'][0] == "titulo":
					file_name = re.sub(r'\W+', '', unidecode(item.get_text().split(":")[0])) + ".csv"
			if not file_name: raise Exception("Could not find filename!")

			# check data is already downloaded
			file_path = os.path.join(self.data_folder, file_name)
			if os.path.exists(file_path) and not redownload:
				print("File {} already cached!".format(file_name))
			else:
				# follow download website link
				download_page_url = urljoin(base_url, link["href"])
				# read download website in raw format
				down_load_page_raw = urllib.request.urlopen(download_page_url).read()
				# parse download website
				download_page_soup = BeautifulSoup(down_load_page_raw, 'lxml')
				# find download link for the desired data format
				download_link = urljoin(download_page_url, download_page_soup.find('a', text=data_format)["href"])
				# download
				download_file = pd.read_csv(download_link, **self.csv_format)

				def fix_value(x):
					"""
					some values come in the format that places . every 3 digits to facilitate reading
					"""
					try:
						r = float(x)
					except:
						r = float(str(x).replace(".", ""))
					return r

				# cast all values from string to float
				download_file.iloc[:, 1:] = download_file.iloc[:, 1:].applymap(fix_value)
				# save to disk
				download_file.to_csv(file_path, sep=self.csv_format["sep"], header=None)

				print("Downloaded {} to {}".format(download_link, self.data_folder))

			# load file from disk
			self.data_bucket.append(pd.read_csv(file_path, sep=self.csv_format["sep"], header=None))

	def process_data(self):
		print("**************************************")
		print("******	PROCESSING DATA   ***********")
		print("**************************************")

		nsex= 3
		acc = []
		for df in self.data_bucket:
			# extract numpy array from original dataframe that needs cleaning
			v = df.values
			# get years of data and unique years of data
			years = v[0, 2:-1].astype(str)
			unique_years = set(years)
			nyears = len(unique_years)
			cities = v[1:-5, 1]
			# get values
			values = v[1:-5, 2:-1]
			# shift the replication of year on the columns to new rows instead
			values = values.reshape((len(values)*nsex, nyears))
			# replicate cities axis as many times as different sexes we have
			cities = np.expand_dims(np.repeat(cities, nsex), axis=1)
			# create final dataframe (without sex yet)
			df = pd.DataFrame(np.hstack((cities, values)), columns=["city"] + list(unique_years))
			df.insert(0, "sex", np.tile(["both", "male", "female"], df.city.nunique()))

			acc.append(df)

		# extract postal code
		all_data = pd.concat(acc)
		all_data.insert(1, "zip_code", all_data.city.apply(lambda x: x.split(" ")[0].zfill(5)))

		self.processed_data = all_data
		# cache processed_data to disk
		all_data.to_csv(os.path.join(self.processed_data_folder, self.processed_data_file))

	def load_geojson_data(self):
		encoding = "Latin-1"

		with open(self.geo_data_file_path, encoding=encoding) as f:
			geo_data = json.load(f)

		# cast geojson to plotly format
		for x in geo_data["features"]:
			def f(q): return q
			x["id"] = None
			for c in self.id_cols:
				if isinstance(c, tuple):
					c, f = c
				# fill id with the first allowed id_col available
				if c in x["properties"]:
					x["id"] = f(x["properties"][c])
					break

		return geo_data

	def load_shapefile_data(self, file, id_col, property_cols):
		return self.geodataframe_to_plotly(geopandas.read_file(file), id_col=id_col, properties=property_cols)

	@staticmethod
	def geodataframe_to_plotly(df, id_col, properties):
		"""
		:param df: geodataframe containing de map polygon descriptions inside the geometry column
		:param id_col: column frrom the geodataframe to use as id for the Polygon
		:param properties: extra info to be included into the geojson
		:return: geojson version of the geodataframe
		"""
		geojson = {'type': 'FeatureCollection', 'features': []}
		for _, row in df.iterrows():
			if type(row['geometry']).__name__ == 'Polygon':
				coords = [list(map(list, list(row['geometry'].exterior.coords)))]
				geom = {
						'type': 'Polygon',
						'coordinates': coords
					   }
			else:
				coords = [[list(map(list, list(x.exterior.coords)))] for x in row["geometry"]]
				geom = {
						'type': 'MultiPolygon',
						'coordinates': coords
					   }

			feature = {
						'type': 'Feature',
						'properties': {prop: row[prop] for prop in properties},
						'geometry': geom,
						'id': row[id_col]
					  }

			geojson['features'].append(feature)
		return geojson

	def draw_choropleth(self, ids, z, **kwargs):
		# plot using plotly
		fig = go.Figure(go.Choroplethmapbox(geojson=self.geo_data,
											locations=ids,
											z=z,
											**kwargs)
						)

		fig.update_layout(mapbox_style="carto-positron", mapbox_zoom=3, mapbox_center={"lat": 40.4637, "lon": 3.7492})
		fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
		fig.show()


if __name__ == "__main__":
	# load population data
	age_data = pd.read_csv("data/Censuses2011_2.csv", encoding="latin-1")
	# extract zip code from municipality column
	age_data["cp"] = age_data["Municipality of residence"].apply(lambda x: int(x.split(" ")[0]))

	plotter = INEMapPlotter()

	plotter.plot_data("https://www.ine.es/dynt3/inebase/index.htm?padre=525",
					  year=1998, sex="both",
					  reprocess=True,
					  redownload=False)







