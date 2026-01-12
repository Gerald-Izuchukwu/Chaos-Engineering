#!/bin/bash

#read env file
source ../.env 

#check active pool
if [ "$ACTIVE_POOL" == 'blue' ]; then
    export GREEN_ROLE="backup"
    export BLUE_ROLE=""
elif [ "$ACTIVE_POOL" == 'green' ] 
    export GREEN_ROLE=""
    export BLUE_ROLE="backup"
else
    echo "ACTIVE_POOL can either "BLUE or "GREEN"
fi;



#check NGINX Port
export NGINX_PORT=$NGINX_PORT

#create nginx.conf file
envsubst '${GREEN_ROLE} ${BLUE_ROLE} ${NGINX_PORT}' < nginx.conf.template > nginx.conf.main
echo "Generated nginx.conf with ACTIVE_POOL=$ACTIVE_POOL and NGINX_PORT=$NGINX_PORT"

#call docker-compose
docker compose -f ../docker-compose.yaml up