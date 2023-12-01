#!/usr/bin/env bash

set -e

#export PYTHONPATH=$(pwd)
#echo "PYTHONPATH is $PYTHONPATH"

function migrate() {
  echo "Migrating..."
  python manage.py makemigrations
  python manage.py migrate
}

function start() {
  if [ "$USE_GUNICORN" == "true" ]
  then
    echo "Starting with gunicorn..."
    gunicorn -c gunicorn_config.py server.wsgi:application --preload
  else
    echo "Starting with django..."
    python manage.py runserver 0.0.0.0:8000
  fi
}

function start_engine(){
  python manage.py start_engine &
  echo "engine started"
}


function main() {
  cd django_common_task_system_server
  echo "INIT is $INIT"
  echo "SET_USER is $SET_USER"
  export RUN_MAIN="false"
  if [ "$INIT" == "true" ]
  then
      migrate
  fi
  if [ "$SET_USER" != "" -a "$SET_PASSWORD" != "" ]
  then
      python manage.py init -u $SET_USER -p $SET_PASSWORD --createsuperuser
  elif [ "$SET_USER" != "" -a "$SET_PASSWORD" == "" ];
  then
      echo "You must set password for user $SET_USER"
      exit 1
  fi
  python manage.py collectstatic --noinput
  export RUN_MAIN="true"

  if [ "$USE_GUNICORN" == "true" ]
  then
    echo "Set environment for gunicorn..."
    export DJANGO_SERVER_ADDRESS=http://127.0.0.1:8000
  fi
  start_engine
  start
}

main