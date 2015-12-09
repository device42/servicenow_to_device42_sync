#!/usr/bin/python

"""
README
This script reads CIs from Servicenow and uploads them to Device42.
It has 2 modes:
1. Full migration  - when the TIMEFRAME is set to 0
2. Synchronization - when the TIMEFRAME is set to anything else but 0


GOTCHAS
* In order for hardwares to be migrated, hardware must have unique name.


"""

import sys
import re
import json
import base64
import requests
import sqlite3 as sql
from datetime import datetime, timedelta

try:
    requests.packages.urllib3.disable_warnings()
except AttributeError:
    pass


__copyright__   = "Copyright 2015, Device42 LLC"
__version__     = "2.0.0"
__status__      = "Production"


# ===== Device42 ===== #
D42_USER    = 'admin'
D42_PWD     = 'adm!nd42'
D42_URL     = 'https://192.168.3.30'

# ===== ServiceNow ===== #
USERNAME    = 'admin'
PASSWORD    = 'P@ssw0rd'
BASE_URL    = 'https://dev13344.service-now.com/api/now/table/'
LIMIT       = 1000000 # number of CIs to retrieve from ServiceNow
HEADERS     = {"Content-Type":"application/json","Accept":"application/json"}
DEVICES     = ['cmdb_ci_server','cmdb_ci_app_server', 'cmdb_ci_database', 'cmdb_ci_email_server',
               'cmdb_ci_ftp_server', 'cmdb_ci_directory_server', 'cmdb_ci_ip_server', 'cmdb_ci_computer']

# ===== Other ===== #
DEBUG        = False    # print to STDOUT
DRY_RUN      = False    # Do not upload to Device42 (DRY_RUN=False)
ZONE_AS_ROOM = True     # for the explanation take a look at get_zones() docstring
TIMEFRAME    = 12       # Value represents hours. If set to 0, script does full migration, if set to any other value,
                        # script syncs changes from TIMESTAMP till now(). now() referes to current localtime.



class Rest():
    """
    All of the download/upload stuff goes here.
    """
    def __init__(self):
        self.base_url   = D42_URL
        self.username   = D42_USER
        self.password   = D42_PWD
        self.debug      = DEBUG


    def uploader(self, data, url):
        """
        Uploads data to Device42
        :param data: data to upload
        :param url: URl to upload data to
        :return:
        """
        payload = data
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(self.username + ':' + self.password),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        r = requests.post(url, data=payload, headers=headers, verify=False)
        msg =  unicode(payload)
        if self.debug:
            print '\t\t',msg
        msg = '\t\t[!]Status code: %s' % str(r.status_code)
        print msg
        msg = str(r.text)
        if self.debug:
            print '\t\t', msg

    def post_device(self, data):
        if DRY_RUN == False:
            url = self.base_url+'/api/device/'
            msg =  '\n\t[+] Posting data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_ip(self, data):
        if DRY_RUN == False:
            url = self.base_url+'/api/ip/'
            msg =  '\t[+] Posting IP data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_mac(self, data):
        if DRY_RUN == False:
            url = self.base_url+'/api/1.0/macs/'
            msg = '\t[+] Posting MAC data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_building(self, data):
        if DRY_RUN == False:
            url = self.base_url+'/api/1.0/buildings/'
            msg = '\t[+] Posting Building data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_room(self, data):
        if DRY_RUN == False:
            url = self.base_url+'/api/1.0/rooms/'
            msg = '\t[+] Posting Room data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_rack(self, data):
        if DRY_RUN == False:
            url = self.base_url+'/api/1.0/racks/'
            msg = '\t[+] Posting Rack data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_hardware(self, data):
        if DRY_RUN == False:
            url = self.base_url+'/api/1.0/hardwares/'
            msg = '\t[+] Posting Hardware data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def mount_to_rack(self, data,device):
        if DRY_RUN == False:
            url = self.base_url+'/api/1.0/device/rack/'
            msg = '\n\t[+] Mounting device "%s"to %s ' % (device, url)
            if self.debug:
                print msg
            self.uploader(data, url)

class ServiceNow():
    """
    All ServiceNow stuff goes here
    """
    def __init__(self):
        self.total      = 0
        self.names      = []
        self.rest       = Rest()
        self.location_map   = {}
        self.conn           = None
        self.datacenters    = {} # maps datacenter ID to datacenter name
        self.rooms          = {} # maps room ID to room name
        self.racks          = {} # maps rack ID to rack name

        if BASE_URL.endswith('/'):
            self.base_url = BASE_URL
        else:
            self.base_url = BASE_URL + '/'

    def connect(self):
        """
        Connect to an in-memory database
        :return:
        """
        self.conn = sql.connect(':memory:')


    def create_db(self):
        """
        Create database tables
        :return:
        """
        if not self.conn:
            self.connect()

        with self.conn:
            cur = self.conn.cursor()
            cur.execute("CREATE TABLE devices  (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "dev_sys_id TEXT UNIQUE,"
                        "dev_name TEXT)")

            cur.execute("CREATE TABLE adapters (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "nic_sys_id TEXT UNIQUE, "
                        "nic_mac TEXT,"
                        "nic_name TEXT,"
                        "dev_sys_id TEXT)")

            cur.execute("CREATE TABLE addresses(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "ip_address TEXT, "
                        "netmask TEXT, "
                        "nic_sys_id TEXT)")

            cur.execute("CREATE TABLE locations(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "loc_sys_id TEXT UNIQUE, "
                        "name TEXT, "
                        "country TEXT, "
                        "city TEXT, "
                        "street TEXT)")

            cur.execute("CREATE TABLE relationships(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "parent TEXT, "
                        "child TEXT)")

            cur.execute("CREATE TABLE manufacturers(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "name TEXT, "
                        "sys_id TEXT UNIQUE )")

            cur.execute("CREATE TABLE hardwares(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                        "name TEXT, "
                        "sys_id TEXT UNIQUE )")

    def strip_html(self, raw):
        """
        Some text has embedded html tags that we must remove
        :param raw: Text with HTML
        :return: Text without HTML
        """
        if raw:
            result = re.sub("<.*?>", "", raw)
        else:
            result = ''
        return result


    def query_db(self, query ,level=2):
        """
        Query database
        :param query: SQL query
        :param level: Database response slicing level
        :return: Data returned from the database
        """
        if not self.conn:
            self.connect()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute(query)
            raw = cur.fetchall()
            response = None
            if level==0:
                return raw
            elif level==1:
                try:
                    response = raw[0]
                except:
                    pass
            else:
                try:
                    response = raw[0][0]
                except:
                    pass
        return response

    def get_parent(self, sys_id):
        """
        Get parent sys_id
        :param sys_id: Child's sys_id
        :return: parent's sys_id
        """
        try:
            sql     = 'SELECT child FROM relationships WHERE parent="%s"' % sys_id
            parent  = self.query_db(sql)
        except:
            parent  = None
        return parent


    def get_timestamp(self):
        """
        Return time.now() - TIMEFRAME to be used in search filters during synchronization process
        :return: Timestamp
        """
        now = datetime.now()
        ts = now - timedelta(hours = int(TIMEFRAME))
        return ts


    def fetch_data(self, table):
        """
        Get the data from ServiceNow
        :param table: Table to query
        :return: Table data
        """
        if TIMEFRAME and table != 'cmdb_rel_ci':
            TIMESTAMP = self.get_timestamp()
            URL = self.base_url + table + '?sysparm_limit=%s&sysparm_query=sys_updated_on>%s' % (LIMIT, TIMESTAMP)
        else:
            URL = self.base_url + table + '?sysparm_limit=%s' % LIMIT

        response = requests.get(URL, auth=(USERNAME, PASSWORD), headers=HEADERS)
        if response.status_code == 200:
            response = response.json()
            try:
                return response['result']
            except:
                return None


    def value(self, data, word):
        """
        Check if key exists using try/except block. If it exists, return it's value.
        :param data: Data (CI's JSON)
        :param word: Key to check
        :return: Key's value
        """
        try:
            val = data['%s' % word]
            if val == '':
                val = None
            return val
        except Exception as e:
            return None


    def get_locations(self):
        """
        Get locations from ServiceNow and insert them into the database
        :return: 
        """
        table = 'cmn_location'
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
        if response:
            for data in response:
                #print json.dumps(data, indent=4, sort_keys=True)
                name        = data['name']
                country     = data['country']
                city        = data['city']
                street      = data['street']
                loc_sys_id  = data['sys_id']
                if not self.conn:
                    self.connect()
                with self.conn:
                    cur = self.conn.cursor()
                    cur.execute("INSERT INTO locations VALUES (?,?,?,?,?,?)",
                                (None, loc_sys_id,name,country,city,street))

    def get_relationships(self):
        """
        Get relationships from SN and insert them into the database
        :return: 
        """
        table = 'cmdb_rel_ci'
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)

        if response:
            for rec in response:
                child   = rec['child']['value']
                parent  = rec['parent']['value']

                if not self.conn:
                    self.connect()
                with self.conn:
                    cur = self.conn.cursor()
                    cur.execute('INSERT INTO relationships VALUES (?,?,?)',(None,parent,child))

    def get_manufacturers(self):
        """
        Get manufacturers from SN and insert them into the database
        :return: 
        """
        table = 'core_company'
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
        if response:
            for rec in response:
                #print json.dumps(data, indent=4, sort_keys=True)
                sys_id = self.value(rec, 'sys_id')
                name   = self.value(rec, 'name')
                if not self.conn:
                    self.connect()
                with self.conn:
                    cur = self.conn.cursor()
                    cur.execute("INSERT INTO manufacturers VALUES (?,?,?)", (None, name, sys_id))

    def get_hardware(self):
        """
        Get hardware from SN and upload it to the Device42
        :return:
        """
        table = 'cmdb_hardware_product_model'
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
        if response:
            for rec in response:
                #print json.dumps(rec, indent=4, sort_keys=True)
                hw_data     = {}
                name        = self.value(rec, 'name')
                sys_id      = self.value(rec, 'sys_id')
                size        = self.value(rec, 'rack_units')
                watts       = self.value(rec, 'power_consumption')
                desc        = self.value(rec,'description')
                description = self.strip_html(desc)
                man_id      = self.value(self.value(rec, 'manufacturer'),'value')
                if man_id:
                    sql = 'SELECT name FROM manufacturers WHERE sys_id="%s"' % man_id
                    manufacturer = self.query_db(sql)
                    hw_data.update({'manufacturer':manufacturer})
                hw_data.update({'name':name})
                hw_data.update({'watts':watts})
                hw_data.update({'notes':description})
                hw_data.update({'size':size})
                if not self.conn:
                    self.connect()
                with self.conn:
                    cur = self.conn.cursor()
                    cur.execute("INSERT INTO hardwares VALUES (?,?,?)", (None, name, sys_id))
                self.rest.post_hardware(hw_data)

    def get_buildings(self):
        """
        Get buildings from SN and upload them to the Device42
        :return:
        """
        table = 'cmdb_ci_datacenter'
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)

        if response:
            for rec in response:
                building_data   = {}
                data_sys_id     = rec['sys_id']
                name            = rec['name']
                loc_sys_id      = rec['location']['value']
                self.datacenters.update({data_sys_id:name})
                sql             = 'SELECT * FROM locations WHERE loc_sys_id="%s"' % loc_sys_id
                result          = self.query_db(sql,level=1)
                if result:
                    id, sys_id, locname, country, city, street = result
                    if not name:
                        name = country +'/'+ city +'/'+ street
                    address = country +'/'+ city +'/'+ street
                    building_data.update({'name':name})
                    building_data.update({'address':address})
                    self.rest.post_building(building_data)

    def get_rooms(self):
        """
        Get rooms from SN and upload them to the Device42
        :return:
        """
        table = 'cmdb_ci_computer_room'
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)

        if response:
            for rec in response:
                room_data   = {}
                name        = self.value(rec,'name')
                sys_id      = self.value(rec,'sys_id')
                parent      = self.get_parent(sys_id)
                building    = self.datacenters[parent]
                self.rooms.update({sys_id:name})
                room_data.update({'name':name})
                room_data.update({'building':building})
                self.rest.post_room(room_data)

    def get_zones(self):
        """
        Get zones from SN and upload them to the Device42
        In case ZONE_AS_ROOM=True, zones are uploaded as rooms to the parent building.

        1. ZONE_AS_ROOM = False:
         ----------      ------      ------
        | building | -> | room | -> | zone |
         ----------      ------      ------

         2. ZONE_AS_ROOM = True
         ----------                  ------
        | building | -------------> | zone |
         ----------        |         ------
                           |         ------
                            ------> | room |
                                     ------
        :return:
        """

        table = 'cmdb_ci_zone'
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        response   = self.fetch_data(table)
        #print json.dumps(response, indent=4, sort_keys=True)
        if response:
            for rec in response:
                room_data   = {}
                name        = self.value(rec,'name')
                sys_id      = self.value(rec,'sys_id')
                parent      = self.get_parent(sys_id)
                grandparent = self.get_parent(parent)
                building    = self.datacenters[grandparent]
                self.rooms.update({sys_id:name})
                room_data.update({'name':name})
                room_data.update({'building':building})
                self.rest.post_room(room_data)

    def get_racks(self):
        """
        Get racks from SN and upload them to the Device42
        :return:
        """

        table = 'cmdb_ci_rack'
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
        #print json.dumps(response, indent=4, sort_keys=True)
        if response:
            for rec in response:
                rack_data   = {}
                sys_id      = self.value(rec ,'sys_id')
                name        = self.value(rec ,'name')
                self.racks.update({sys_id:name})
                rack_size   = self.value(rec ,'rack_units')
                rack_data.update({'name':name})
                rack_data.update({'size':rack_size})

                try:
                    parent      = self.get_parent(sys_id)
                    if parent:
                        room= self.rooms[parent]
                        rack_data.update({'room':room})
                except:
                    pass
                self.rest.post_rack(rack_data)

    def get_computers(self, table):
        """
        Get computers from SN and upload them to the Device42
        :param table:
        :return:
        """
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
        if response:
            for data in response:
                #print json.dumps(data, indent=4, sort_keys=True)
                devData         = {}
                rack_data       = {}
                sys_id          = self.value(data, 'sys_id')
                name            = data['name']
                # we do not want duplicate names, right?
                if name in self.names:
                    name        = name + '_' + sys_id
                self.names.append(name)
                domain          = self.value(data, 'dns_domain')
                fqdn            = self.value(data, 'fqdn')
                serial_no       = self.value(data, 'serial_number')
                # asset might not have 'value' field - we must handle that
                try:
                    asset_no    = self.value(data, 'asset')['value']
                except:
                    asset_no    = None
                os              = self.value(data, 'os')
                os_ver          = self.value(data, 'os_version')
                cpu_count       = self.value(data, 'cpu_count')
                cpu_name        = self.value(data, 'cpu_name')
                cpu_speed       = self.value(data, 'cpu_speed')
                cpu_type        = self.value(data, 'cpu_type')
                cpu_core_count  = self.value(data, 'cpu_core_count')
                disk_space      = self.value(data, 'disk_space')
                ram             = self.value(data, 'ram')
                # is it virtual?
                virt            = self.value(data, 'virtual')
                if virt in ('true', 'True'):
                    dev_type    = 'virtual'
                else:
                    dev_type    = 'physical'

                devData.update({'name':name})
                rack_data.update({'device':name})
                if serial_no:
                    devData.update({'serial_no':serial_no})
                if os:
                    devData.update({'os':os})
                if os_ver:
                    devData.update({'osver':os_ver})
                if ram and '-' not in ram:
                    devData.update({'memory':ram})
                if cpu_count:
                    devData.update({'cpucount':cpu_count})
                if cpu_core_count:
                    devData.update({'cpu_core':cpu_core_count})
                if cpu_speed:
                    devData.update({'cpupower':cpu_speed})
                if asset_no:
                    devData.update({'asset_no':asset_no})
                devData.update({'type':dev_type})

                hw_id = self.value(self.value(data, 'model_id'),'value')
                if hw_id:
                    sql = 'SELECT name FROM hardwares WHERE sys_id="%s"' % hw_id
                    hw_model =  self.query_db(sql)
                    devData.update({'hw_model':hw_model})
                    rack_data.update({'hw_model':hw_model})

                # upload device data
                self.rest.post_device(devData)

                # add data to db - needed for IP upload
                if not self.conn:
                    self.connect()
                with self.conn:
                    cur = self.conn.cursor()
                    try:
                        cur.execute('INSERT INTO devices VALUES (?,?,?)',(None, sys_id, name))
                    except Exception, e:
                        pass


                # try to find out if the parent is rack, room or building (or any combination of them)
                rack_id = self.get_parent(sys_id)
                if rack_id and rack_id in self.racks:
                    # it's rack mounted!
                    rack_data.update({'start_at':'auto'}) # servicenow has no idea regarding where the device is mounted
                    rack_name = self.racks[rack_id]
                    rack_data.update({'rack':rack_name})

                    # there might be multiple racks with same name. We must find room & building as well
                    room_id = self.get_parent(rack_id)
                    if room_id and room_id in self.rooms:
                        room_name = self.rooms[room_id]
                        rack_data.update({'room':room_name})

                        building_id = self.get_parent(room_id)
                        if building_id and building_id in self.datacenters:
                            building_name = self.datacenters[building_id]
                            rack_data.update({'building':building_name})
                    self.rest.mount_to_rack(rack_data, name)

    def get_adapters(self):
        """
        Get adapters from SN and insert them into the database
        :return:
        """
        if DEBUG:
            print '\n[!] Fetching network adapters'
        table = 'cmdb_ci_network_adapter'
        URL = self.base_url + table
        response = requests.get(URL, auth=(USERNAME, PASSWORD), headers=HEADERS)
        all_nics = response.json()['result']
        for rec in all_nics:
            #print json.dumps(rec, indent=4, sort_keys=True)
            if 'value' in rec['cmdb_ci']:
                dev_sys_id  = rec['cmdb_ci']['value']
                nic_sys_id  = rec['sys_id']
                ip_address  = rec['ip_address']
                mac_address = rec['mac_address']
                nic_name    = rec['name']
                netmask     = rec['netmask']
                if not self.conn:
                    self.connect()
                with self.conn:
                    cur = self.conn.cursor()
                    cur.execute("INSERT INTO adapters VALUES (?,?,?,?,?)", (None, nic_sys_id, mac_address, nic_name, dev_sys_id))
                    cur.execute("INSERT INTO addresses VALUES (?,?,?,?)", (None, ip_address, netmask, nic_sys_id) )

    def get_ips(self):
        """
        Get IPs from SN and insert them into the database
        :return:
        """
        if DEBUG:
            print '\n[!] Fetching IP addresses'
        table = 'cmdb_ci_ip_address'
        URL = self.base_url + table
        response = requests.get(URL, auth=(USERNAME, PASSWORD), headers=HEADERS)
        for rec in response.json()['result']:
            nic_sys_id  = self.value(rec['nic'],'value')
            ipaddress   = self.value(rec, 'ip_address')
            netmask     = self.value(rec, 'netmask')

            if ipaddress:
                if not self.conn:
                    self.connect()
                with self.conn:
                    cur = self.conn.cursor()
                    cur.execute("INSERT INTO addresses VALUES (?,?,?,?)", (None, ipaddress, netmask, nic_sys_id) )

    def upload_adapters(self):
        """
        Get data from database, construct IP and MAC data and upload it to Device42
        :return:
        """
        if not self.conn:
            self.connect()
        with self.conn:
            cur = self.conn.cursor()

            cur.execute('SELECT dev_name, nic_name, ip_address, netmask, nic_mac FROM addresses '
                        'LEFT JOIN adapters ON adapters.nic_sys_id=addresses.nic_sys_id '
                        'LEFT JOIN devices ON devices.dev_sys_id=adapters.dev_sys_id '
                        'ORDER BY dev_name ASC')

            raw = cur.fetchall()
        for row in raw:
            ipdata  = {}
            macdata = {}
            device, label, ipaddress, netmask, macaddress = row
            ipdata.update({'device':device})
            ipdata.update({'label':label})
            ipdata.update({'ipaddress':ipaddress})
            ipdata.update({'macaddress':macaddress})

            macdata.update({'macaddress':macaddress})
            macdata.update({'device':device})

            self.rest.post_ip(ipdata)
            self.rest.post_mac(macdata)



if __name__ == '__main__':
    snow = ServiceNow()
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
    for table in DEVICES:
        snow.get_computers(table)
    snow.get_adapters()
    snow.get_ips()
    snow.upload_adapters()

    sys.exit()




