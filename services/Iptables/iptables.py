
import re
from jinja2 import Environment, FileSystemLoader
from netaddr import IPAddress, IPNetwork
from yamlreader import yaml_load
from nameko.rpc import rpc, RpcProxy
from nameko.standalone.rpc import ClusterRpcProxy


CONFIG = {'AMQP_URI': "amqp://guest:guest@localhost:5672"}


def check_ip_network(ip, network):
    if IPAddress(ip) in IPNetwork(network):
        return True
    else:
        return False


def check_values(dict_intent):
    if dict_intent['name'] == 'acl':
        parameters = ['from', 'to', 'rule', 'traffic', 'apply']
    elif dict_intent['name'] == 'nat11':
        parameters = ['from', 'to', 'for', 'protocol', 'apply']
    elif dict_intent['name'] == 'traffic_shaping':
        parameters = ['from', 'to', 'for', 'with', 'traffic', 'apply']
    else:
        return "IPTABLES MODULE: Intent type not supported"
    for parameter in parameters:
        if parameter not in dict_intent:
            return 'IPTABLES MODULE: ' + parameter + 'parameter is missing'
    return True


def process_acl(dict_intent):
    # loading YAML with iptables settings
    config = yaml_load('iptables_config.yml')

    # identifies chain
    for interface in config['INTERFACES']:
        if dict_intent['from'] == re.search(r'(.*)/', str(interface['addr'])).group(1):
            dict_intent['chain'] = 'OUTPUT'
        elif dict_intent['to'] == re.search(r'(.*)/', str(interface['addr'])).group(1):
            dict_intent['chain'] = 'INPUT'
        else:
            dict_intent['chain'] = 'FORWARD'
    # translate allow/block
    if dict_intent['rule'] == 'allow':
        dict_intent['rule'] = 'ACCEPT'
    else:
        dict_intent['rule'] = 'DROP'
    # translate protocol/port
    if dict_intent['traffic'] == 'any':
        dict_intent['traffic'] = 'all'
    elif dict_intent['traffic'] == 'icmp':
        dict_intent['traffic'] = 'icmp'
    else:
        dict_intent['traffic'], dict_intent['traffic_port'] = dict_intent['traffic'].split('/')
        dict_intent['traffic_port'] = '--dport ' + dict_intent['traffic_port']
    if 'from_mask' in dict_intent:
        dict_intent['from'] = dict_intent['from'] + '/' + dict_intent['from_mask']
    if 'to_mask' in dict_intent:
        dict_intent['to'] = dict_intent['to'] + '/' + dict_intent['to_mask']
    print(dict_intent)
    # other configs
    dict_intent['password'] = config['password']
    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('iptables_template.j2')
    output = template.render(dict_intent)
    with ClusterRpcProxy(CONFIG) as rpc_connect:
        rpc_connect.ssh_connector.apply_config(config['ip_manage'], config['ssh_port'], config['username'], config['password'],
                                               config['device_type'], output)
    return output


def process_nat11(dict_intent):
    config = yaml_load('iptables_config.yml')
    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('iptables_template.j2')
    output = template.render(dict_intent)
    with ClusterRpcProxy(CONFIG) as rpc_connect:
        rpc_connect.ssh_connector.apply_config(config['ip_manage'], config['ssh_port'], config['username'],
                                               config['password'], config['device_type'], output)
    return output


def process_traffic_shaping(dict_intent):
    return 'IPTABLES MODULE: Traffic shaping is not yet supported'


class IptablesService:
    """
        IPTABLES Service
        Microservice that translates the information sent by the api to commands applicable in IPTABLES
        Receive: this function receives a python dictionary, with at least the following information for each processing
            For acl process:
                - from: ip or network of traffic origin
                - to: ip or network of traffic destination
                - rule: permit or allow traffic
                - traffic: protocol, or protocol + port of traffic
            For nat11 process:
                - from: public ip used in nat
                - to: private ip used in nat
                - for: type of traffic or port redirect
                - protocol: protocol of ports used
            For traffic_shaping process:
                - from: ip or network of traffic origin
                - to: ip or network of traffic destination
                - for: type of traffic treated traffic shaping
                - with: bandwidth in Mbps
                - traffic: port and protocol
        Return:
            - The microservice activates the application module via ssh and returns the result. If any incorrect
            information in the dictionary, the error message is returned
        """
    name = "iptables_translator"
    zipcode_rpc = RpcProxy('iptables_service_translator')

    @rpc
    def intent_to_iptables(self, dict_intent):
        if 'name' in dict_intent:
            output = check_values(dict_intent)
            if output is True:
                if dict_intent['name'] == 'acl':
                    return process_acl(dict_intent)
                elif dict_intent['name'] == 'nat11':
                    return process_nat11(dict_intent)
                elif dict_intent['name'] == 'traffic_shaping':
                    return process_traffic_shaping(dict_intent)
            else:
                return output
        else:
            return 'IPTABLES MODULE: the key "name" is unavailable in the dictionary'


