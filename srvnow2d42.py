#!/usr/bin/python

import sys
import json
import base64
import requests

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
TABLES      = ['cmdb_ci_server', 'cmdb_ci_computer']
HEADERS     = {"Content-Type":"application/json","Accept":"application/json"}

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


class ServiceNow():
    def __init__(self):
        self.total      = 0
        self.names      = []
        self.rest       = Rest()
        self.ids        = []
        self.all_nics   = None
        self.nic_map    = {}

        if BASE_URL.endswith('/'):
            self.base_url = BASE_URL
        else:
            self.base_url = BASE_URL + '/'

    def fetch_data(self, table):
        URL = self.base_url + table + '?sysparm_limit=%s' % LIMIT
        response = requests.get(URL, auth=(USERNAME, PASSWORD), headers=HEADERS)
        if response.status_code == 200:
            response = response.json()
            self.total = len(response['result'])
            self.process_data(response['result'], table)


    def value(self, data, word):
        try:
            val = data['%s' % word]
            #print '\nVAL: ', val
            if val == '':
                val = None
            return val
        except Exception as e:
            return None


    def process_data(self, response, table):
        if DEBUG:
            print '\n[!] Processing table "%s"' % (table)
        i = 0
        for data in response:
            print '\n' + '-' * 80
            #print json.dumps(data, indent=4, sort_keys=True)
            mac_address = None
            ip_address  = None
            nic_name    = None
            macData     = {}
            nicData     = {}
            devData     = {}
            macs        = []
            ips         = []

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
                dev_type     = 'virtual'
            else:
                dev_type     = 'physical'

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

            for k,v in self.nic_map.items():
                if v == sys_id:
                    nic_sys_id = k
                    mac_address, ip_address, nic_name = self.get_ip_data(nic_sys_id)
                    if mac_address:
                        macs.append(mac_address)
                        macData.update({'device':name})
                        if nic_name:
                            macData.update({'port_name':nic_name})
                        macData.update({'macaddress':mac_address})
                        # upload mac address
                        if macData:
                            self.rest.post_mac(macData)

                    if ip_address:
                        ips.append(ip_address)
                        nicData.update({'device':name})
                        if nic_name:
                            nicData.update({'tag':nic_name})
                        if mac_address:
                            nicData.update({'macaddress':mac_address})
                        nicData.update({'ipaddress':ip_address})
                        # upload nic data
                        if nicData:
                            self.rest.post_ip(nicData)

            if DEBUG:
                print '\n%d devices left in table "%s"' % (self.total-i, table)
                print '\n[!] Name: %s' % name
                print '\tSys ID: %s' % sys_id
                print '\tDomain: %s' % domain
                print '\tFQDN: %s' % fqdn
                print '\tSerial #: %s' % serial_no
                print '\tAsset #: %s' % asset_no
                print '\tOS: %s' % os
                print '\tOS ver: %s' % os_ver
                print '\tCPU count: %s' % cpu_count
                print '\tCPU name: %s' % cpu_name
                print '\tCPU Speed: %s MHz' % cpu_speed
                print '\tCPU type: %s' % cpu_type
                print '\tCPU core count: %s' % cpu_core_count
                print '\tHDD size: %s Gb' % disk_space
                print '\tRAM size: %s Mb' % ram
                print '\tDevice type: %s' % dev_type
                print '\tIP Address[es]: %s' % ', '.join(ips)
                print '\tMAC address[es]: %s' % ', '.join(macs)

            i+=1

    def get_ip_data(self, nic_sys_id):
        for nic in self.all_nics:
            if nic['sys_id'] == nic_sys_id:
                #print json.dumps(raw,indent=4, sort_keys=True)
                mac_address = self.value(nic ,'mac_address')
                ip_address = self.value(nic, 'ip_address')
                nic_name = self.value(nic, 'name')
                return (mac_address, ip_address, nic_name)


    def get_adapters(self):
        if DEBUG:
            print '\n[!] Fetching network adapters'
        table = 'cmdb_ci_network_adapter'
        URL = self.base_url + table
        response = requests.get(URL, auth=(USERNAME, PASSWORD), headers=HEADERS)
        self.all_nics = response.json()['result']
        for rec in self.all_nics:
            #print json.dumps(rec, indent=4, sort_keys=True)
            if 'value' in rec['cmdb_ci']:
                computer_sys_id = rec['cmdb_ci']['value']
                nic_sys_id = rec['sys_id']
                self.nic_map.update({nic_sys_id:computer_sys_id})



    def get_ips(self):
        if DEBUG:
            print '\n[!] Fetching IP addresses'
        table = 'cmdb_ci_ip_address'
        URL = self.base_url + table
        response = requests.get(URL, auth=(USERNAME, PASSWORD), headers=HEADERS)

        for rec in response.json()['result']:
            ipData      = {}
            ipaddress   = self.value(rec, 'ip_address')
            macaddress  = self.value(rec, 'mac_address')
            netmask     = self.value(rec, 'netmask')
            if ipaddress:
                ipData.update({'ipaddress':ipaddress})
                if netmask:
                    ipData.update({'netmask':netmask})
                if macaddress:
                    ipData.update({'macaddress':macaddress})
                # upload ip address
                self.rest.post_ip(ipData)
                #print json.dumps(rec, indent=4, sort_keys=True)







if __name__ == '__main__':
    snow = ServiceNow()
    snow.get_ips()
    snow.get_adapters()
    for table in TABLES:
        snow.fetch_data(table)


    sys.exit()




