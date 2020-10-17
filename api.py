from flask import Flask, request
import re
import socket
import struct
#import os
from nameko.standalone.rpc import ClusterRpcProxy
#from nameko import exceptions


CONFIG = {'AMQP_URI': "amqp://guest:guest@localhost:5672"}
intent_archive = "intent.txt"
app = Flask(__name__)


def cidr_to_netmask(cidr):
    network, net_bits = cidr.split('/')
    hots_bits = 32 - int(net_bits)
    netmask = socket.inet_ntoa(struct.pack('!I', (1 << 32) - (1 << hots_bits)))
    return network, netmask


def get_line(word):
    with open(intent_archive) as archive:
        for line_num, l in enumerate(archive, 0):
            if word in l:
                return line_num
        return False


def is_valid_ip (ip):
    m = re.match(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$", ip)
    return bool(m) and all(map(lambda n: 0 <= int(n) <= 255, m.groups()))


def search_in_arq(value, path):
    result = None
    for line in open(path):
        if value in line:
            _, result = line.split()
    if result is None:
        return False
    else:
        return result


def identify_value(tag, value):
    tag_status_ok = False
    if tag == 'from' or tag == 'to':
        if is_valid_ip(value) or value == 'any':
            tag_status_ok = True
        if not tag_status_ok:
            result = search_in_arq(value, 'conf/hosts_protocols.conf')
            if is_valid_ip(result):
                value = result
                tag_status_ok = True
        # if not tag_status_ok:
        #    print('function DNS')
    elif tag == 'rule' or tag == 'for':
        if not tag_status_ok:
            value = search_in_arq(value, 'conf/hosts_protocols.conf')
            tag_status_ok = True
    if tag_status_ok:
        return value
    else:
        return False


def process_intent_acl(dict_intent, intent_type):
    parameters = ['from', 'to', 'rule', 'apply']
    flag = 0
    text_return = 'Missing parameter for intent type ' + intent_type.upper() + ':'
    for parameter in parameters:
        # check if all parameters are available
        if parameter in dict_intent:
            if parameter == 'from' or parameter == 'to':
                if "endpoint('" in dict_intent[parameter] and "')" in dict_intent[parameter]:
                    value = re.search(r"'(.*)'", dict_intent[parameter]).group(1)
                    dict_intent[parameter] = value
                    result = identify_value(parameter, dict_intent[parameter])
                    if not result:
                        return 'Not possible translate parameter "' + parameter + ': ' + dict_intent[parameter] + '"'
                    else:
                        dict_intent[parameter] = result
                elif "range('" in dict_intent[parameter] and "')" in dict_intent[parameter]:
                    value = re.search(r"'(.*)'", dict_intent[parameter]).group(1)
                    range, netmask = cidr_to_netmask(value)
                    dict_intent[parameter] = range
                    dict_intent[parameter+'_mask'] = netmask
                else:
                    return 'Syntax error in parameter: '+parameter
            elif parameter == 'rule':
                value = re.search(r"'(.*)'", dict_intent[parameter]).group(1)
                if "block('" in dict_intent[parameter] and "')" in dict_intent[parameter]:
                    dict_intent[parameter] = 'block'
                elif "allow('" in dict_intent[parameter] and "')" in dict_intent[parameter]:
                    dict_intent[parameter] = 'allow'
                else:
                    return 'Syntax error in parameter: "' +parameter+'". Use "allow" or "block."'
                result = identify_value(parameter, value)
                if result is False:
                    return 'Not possible to translate the value into the parameter ' + parameter.upper() + ': "' + value + '"'
                else:
                    dict_intent['traffic'] = result
            elif parameter == 'apply':
                if dict_intent['apply'] != 'insert' and dict_intent['apply'] != 'remove':
                    return 'In parameter "apply" use "insert" or "remove"'
        else:
            flag = 1
            text_return += ' ' + parameter + ','
    # print(dict_intent)
    if flag == 0:
        return send_to_translate(dict_intent)
    else:
        return text_return


def process_intent_nat11(dict_intent, intent_type):
    parameters = ['from', 'to', 'for', 'apply']
    flag = 0
    text_return = 'Missing parameter for intent type ' + intent_type.upper() + ':'
    for parameter in parameters:
        # check if all parameters are available
        if parameter in dict_intent:
            if parameter == 'from' or parameter == 'to':
                if "endpoint('" in dict_intent[parameter] and "')" in dict_intent[parameter]:
                    value = re.search(r"'(.*)'", dict_intent[parameter]).group(1)
                    if '-' in value:
                        value, port = value.split('-')
                        if is_valid_ip(value):
                            dict_intent[parameter] = value
                        else:
                            result = identify_value(parameter, dict_intent[parameter])
                            if not result:
                                return 'Not possible translate parameter "' + parameter + ': ' + dict_intent[
                                    parameter] + '"'
                            else:
                                dict_intent[parameter] = result
                        dict_intent[parameter+'_port'] = port
                    else:
                        if is_valid_ip(value):
                            dict_intent[parameter] = value
                        else:
                            result = identify_value(parameter, dict_intent[parameter])
                            if not result:
                                return 'Not possible translate parameter "' + parameter + ': ' + dict_intent[
                                    parameter] + '"'
                            else:
                                dict_intent[parameter] = result
                else:
                    return 'Syntax error in parameter: '+parameter
            elif parameter == 'for':
                if "traffic('" in dict_intent[parameter] and "')" in dict_intent[parameter]:
                    value = re.search(r"'(.*)'", dict_intent[parameter]).group(1)
                    dict_intent['protocol'] = value
                else:
                    return 'Syntax error in parameter: ' + parameter
        else:
            flag = 1
            text_return += ' ' + parameter + ','
    # print(dict_intent)
    if flag == 0:
        return send_to_translate(dict_intent)
    else:
        return text_return


def process_intent_traffic_shaping(dict_intent, intent_type):
    parameters = ['from', 'to', 'for', 'with', 'apply']
    flag = 0
    text_return = 'Missing parameter for intent type ' + intent_type.upper() + ':'
    for parameter in parameters:
        # check if all parameters are available
        if parameter in dict_intent:
            if parameter == 'from' or parameter == 'to':
                if "endpoint('" in dict_intent[parameter] and "')" in dict_intent[parameter]:
                    value = re.search(r"'(.*)'", dict_intent[parameter]).group(1)
                    dict_intent[parameter] = value
                    result = identify_value(parameter, dict_intent[parameter])
                    if not result:
                        return 'Not possible translate parameter "' + parameter + ': ' + dict_intent[parameter] + '"'
                    else:
                        dict_intent[parameter] = result
                elif "range('" in dict_intent[parameter] and "')" in dict_intent[parameter] and "/" in dict_intent[parameter]:
                    value = re.search(r"'(.*)'", dict_intent[parameter]).group(1)
                    range, netmask = cidr_to_netmask(value)
                    dict_intent[parameter] = range
                    dict_intent[parameter + '_mask'] = netmask
                else:
                    return 'Syntax error in parameter: ' + parameter
            elif parameter == 'for':
                if "traffic('" in dict_intent[parameter] and "')" in dict_intent[parameter]:
                    value = re.search(r"'(.*)'", dict_intent[parameter]).group(1)
                else:
                    return 'Syntax error in parameter: ' + parameter
                result = identify_value(parameter, value)
                if not result:
                    return 'Not possible to translate the value into the parameter ' + parameter.upper() + ': "' + value + '"'
                else:
                    dict_intent['traffic'] = result
            elif parameter == 'with':
                if "throughput('" in dict_intent[parameter] and "')" in dict_intent[parameter]:
                    value = re.search(r"'(.*)'", dict_intent[parameter]).group(1)
                    if 'mbps' in value.lower():
                        dict_intent[parameter] = int(re.search(r'\d+', value).group())
                    else:
                        return 'Use "Mbps" in throughout'
                else:
                    return 'Syntax error in parameter: "'+parameter
        else:
            flag = 1
            text_return += ' ' + parameter + ','
    # print(dict_intent)
    if flag == 0:
        return send_to_translate(dict_intent)
    else:
        return text_return


def send_to_translate(dict_intent):
    result = "\n"
    flag = 0
    with open("conf/services_enable.conf", 'r') as archive:
        for line in archive:
            if line[0:1] != "#" and line[0:1] != " " and line[0:1] != "\n":
                flag = 1
                try:
                    name, function = line.split()
                except ValueError:
                    return "ERROR: Check the file 'services_enable.conf'"
                result = result + "\n --> Applied Commands in " + name + " firewall\n\n"
                with ClusterRpcProxy(CONFIG) as rpc:
                    command = "rpc." + function + "(dict_intent)"
                    result = result + eval(command) + "\n"
    if flag == 1:
        return result
    else:
        return "ERROR: Check the file 'services_enable.conf'"


def process_intent(intent):
    try:
        intent_type = re.search(r'define intent (.*):', str(intent)).group(1)
    except AttributeError:
        return "Syntax error in Intent"
    with open(intent_archive, 'w+b') as archive:
        archive.write(intent)
    archive = open(intent_archive, 'r')
    tmp_intent = archive.readlines()[get_line('define intent'):]
    final_intent = {}
    final_intent['name'] = intent_type.lower()
    for line in tmp_intent[1:]:
        try:
            key, value = line.split()
            key = key.lower()
            final_intent[key] = value.lower()
        except ValueError:
            return 'Incomplete intent for type "'+intent_type.upper()+'", see /help'
    # print(final_intent)
    if intent_type == 'acl':
        return process_intent_acl(final_intent, intent_type)
    elif intent_type == 'nat11':
        return process_intent_nat11(final_intent, intent_type)
    elif intent_type == 'traffic_shaping':
        return process_intent_traffic_shaping(final_intent, intent_type)
    else:
        return "Unrecognized intent type, see /help"


@app.route('/', methods=['POST'])
def receive_intent():
    request.get_data()
    response = process_intent(request.data)
    return response+"\n", 200


if __name__ == '__main__':
    app.run()


