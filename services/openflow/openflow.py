
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



class OpenflowService:
    """
        Openflow Service
        Microservice that translates the information sent by the api to commands applicable in Openflow devices
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
    name = "openflow_translator"
    zipcode_rpc = RpcProxy('openflow_service_translator')

    @rpc
    def translate_intent(self, dict_intent):
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
            return 'OPENFLOW MODULE: the key "name" is unavailable in the dictionary'

