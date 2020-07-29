#!/bin/bash

####
# This script runs microservices and python api
# 
# Author: Maurício Fiorenza
# Last modification: 16-06-2020
####

cd ~/PycharmProjects/intent_translator/services/Cisco/
nameko run cisco --broker amqp://guest:guest@localhost &

cd ~/PycharmProjects/intent_translator/services/Iptables/
nameko run iptables --broker amqp://guest:guest@localhost &

cd ~/PycharmProjects/intent_translator/connectors/
nameko run ssh_connector --broker amqp://guest:guest@localhost &

#python3.7 ~/PycharmProjects/intent_translator/api.py &

echo "To send intents see README.MD"
