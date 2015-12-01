#!/usr/bin/python

import sys
import os
import json
import base64
import requests
import sqlite3 as sql

try:
    requests.packages.urllib3.disable_warnings()
except AttributeError:
    pass


__copyright__   = "Copyright 2015, Device42 LLC"
__version__     = "1.0.0"
__status__      = "Testing"


# ===== Device42 ===== #
D42_USER    = 'admin'
D42_PWD     = 'adm!nd42'
D42_URL     = 'https://192.168.3.30'

# ===== ServiceNow ===== #
USERNAME    = 'admin'
PASSWORD    = 'P@ssw0rd'
BASE_URL    = 'https://dev13344.service-now.com/api/now/table/'
LIMIT       = 1000000
HEADERS     = {"Content-Type":"application/json","Accept":"application/json"}
TABLES      = ['cmdb_ci_server']#['cmdb_ci_computer_room']#'cmn_location']#, 'cmdb_ci_server']#, 'cmdb_ci_computer'] # ]#''cmdb_ci_datacenter',

# ===== Other ===== #
DEBUG       = True
DRY_RUN     = False



class Rest():
    def __init__(self):
        self.base_url   = D42_URL
        self.username   = D42_USER
        self.password   = D42_PWD
        self.debug      = DEBUG


    def uploader(self, data, url):
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

class ServiceNow():
    def __init__(self):
        self.total      = 0
        self.names      = []
        self.rest       = Rest()
        self.location_map = {}
        self.conn = None


        if BASE_URL.endswith('/'):
            self.base_url = BASE_URL
        else:
            self.base_url = BASE_URL + '/'

    def connect(self):
        self.conn = sql.connect(':memory:')


    def create_db(self):
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


    def fetch_data(self, table):
        URL = self.base_url + table + '?sysparm_limit=%s' % LIMIT
        response = requests.get(URL, auth=(USERNAME, PASSWORD), headers=HEADERS)
        if response.status_code == 200:
            response = response.json()
            self.total = len(response['result'])
            if table == 'cmdb_ci_datacenter':
                self.process_datacenter_data(response['result'], table)
            elif table == 'cmn_location':
                self.process_buildings(response['result'], table)
            elif table == 'cmdb_ci_computer_room':
                self.process_buildings(response['result'], table)
            elif table in ['cmdb_ci_server', 'cmdb_ci_computer']:
                self.process_computer_data(response['result'], table)
            else:
                if DEBUG:
                    print '\n[!] Unknown table: %s \n' % table

    def value(self, data, word):
        try:
            val = data['%s' % word]
            #print '\nVAL: ', val
            if val == '':
                val = None
            return val
        except Exception as e:
            return None

    def process_datacenter_data(self, response, table):
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        i = 0
        for data in response:
            print '\n' + '-' * 80
            #print json.dumps(data, indent=4, sort_keys=True)

    def process_buildings(self, response, table):
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        i = 1
        for data in response:
            print '\n[%d of %d ]' % (i, self.total) + '-' * 80
            #print json.dumps(data, indent=4, sort_keys=True)
            location    = {}
            name        = self.value(data, 'name')
            sys_id      = self.value(data, 'sys_id')
            address     = self.value(data, 'street')
            phone       = self.value(data, 'phone')

            self.location_map.update({sys_id:name})
            location.update({'name':name})
            location.update({'address':address})
            location.update({'contact_phone':phone})

            self.rest.post_building(location)
            i+=1

    def process_rooms(self, response, table):
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        i = 1
        for data in response:
            print '\n[%d of %d ]' % (i, self.total) + '-' * 80
            print json.dumps(data, indent=4, sort_keys=True)

    def process_computer_data(self, response, table):
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)

        for data in response:
            #print '\n' + '-' * 80
            #print json.dumps(data, indent=4, sort_keys=True)
            devData         = {}
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

            # upload device data
            self.rest.post_device(devData)

            # add data to db - neede for IP upload
            if not self.conn:
                self.connect()
            with self.conn:
                cur = self.conn.cursor()

                cur.execute('INSERT INTO devices VALUES (?,?,?)',(None, sys_id, name))


    def get_adapters(self):
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
        #print '\nRESULT: ' + '-' * 80
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




    """
    def print_ips(self):
        print '\n' + '-' * 80

        if not self.conn:
            self.connect()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM addresses")
            raw = cur.fetchall()
            print [description[0] for description in cur.description]
        for x in raw:
            print x

    def print_devices(self):
        print '\n' + '-' * 80
        if not self.conn:
            self.connect()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute('SELECT * from devices')
            raw = cur.fetchall()
            print [description[0] for description in cur.description]
        for x in raw:
            print x

    def print_adapters(self):
        print '\n' + '-' * 80
        if not self.conn:
            self.connect()
        with self.conn:
            cur = self.conn.cursor()
            cur.execute('SELECT * from adapters')
            raw = cur.fetchall()
            print [description[0] for description in cur.description]
        for x in raw:
            print x
    """


if __name__ == '__main__':
    snow = ServiceNow()
    snow.create_db()

    for table in TABLES:
        snow.fetch_data(table)
    snow.get_adapters()
    snow.get_ips()

    snow.upload_adapters()



    sys.exit()




