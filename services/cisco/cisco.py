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


# function to ensure that the dictionary has all the necessary fields
def check_values(dict_intent):
    if dict_intent['name'] == 'acl':
        parameters = ['from', 'to', 'rule', 'traffic', 'apply']
    elif dict_intent['name'] == 'nat11':
        parameters = ['from', 'to', 'for', 'protocol', 'apply']
    elif dict_intent['name'] == 'traffic_shaping':
        parameters = ['from', 'to', 'for', 'with', 'traffic', 'apply']
    else:
        return "CISCO MODULE: Intent type not supported"
    for parameter in parameters:
        if parameter not in dict_intent:
            return 'CISCO MODULE: ' + parameter + 'parameter is missing'
    return True


def process_acl(dict_intent):
    # loading YAML file with firewall settings
    config = yaml_load('cisco_config.yml')
    # identify interface
    for interface in config['INTERFACES']:
        if check_ip_network(dict_intent['from'], interface['addr']):
            dict_intent['from_interface'] = interface['name']
        elif check_ip_network(dict_intent['to'], interface['addr']):
            dict_intent['to_interface'] = interface['name']
    if 'from_interface' not in dict_intent and 'to_interface' not in dict_intent:
        return "CISCO MODULE: Unrecognized network"
    # translate allow/block
    if dict_intent['rule'] == 'allow':
        dict_intent['rule'] = 'permit'
    else:
        dict_intent['rule'] = 'deny'
    # translate protocol/port
    if dict_intent['traffic'] == 'any':
        dict_intent['traffic'] = 'ip'
    elif dict_intent['traffic'] == 'icmp':
        dict_intent['traffic'] = 'icmp'
    else:
        protocol, port = dict_intent['traffic'].split('/')
        dict_intent['traffic'] = protocol
        dict_intent['traffic_port'] = 'eq ' + port
    # identifies the use of ranges
    if 'from_mask' in dict_intent:
        dict_intent['from'] = dict_intent['from'] + ' ' + dict_intent['from_mask']
    else:
        dict_intent['from'] = 'host ' + dict_intent['from']
    if 'to_mask' in dict_intent:
        dict_intent['to'] = dict_intent['to'] + ' ' + dict_intent['to_mask']
    else:
        dict_intent['to'] = 'host ' + dict_intent['to']
    # other configs
    dict_intent['password'] = config['password']
    # loading and render template jinja2
    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('cisco_template.j2')
    output = template.render(dict_intent)
    #with ClusterRpcProxy(CONFIG) as rpc_connect:
        #rpc_connect.ssh_connector.apply_config(config['ip_manage'], config['ssh_port'], config['username'], config['password'], config['device_type'], output)
    return output


def process_nat11(dict_intent):
    # loading YAML file with firewall settings
    config = yaml_load('cisco_config.yml')
    # identifies interfaces
    for interface in config['INTERFACES']:
        if check_ip_network(dict_intent['from'], interface['addr']):
            dict_intent['from_interface'] = interface['name']
        elif check_ip_network(dict_intent['to'], interface['addr']):
            dict_intent['to_interface'] = interface['name']
        else:
            return 'CISCO MODULE: IP/Network not recognized'
    # loading and render template jinja2
    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('cisco_template.j2')
    output = template.render(dict_intent)
    # with ClusterRpcProxy(CONFIG) as rpc_connect:
    #    rpc_connect.ssh_connector.apply_config(config['ip_manage'], config['ssh_port'], config['username'],
    #                                           config['password'], config['device_type'], output)
    return output


def process_traffic_shaping(dict_intent):
    # loading YAML file with firewall settings
    config = yaml_load('cisco_config.yml')
    # converting throughput and rate
    dict_intent['with'] = dict_intent['with'] * 1000000
    dict_intent['rate'] = int(dict_intent['with'] * 0.0005)
    # name of policy
    dict_intent['policy'] = dict_intent['from'] + '-' + dict_intent['to']
    # range/host treatment
    if 'from_mask' in dict_intent:
        dict_intent['from'] = dict_intent['from'] + ' ' + dict_intent['from_mask']
    else:
        dict_intent['from'] = 'host ' + dict_intent['from']
    if 'to_mask' in dict_intent:
        dict_intent['to'] = dict_intent['to'] + ' ' + dict_intent['to_mask']
    else:
        dict_intent['to'] = 'host ' + dict_intent['to']
    # translate protocol/port
    if dict_intent['traffic'] == 'any':
        dict_intent['traffic'] = 'ip'
    elif dict_intent['traffic'] == 'icmp':
        dict_intent['traffic'] = 'icmp'
    else:
        protocol, port = dict_intent['traffic'].split('/')
        dict_intent['traffic'] = protocol
        dict_intent['traffic_port'] = 'eq ' + port
    # loading and render template jinja2
    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)
    template = env.get_template('cisco_template.j2')
    output = template.render(dict_intent)
    #with ClusterRpcProxy(CONFIG) as rpc_connect:
        #rpc_connect.ssh_connector.apply_config(config['ip_manage'], config['ssh_port'], config['username'],
        #                                       config['password'], config['device_type'], output)
    return output


class CiscoService:
    """
        Cisco Service
        Microservice that translates the information sent by the api to commands applicable in Cisco ASA
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
    name = "cisco_translator"
    zipcode_rpc = RpcProxy('cisco_service_translator')

    @rpc
    def translate_intent(self, dict_intent):
        if 'name' in dict_intent:
            output = check_values(dict_intent)
            if output is True:
                if dict_intent['name'] == 'acl':
                    output_service = process_acl(dict_intent)
                elif dict_intent['name'] == 'nat11':
                    output_service = process_nat11(dict_intent)
                elif dict_intent['name'] == 'traffic_shaping':
                    output_service = process_traffic_shaping(dict_intent)
                if output_service == 'ERROR':
                    return 'CISCO MODULE: Error when applying settings'
                else:
                    return output_service
            else:
                return 'CISCO MODULE: Error in dictionary'
        else:
            return 'CISCO MODULE: the key "name" is unavailable in the dictionary'
