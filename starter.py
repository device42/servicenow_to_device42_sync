#!/usr/bin/python

""" README
    This script is deprecated. Please use https://github.com/device42/servicenow_device42_mapping

    This script reads CIs from Servicenow and uploads them to Device42.
    It has 2 modes:
    1. Full migration  - when the TIMEFRAME is set to 0
    2. Synchronization - when the TIMEFRAME is set to anything else but 0


GOTCHAS
* In order for hardwares to be migrated, hardware must have unique name.
* When there are multiple devices with the same name, device name is constructed as: "device_name" + "_" + "servicenow_sys_id"
    i.e. " MacBook Air 13" " will become " MacBook Air 13"_01a9280d3790200044e0bfc8bcbe5d79 "
*
"""

import sys
from srvnow2d42 import ServiceNow


__version__     = "2.0.2"
__status__      = "Production"


# ===== Device42 ===== #
D42_USER    = 'admin'
D42_PWD     = 'adm!nd42'
D42_URL     = 'https://192.168.3.30'

# ===== ServiceNow ===== #
USERNAME    = 'admin'
PASSWORD    = 'admin123'
BASE_URL    = 'https://dev13852.service-now.com/api/now/table/'
LIMIT       = 1000000 # number of CIs to retrieve from ServiceNow
HEADERS     = {"Content-Type":"application/json","Accept":"application/json"}
TABLES      = ['cmdb_ci_server' , 'cmdb_ci_computer', 'cmdb_ci_app_server', 'cmdb_ci_database', 'cmdb_ci_email_server',
               'cmdb_ci_ftp_server', 'cmdb_ci_directory_server', 'cmdb_ci_ip_server']

# ===== Other ===== #
DEBUG        = True    # print to STDOUT
DRY_RUN      = False   # Upload to Device42 or not
ZONE_AS_ROOM = True    # for the explanation take a look at get_zones() docstring
TIMEFRAME    = 0       # Value represents hours. If set to 0, script does full migration, if set to any other value,
                       # script syncs changes back from  till now(). now() refers to current localtime.


if __name__ == '__main__':
    snow = ServiceNow(D42_URL, D42_USER, D42_PWD, USERNAME, PASSWORD, BASE_URL, LIMIT,
                        HEADERS, DEBUG, DRY_RUN, ZONE_AS_ROOM, TIMEFRAME)
    snow.create_db()
    snow.get_relationships()
    snow.get_manufacturers()
    snow.get_hardware()
    snow.get_locations()
    snow.get_buildings()
    snow.get_rooms()
    if ZONE_AS_ROOM:
        snow.get_zones()
    snow.get_racks()
    for table in TABLES:
        snow.get_computers(table)
    snow.get_adapters()
    snow.get_ips()
    snow.upload_adapters()

    sys.exit()
