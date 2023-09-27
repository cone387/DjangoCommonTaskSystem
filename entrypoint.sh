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
    gunicorn server.wsgi:application --bind 0.0.0.0:8000
  else
    echo "Starting with django..."
    python manage.py runserver 0.0.0.0:8000
  fi
}

function main() {
  cd django_common_task_system_server
  echo "INIT is $INIT"
  echo "SET_USER is $SET_USER"
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
  start
}

main