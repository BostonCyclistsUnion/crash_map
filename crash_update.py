import requests
from datetime import datetime
import geopandas as gpd
import pandas as pd

def call_api(url):
  response = requests.get(url)
  if response.status_code == 200:
    data = response.json()
    return data['result']['records']
  else:
    print(f"Error: {response.status_code}")
    print(response.text)
    return None
  
def collect_records(resource_id, date_field, filename, st, end):
    """Collect records from the specified resource_id between the start and end dates.
    The records are collected by year to ensure all data is collected.
    
    Args:
    resource_id (str): the resource id for the dataset
    date_field (str): the field in the dataset that contains the date
    filename (str): the filename to write the data to
    st (str): the start date in the format 'YYYY-MM-DD'
    end (str): the end date in the format 'YYYY-MM-DD'"""

    collect_records = []
    st_year = datetime.strptime(st, '%Y-%m-%d').year
    end_year = datetime.strptime(end, '%Y-%m-%d').year
    for year in range(st_year, end_year+1):
        print(year)
        st_date = f'{year}-01-01'
        end_date = f'{year+1}-01-01'
        sql = f"""SELECT {date_field}, mode_type, location_type, street, xstreet1, xstreet2, lat, long
        from "{resource_id}" 
        WHERE {date_field}>='{st_date}' and {date_field}<'{end_date}'"""
        url = f"https://data.boston.gov/api/3/action/datastore_search_sql?sql={sql}"
        result = call_api(url)
        if result:
            collect_records.extend(result)

    # write to file
    print(f"Total records: {len(collect_records)}")
    with open(f'data/{filename}.csv', 'w') as f:
        f.write(f'{date_field},mode_type,location_type,street,xstreet1,xstreet2,lat,long\n')
        for record in collect_records:
            f.write(','.join([str(record[key]) for key in [date_field, 'mode_type', 'location_type', 'street', 'xstreet1', 'xstreet2', 'lat', 'long']]) + '\n')

resource_dict = {}
# Boston Vision Zero crash data
# https://data.boston.gov/dataset/vision-zero-crash-records/resource/e4bfe397-6bfc-49c5-9367-c879fac7401d
resource_dict['crash'] = {}
resource_dict['crash']['resource'] = 'e4bfe397-6bfc-49c5-9367-c879fac7401d'
# this field changes depending on the dataset
resource_dict['crash']['date_field'] = 'dispatch_ts'


# Boston Vision Zero fatality data
# https://data.boston.gov/dataset/vision-zero-fatality-records/resource/92f18923-d4ec-4c17-9405-4e0da63e1d6c
resource_dict['fatality'] = {}
resource_dict['fatality']['resource'] = '92f18923-d4ec-4c17-9405-4e0da63e1d6c'
resource_dict['fatality']['date_field'] = 'date_time'

# specify the time bounds
st = '2019-01-01'
end = '2024-05-01'

for k in resource_dict:
    resource_id = resource_dict[k]['resource']
    filename = k
    date_field = resource_dict[k]['date_field']
    collect_records(resource_id, date_field, filename, st, end)

# read in and process to geojson
df = gpd.GeoDataFrame(pd.read_csv('data/crash_records.csv'))
df.set_geometry(gpd.points_from_xy(df.long, df.lat), inplace=True)
# collect mode types
mode_types = df['mode_type'].unique()
for m in mode_types:
    print(m)
    m_df = df[df.mode_type == m]
    print(m_df.shape)
    # group by geometry, get string of dates
    m_df = m_df.fillna('').groupby('geometry').agg({'dispatch_ts':[lambda x: ','.join(x),
                                                    pd.Series.nunique,],
                                        'xstreet1': pd.Series.max,
                                        'xstreet2': pd.Series.max}).reset_index()
    # rename
    m_df.columns = ['geometry', 'crash_dates', 'total_crashes', 'xstreet1', 'xstreet2']
    # getting an id for reference
    # TODO: this probably isn't necessary
    m_df.reset_index(inplace=True)
    # functions in js assume this order
    m_df.sort_values('total_crashes', inplace=True, ascending=False)
    m_df = gpd.GeoDataFrame(m_df)
    m_df.to_file(f"./data/{m}_rollup.geojson", driver='GeoJSON')