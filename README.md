
##ServiceNow to Device42
------------------------------------
#This script is deprecated. Please use https://github.com/device42/servicenow_device42_mapping

[Device42](http://www.device42.com/) is a comprehensive data center inventory management and IP Address management software 
that integrates centralized password management, impact charts and applications mappings with IT asset management.


This script reads CIs from Servicenow and uploads them to Device42.
It has 2 modes:

1. Full migration  - when the TIMEFRAME is set to 0
2. Synchronization - when the TIMEFRAME is set to anything else but 0

### Requirements
-----------------------------
* python 2.7.x
* requests

### Compatibility
-----------------------------
* Script runs on any OS capable of running Python 2.7.x
	
	
### Usage
-----------------------------
Set params in **starter.py**

* Set Device42 params
```
# ===== Device42 ===== #
D42_USER    = 'username'
D42_PWD     = 'password'
D42_URL     = 'https://device42_server_ip'
```

* Set Servicenow params
```
# ===== ServiceNow ===== #
USERNAME    = 'servicenow_username'
PASSWORD    = 'servicenow_password'
BASE_URL    = 'https://your_servicenow_instance/api/now/table/'
LIMIT       = 1000000 
HEADERS     = {"Content-Type":"application/json","Accept":"application/json"}
TABLES      = ['cmdb_ci_server' , 'cmdb_ci_computer', 'cmdb_ci_app_server', 'cmdb_ci_database', 'cmdb_ci_email_server',
               'cmdb_ci_ftp_server', 'cmdb_ci_directory_server', 'cmdb_ci_ip_server']
```
* Description
    * LIMIT - number of CIs to retrieve from ServiceNow
    * TABLES  - Servicenow database tables that contain servers and workstations

* set other params
```
# ===== Other ===== #
DEBUG        = True    
DRY_RUN      = False   
ZONE_AS_ROOM = True   
TIMEFRAME    = 0 
```
* Description
    * DEBUG - print to STDOUT
    * DRY_RUN - upload to Device42 or not
    * ZONE_AS_ROOM  - in case ZONE_AS_ROOM=True, zones are uploaded as rooms to the parent building.
    * TIMEFRAME  - Value represents hours. If set to 0, script does full migration, if set to any other value, script syncs changes from TIMEFRAME hours ago untill now().  now() refers to current localtime.

* Run from starter.py


##Gotchas
* In order for hardwares to be migrated, hardware must have unique name.
* When there are multiple devices with the same name, device name is constructed as: "device_name" + "_" + "servicenow_sys_id"    i.e. :
    * "MacBook Air 13" will become 
    * "MacBook Air 13"_01a9280d3790200044e0bfc8bcbe5d79"


