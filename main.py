import argparse
import requests # For... yeah.
import configparser
import logging
import logging.handlers # For RotatingFileHandler
import os, sys, datetime, time, platform
import keyring
import browser_cookie3
import geopandas as gpd 
# import psycopg2, geoalchemy
import fiona 
import numpy as np
import pandas as pd 
from sqlalchemy import create_engine

# First thing, logs directory
if not os.path.exists("logs"):
    os.makedirs("logs")
# Timing
start_time = time.time()
start_datetime = datetime.datetime.utcnow()

##### Logging
logger = logging.getLogger() # Root logger
log_file_name = "logs" + os.sep + "google_location_history_downloader.log"
log_file_handler = logging.handlers.RotatingFileHandler(log_file_name, maxBytes=5000000, backupCount=5)
log_console_handler = logging.StreamHandler(sys.stdout)
log_formatter = logging.Formatter("%(asctime)s [%(threadName)s] [%(levelname)s]  %(message)s")
log_file_handler.setFormatter(log_formatter)
log_console_handler.setFormatter(log_formatter)
logger.setLevel(logging.INFO)
logger.addHandler(log_file_handler)
logger.addHandler(log_console_handler)

logger.info("Google Location History Exporter v1.0")

# Parse arguments first
parser = argparse.ArgumentParser(prog="main.py", description="Export history. Well, _your_ history.")
# Operational arguments
parser.add_argument("--destination", "-d", dest="destination", required=False, default="kml", type=str, help="TBD what the options are; raw KML is a start?")
parser.add_argument("--destination-path", "-p", dest="destination_path", required=True, type=str, help="If files, the path where these will be stored. Default is a data subfolder in the current working directory.")
parser.add_argument("--mode", "-m", dest="mode", required=False, default="yesterday", type=str, help="Either \"yesterday\" or \"full\".")
parser.add_argument("--start-date", "-s", dest="start_date", required=False, type=str, help="Only relevant when in \"full\" mode. If not specified, the default is yesterday. The format to be used is yyyy-mm-dd")
parser.add_argument("--config-file", "-c", dest="config_file", required=False, type=str, help="The config file to be read, with additional tweaks and options. The default is config/config.ini. Probably going to be containing references to credentials for databases?")
parser.add_argument("--authuser", "-a", dest="authuser", required=False, default="0", type=str, help="If you're logged in to multiple Google accounts in your Chrome session, use this to specify a different one. Default 0.")

args = parser.parse_args()

if args.destination_path is None:
    # ./data
    args.destination_path = "." + os.sep + "data" + os.sep

logger.info(f"Destination path: { args.destination_path }")

# Determine start and end date based on input or nothing
if (args.mode == "full" and args.start_date is None) or (args.mode == "yesterday"):
    # Yesterday as string, which we'll parse later (it's silly)
    start_date = datetime.date.today() - datetime.timedelta(days=1)
    end_date = start_date
elif args.mode == "full":
    try:
        start_date = datetime.date.fromisoformat(args.start_date)
    except Exception as e:
        logger.error(f"Failed to parse start date: { args.start_date }. Is it in the right format (yyyy-mm-dd)?")
        exit(1)
    end_date = datetime.date.today() - datetime.timedelta(days=1)
else:
    logger.error(f"Unsupported mode: { args.mode }.")
    exit(1)

logger.info(f"Mode: { args.mode }")
logger.info(f"Date range: { start_date } - { end_date }")

# We need to omit the leading 0 for the day in the date format string later on, otherwise Google does not "understand" the request. For some reason, there is no cross-platform format string for this, but we need to fiddle.
logger.info(f"Running on platform: { platform.system() }. Using the appropriate date format string.")
if platform.system() == "Windows":
    date_day_format_string = "%#d"
else:
    date_day_format_string = "%-d"

# Process config.ini second
if args.config_file is None:
    args.config_file = "config" + os.sep + "config.ini"
logger.info(f"Config file path: { args.config_file }")
try:
    config = configparser.ConfigParser()
    config.read(args.config_file)
except Exception as e:
    logger.error("Problem reading config file. Exiting.")
    logger.error(e)
    exit(1)

# Create the local destination folder regardless of actions, if it doesn't exist
if not os.path.exists(args.destination_path):
    os.makedirs(args.destination_path)

# Get cookies from Chrome
# We may need to think about profiles and stuff? Eh.
cookies = browser_cookie3.chrome(domain_name='.google.com')

# Database
fiona.drvsupport.supported_drivers['KML'] = 'rw' # Import KML Driver
postgres_password = keyring.get_password(service_name=config.get('postgres', 'password_keyring_reference'), username=config.get('postgres', 'username'))
if postgres_password is None:
    logger.error(f"Failed to get password for reference { config.get('postgres', 'password_keyring_reference') }. We have to exit...")
    exit(1)
postgres_db_connection_url = f"postgresql://{config.get('postgres', 'username')}:{postgres_password}@{config.get('postgres', 'server')}:{config.get('postgres', 'port')}/{config.get('postgres', 'database')}"
sqlalchemy_engine = create_engine(postgres_db_connection_url)

# Let's go
# Determine URL. E.g.:
# https://www.google.com/maps/timeline/kml?authuser=0&pb=!1m8!1m3!1i2017!2i3!3i16!2m3!1i2017!2i3!3i16
gl_url_base = f"https://www.google.com/maps/timeline/kml?authuser={ args.authuser }&pb=!1m8!1m3!1i"

# Iterdate
dates_range = [start_date + datetime.timedelta(days=x) for x in range((end_date-start_date).days + 1)]
for date in dates_range:
    date_for_request = datetime.date.strftime(date, "%Y") + "!2i" + str(date.month - 1) + "!3i" + datetime.date.strftime(date, date_day_format_string)
    gl_url_full = f"{gl_url_base}{ date_for_request }!2m3!1i{ date_for_request }"
    logger.info(f"Getting location info for { date }: { gl_url_full }")
    # Get KML
    try:
        response = requests.get(url=gl_url_full, cookies=cookies)
    except Exception as e:
        logger.warning(f"Failed to get data for { date }:")
        logger.warning(e)
    else:
        try:
            kml_file = os.path.join(args.destination_path, datetime.datetime.strftime(date, "%Y-%m-%d") + ".kml")
            with open(file=kml_file, mode="w", encoding="utf-8") as f:
                f.write(response.text)
        except Exception as e:
            logger.warning(f"Failed to write file for { date }:")
            logger.warning(e)
        else:
            # Read from the file. Lame, but easy.
            try:
                geo_df = gpd.read_file(filename=kml_file, driver="KML")
                geo_df["filename"] = kml_file
                # Clear if this file was already uploaded
                with sqlalchemy_engine.connect() as sqlalchemy_connection:
                    sqlalchemy_connection.execute(statement=f"DELETE FROM { config.get('postgres', 'schema') }.{ config.get('postgres', 'table') } WHERE filename = '{ kml_file }'")
                geo_df.to_postgis(name=config.get("postgres", "table"), schema=config.get("postgres", "schema"), con=sqlalchemy_engine, if_exists="append")
            except Exception as e:
                logger.warning(f"Failed to write data to database for { date }:")
                logger.warning(e)