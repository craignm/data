# Importing CDC 500 PLACES Data

Author: Padma Gundapaneni @padma-g

## Table of Contents
1. [About the Dataset](#about-the-dataset)
    1. [Download URL](#download-url)
    2. [Overview](#overview)
    3. [Notes and Caveats](#notes-and-caveats)
    4. [License](#license)
    5. [Dataset Documentation and Relevant Links](#dataset-documentation-and-relevant-links)
2. [About the Import](#about-the-import)
    1. [Artifacts](#artifacts)
    2. [Import Procedure](#import-procedure)

## About the Dataset

### Download URL
The datasets can be downloaded at the following links from [the CDC website](https://chronicdata.cdc.gov/browse?category=500+Cities+%26+Places&sortBy=newest&utf8). We need to manually search in the website for the latest release files for the below dataset and add the required configuration in json file present in the [GCP Bucket Location](gs://datcom-csv/cdc500_places/)
- PLACES: Local Data for Better Health, Census Tract Data
- PLACES: Local Data for Better Health, County/Country Data
- PLACES: Local Data for Better Health, Place (City) Data
- PLACES: Local Data for Better Health, ZCTA (Zip Code) Data

To download all datasets available, run the following command. The download will take 5-10 minutes total. Files will be downloaded and extracted to a `raw_data` folder.
```bash
$ python3 download_bulk.py
```

All the downloaded data is in .csv format. 

### Overview
The data imported in this effort is from the CDC's [500 Places project](https://www.cdc.gov/places/about/index.html), a continuation of the [500 Cities project](https://www.cdc.gov/places/about/500-cities-2016-2019/index.html), and is provided by the CDC's [National Center for Chronic Disease Prevention and Health Promotion](https://www.cdc.gov/chronicdisease/index.htm). The datasets contain "estimates for 27 measures: 5 chronic disease-related unhealthy behaviors, 13 health outcomes, and 9 on use of preventive services. These estimates can be used to identify emerging health problems and to inform development and implementation of effective, targeted public health prevention activities."

### Notes and Caveats

For data refresh for CDC500 import we need to manually search in the website for the latest release files across all geo levels and add the required configuration in [Json file](gs://datcom-csv/cdc500_places/download_config.json) present in the GCP Bucket Location. The config file is present locally as well [download_config.json](https://github.com/datacommonsorg/data/blob/master/scripts/us_cdc/500_places/download_config.json) we can use this file as well to generate the output.

NOTE: If any changes made in local config update same changes in config file present in GCP as well vice versa. We should always keep both config file in sync.

Please fill the json file for the latest release data in below format:

```
{
        "release_year": {ReleaseYear}, 
        "parameter": [
            {
                "URL": "Download link of latet release",
                "FILE_TYPE": "Geo Level of the data should be either [County, City, ZipCode, CensusTract]",
                "FILE_NAME": "{GeoLevel}_raw_data_2022.csv"
            }
        ]
    }
```

Example:
{
        "release_year": 2022,
        "parameter": [
            {
                "URL": "https://data.cdc.gov/api/views/duw2-7jbt/rows.csv?accessType=DOWNLOAD",
                "FILE_TYPE": "County",
                "FILE_NAME": "county_raw_data_2022.csv"
            },
            {
                "URL": "https://data.cdc.gov/api/views/epbn-9bv3/rows.csv?accessType=DOWNLOAD",
                "FILE_TYPE": "City",
                "FILE_NAME": "city_raw_data_2022.csv"
            },
            {
                "URL": "https://data.cdc.gov/api/views/nw2y-v4gm/rows.csv?accessType=DOWNLOAD",
                "FILE_TYPE": "CensusTract",
                "FILE_NAME": "censustract_raw_data_2022.csv"
            },
            {
                "URL": "https://data.cdc.gov/api/views/gd4x-jyhw/rows.csv?accessType=DOWNLOAD",
                "FILE_TYPE": "ZipCode",
                "FILE_NAME": "zipcode_raw_data_2022.csv"
            }
        ]
    }

### License
The data is made available for public-use by the [CDC](https://www.cdc.gov/nchs/data_access/ftp_data.htm). Users of CDC National Center for Health Statistics Data must comply with the CDC's [data use agreement](https://www.cdc.gov/nchs/data_access/restrictions.htm).

### Dataset Documentation and Relevant Links
These data were collected and provided by the [CDC National Center for Chronic Disease Prevention and Health Promotion](https://www.cdc.gov/chronicdisease/index.htm). The documentation for the datasets is accessible [here](https://www.cdc.gov/places/about/index.html).

## About the Import

### Artifacts

#### Scripts
[`download_bulk.py`](https://github.com/datacommonsorg/data/blob/master/scripts/us_cdc/500_places/download_bulk.py)

[`parse_cdc_places.py`](https://github.com/datacommonsorg/data/blob/master/scripts/us_cdc/500_places/parse_cdc_places.py)

[`run.sh`](https://github.com/datacommonsorg/data/blob/master/scripts/us_cdc/500_places/run.sh)

#### Test Scripts
[`parse_cdc_places_test.py`](https://github.com/datacommonsorg/data/blob/master/scripts/us_cdc/500_places/parse_cdc_places_test.py)

#### tMCFs
[`cdc_places.tmcf`](https://github.com/datacommonsorg/data/blob/master/scripts/us_cdc/500_places/cdc_places.tmcf)

### Import Procedure

#### Testing

##### Test Data Cleaning Script

To test the config file is sync with each other and data cleaning script, run:

```bash
$ python3 parse_cdc_places_test.py
```

The expected output of this test can be found in the [`test_data`](https://github.com/datacommonsorg/data/blob/master/scripts/us_cdc/500_places/test_data/) directory.

#### Data Download and Processing Steps

To download and clean all the data files at once run `run.sh`:

```bash
$ sh run.sh
```
