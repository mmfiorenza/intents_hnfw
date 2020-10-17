#!/bin/bash

####
# This script runs microservices and python api
# 
# Author: Maurício Fiorenza
# Last modification: 04-10-2020
####

source ../bin/activate

cd services/cisco/
nameko run cisco --broker amqp://guest:guest@localhost &

cd ../../services/iptables/
nameko run iptables --broker amqp://guest:guest@localhost &

cd ../../connectors/
nameko run ssh_connector --broker amqp://guest:guest@localhost &

#python api.py

echo "To send intents see README.MD"
