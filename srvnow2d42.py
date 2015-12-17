

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





class Rest():
    """
    All of the download/upload stuff goes here.
    """
    def __init__(self, D42_URL, D42_USER, D42_PWD, DRY_RUN, DEBUG):
        self.base_url   = D42_URL
        self.username   = D42_USER
        self.password   = D42_PWD
        self.dry_run    = DRY_RUN
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
            print '\t\t%s' % msg
        msg = '\t\t[!] Status code: %s' % str(r.status_code)
        if self.debug:
            print '%s' % msg
        msg = str(r.text)
        if self.debug:
            print '\t\t%s'% msg

    def post_device(self, data):
        if self.dry_run == False:
            url = self.base_url+'/api/device/'
            msg =  '\n\t[+] Posting data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_ip(self, data):
        if self.dry_run == False:
            url = self.base_url+'/api/ip/'
            msg =  '\t[+] Posting IP data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_mac(self, data):
        if self.dry_run == False:
            url = self.base_url+'/api/1.0/macs/'
            msg = '\t[+] Posting MAC data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_building(self, data):
        if self.dry_run == False:
            url = self.base_url+'/api/1.0/buildings/'
            msg = '\t[+] Posting Building data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_room(self, data):
        if self.dry_run == False:
            url = self.base_url+'/api/1.0/rooms/'
            msg = '\t[+] Posting Room data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_rack(self, data):
        if self.dry_run == False:
            url = self.base_url+'/api/1.0/racks/'
            msg = '\t[+] Posting Rack data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def post_hardware(self, data):
        if self.dry_run == False:
            url = self.base_url+'/api/1.0/hardwares/'
            msg = '\t[+] Posting Hardware data to %s ' % url
            if self.debug:
                print msg
            self.uploader(data, url)

    def mount_to_rack(self, data,device):
        if self.dry_run == False:
            url = self.base_url+'/api/1.0/device/rack/'
            msg = '\n\t[+] Mounting device "%s"to %s ' % (device, url)
            if self.debug:
                print msg
            self.uploader(data, url)

class ServiceNow():
    """
    All ServiceNow stuff goes here
    """
    def __init__(self, D42_URL, D42_USER, D42_PWD, USERNAME, PASSWORD, BASE_URL, LIMIT,
                 HEADERS, DEBUG, DRY_RUN, ZONE_AS_ROOM, TIMEFRAME):
        self.total          = 0
        self.names          = []
        self.rest           = Rest(D42_URL, D42_USER, D42_PWD, DRY_RUN, DEBUG)
        self.username       = USERNAME
        self.password       = PASSWORD
        self.base_url       = BASE_URL
        self.limit          = LIMIT
        self.headers        = HEADERS
        self.debug          = DEBUG
        self.zone_as_room   = ZONE_AS_ROOM
        self.timeframe      = TIMEFRAME
        self.location_map   = {}
        self.conn           = None
        self.datacenters    = {} # maps datacenter ID to datacenter name
        self.rooms          = {} # maps room ID to room name
        self.racks          = {} # maps rack ID to rack name

        if self.base_url.endswith('/'):
            self.base_url   = self.base_url
        else:
            self.base_url   = self.base_url + '/'

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
        ts = now - timedelta(hours = int(self.timeframe))
        return ts


    def fetch_data(self, table):
        """
        Get the data from ServiceNow
        :param table: Table to query
        :return: Table data
        """
        if self.timeframe and table != 'cmdb_rel_ci':
            TIMESTAMP = self.get_timestamp()
            URL = self.base_url + table + '?sysparm_limit=%s&sysparm_query=sys_updated_on>%s' % (self.limit, TIMESTAMP)
        else:
            URL = self.base_url + table + '?sysparm_limit=%s' % self.limit
        response = requests.get(URL, auth=(self.username, self.password), headers=self.headers)
        if response.status_code == 200:
            response = response.json()
            try:
                return response['result']
            except:
                return None
        else:
            if self.debug:
                print '\t\t[!] Status code: %d' % response.status_code

    def fetch_single_ci(self, table, sys_id):
        """
        Get single Ci from SN
        :param table: table to query
        :param sys_id: sys id to search for
        :return: result or None
        """
        if table:
            tables = [table]
        else:
            tables = ['cmdb_ci_rack', 'cmdb_ci_computer_room', 'cmdb_ci_zone', 'cmdb_ci_datacenter']

        for table in tables:
            if sys_id:
                URL = self.base_url + table +'/' + sys_id
                response = requests.get(URL, auth=(self.username, self.password), headers=self.headers)
                if response.status_code == 200:
                    response = response.json()
                    try:
                        return response['result']
                    except:
                        pass
                else:
                    if self.debug:
                        print '\t\t[!] Status code: %d' % response.status_code


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
        if self.debug:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
        if response:
            for data in response:
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
        if self.debug:
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
        if self.debug:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
        if response:
            for rec in response:
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
        if self.debug:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
        if response:
            for rec in response:
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
        if self.debug:
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
        if self.debug:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)

        if response:
            for rec in response:
                room_data   = {}
                name        = self.value(rec,'name')
                sys_id      = self.value(rec,'sys_id')
                parent      = self.get_parent(sys_id)
                try:
                    building    = self.datacenters[parent]
                    self.rooms.update({sys_id:name})
                    room_data.update({'name':name})
                    room_data.update({'building':building})
                    self.rest.post_room(room_data)
                except KeyError:
                    pass


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
        if self.debug:
            print '\n[!] Processing table "%s"' % (table)
        response   = self.fetch_data(table)
        if response:
            for rec in response:
                room_data   = {}
                name        = self.value(rec,'name')
                sys_id      = self.value(rec,'sys_id')
                parent      = self.get_parent(sys_id)
                try:
                    grandparent = self.get_parent(parent)
                    building    = self.datacenters[grandparent]
                    self.rooms.update({sys_id:name})
                    room_data.update({'name':name})
                    room_data.update({'building':building})
                    self.rest.post_room(room_data)
                except KeyError:
                    pass

    def get_racks(self):
        """
        Get racks from SN and upload them to the Device42
        :return:
        """

        table = 'cmdb_ci_rack'
        if self.debug:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
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
        if self.debug:
            print '\n[!] Processing table "%s"' % (table)
        response = self.fetch_data(table)
        if response:
            for data in response:
                devData         = {}
                rack_data       = {}
                sys_id          = self.value(data, 'sys_id')
                name            = data['name']
                # we do not want duplicate names, right?
                if name in self.names:
                    name        = name + '_' + sys_id
                self.names.append(name)
                serial_no       = self.value(data, 'serial_number')
                # asset might not have 'value' field - we must handle that
                try:
                    asset_no    = self.value(data, 'asset')['value']
                except:
                    asset_no    = None
                os              = self.value(data, 'os')
                os_ver          = self.value(data, 'os_version')
                cpu_count       = self.value(data, 'cpu_count')
                cpu_speed       = self.value(data, 'cpu_speed')
                cpu_core_count  = self.value(data, 'cpu_core_count')
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
                hw_model = None
                if hw_id:
                    sql = 'SELECT name FROM hardwares WHERE sys_id="%s"' % hw_id
                    hw_model =  self.query_db(sql)
                    if hw_model:
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
                elif rack_id and not rack_id in self.racks:
                    self.walked_data = {}
                    # search for hardware model
                    table = 'cmdb_hardware_product_model'
                    walked_hw = self.fetch_single_ci(table,  hw_id)
                    if walked_hw:
                        name  = self.value(walked_hw, 'name')
                        if name:
                            self.walked_data.update({'hw_model':name})
                            # if we are synchronizing, it might happend that self.racks is not populated,
                            # so we might miss some important relations.
                            # We will try to get that info manually
                            self.walk_by_id(rack_id)
                            if self.walked_data:
                                rack_data.update(self.walked_data)
                                self.rest.mount_to_rack(rack_data, name)

    def walk_by_id(self, x_id):
        response = self.fetch_single_ci(None, x_id)
        if response:
            name  = self.value(response,'name')
            sys_id = self.value(response,'sys_id')
            subcategory = self.value(response, 'subcategory')
            if subcategory.lower() == 'rack':
                self.walked_data.update({'start_at':'auto'})
                self.walked_data.update({'rack':name})
            if subcategory.lower() == 'data center zone':
                if self.zone_as_room:
                    self.walked_data.update({'room':name})
            if subcategory.lower() == 'computer room':
                if not self.zone_as_room:
                    self.walked_data.update({'room':name})
            if subcategory.lower() == 'data center':
                self.walked_data.update({'building':name})

            parent_id = self.get_parent(sys_id)
            if parent_id:
                self.walk_by_id(parent_id)
            else:
                return self.walked_data

    def get_adapters(self):
        """
        Get adapters from SN and insert them into the database
        :return:
        """
        if self.debug:
            print '\n[!] Fetching network adapters'
        table = 'cmdb_ci_network_adapter'
        all_nics = self.fetch_data(table)
        if all_nics:
            for rec in all_nics:
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
        if self.debug:
            print '\n[!] Fetching IP addresses'
        table = 'cmdb_ci_ip_address'
        all_ips = self.fetch_data(table)
        if all_ips:
            for rec in all_ips:
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
            if ipaddress:
                self.rest.post_ip(ipdata)
            if macaddress:
                self.rest.post_mac(macdata)
