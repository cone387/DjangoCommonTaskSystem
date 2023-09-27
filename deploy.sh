#/bin/bash

OPTIONS_SHORT="t:p:s:u:i"
OPTIONS_LONG="to:,port:,setting:,user:,pwd:,init,gunicorn,help"

DEPLOY_TO="server";
PROJECT="django-common-task-system";
PORT=8000;
SETTING='';
SET_USER='';
SET_PASSWORD='';
INIT="false";

if ! ARGS=$(getopt -o $OPTIONS_SHORT --long $OPTIONS_LONG -n "$0" -- "$@"); then
  echo "Terminating..."
  echo -e "Usage: ./$SCRIPT_NAME [options]\n"
  exit 1
fi

eval set -- "${ARGS}"

while true;
do
    case $1 in
        -t|--to)
          echo "DEPLOY_TO: $2;"
          DEPLOY_TO=$2;
          shift 2
          ;;
        -p|--port)
          echo "PORT: $2;"
          PORT=$2;
          shift 2
          ;;
        -s|--setting)
          echo "setting.py: $2;"
          SETTING=$2;
          shift 2
          ;;
        -u|--user)
          echo "SET_USER: $2;"
          SET_USER=$2;
          shift 2
          ;;
        --pwd)
          echo "SET_PASSWORD: $2;"
          SET_PASSWORD=$2;
          shift 2
          ;;
        -i|--init)
          echo "INIT: true;"
          INIT="true";
          shift
          ;;
        --gunicorn)
          echo "USE_GUNICORN: true;"
          USE_GUNICORN="true";
          shift
          ;;
        --)
          break
          ;;
        ?)
          echo "there is unrecognized parameter."
          exit 1
          ;;
    esac
done


function deploy_to_pypi() {
  echo "Deploying to pypi..."
  rm -rf ./dist/*
  python setup.py sdist
  twine upload dist/*

}

function deploy_to_docker() {
  echo "Deploying to docker..."
  docker build -t django-common-task-system .
  docker tag django-common-task-system cone387/django-common-task-system:latest
  docker push cone387/django-common-task-system:latest
}


function deploy_to_server() {
  if [ "$SETTING" != "" ];
  then
    if [ ! -f "$SETTING" ];
    then
      echo "SETTING<$SETTING> does not exist"
      exit 1
    fi
    server_path="/etc/django-common-task-system/";
    if [ "$context" != "default" -a "$context" != "" ];
    then
      # docker context 为其它服务器, 先将配置文件拷贝到服务器上
      server=$(docker context inspect | grep -o 'Host.*' | sed 's/.*: "ssh:\/\/\(.*\)".*/\1/')
      echo "server is $server"
      if [ "$server" = "" ];
      then
        exit 1
      fi
      ssh server "mkdir -p $server_path"
      scp $SETTING $server:$server_path;
    else
      # docker context 为本地, 直接将配置文件拷贝到本地server_path
      echo "cp -f $SETTING $server_path"
      cp -f $SETTING $server_path
    fi
    VOLUME="-v $server_path:/home/django-common-task-system/configs"
    ENV="-e DJANGO_SETTINGS_MODULE=configs.$(basename $SETTING .py)";
  fi

  if [ "$INIT" == "true" ]
  then
    INIT_ENV="-e INIT=$INIT"
  else
    INIT_ENV=""
  fi
  if [ "$SET_USER" != "" -a "$SET_PASSWORD" != "" ]
  then
    SET_USER_ENV="-e SET_USER=$SET_USER"
    SET_PASSWORD_ENV="-e SET_PASSWORD=$SET_PASSWORD"
  elif [ "$SET_USER" != "" ];
  then
    echo "You must set password for user $SET_USER"
    exit 1
  else
    SET_USER_ENV=""
    SET_PASSWORD_ENV=""
  fi
  if [ "$USE_GUNICORN" == "true" ]
  then
    GUNICORN_ENV="-e USE_GUNICORN=$USE_GUNICORN"
  else
    GUNICORN_ENV=""
  fi
  echo "Deploying to server..."
  cid=`docker ps -a | grep $PROJECT | awk '{print $1}'`
  for c in $cid
    do
        docker stop $c
        docker rm $c
    done
  echo "docker build -t $PROJECT ."
  docker build -t $PROJECT .
  echo "docker run -d -v /etc/ -v /var/run/docker.sock:/var/run/docker.sock $VOLUME $INIT_ENV $SET_USER_ENV $SET_PASSWORD_ENV $GUNICORN_ENV $ENV  -p $PORT:8000 --log-opt max-size=100m --name django-common-task-system $PROJECT"
  docker run -d -v /etc/django-common-task-system/static/:/home/django-common-task-system/django_common_task_system_server/static/ -v /var/run/docker.sock:/var/run/docker.sock $VOLUME $INIT_ENV $SET_USER_ENV $SET_PASSWORD_ENV $GUNICORN_ENV $ENV  -p $PORT:8000 --log-opt max-size=100m --name django-common-task-system $PROJECT
}

if [ "$DEPLOY_TO" = 'pypi' ];
then
  deploy_to_pypi
elif [ "$DEPLOY_TO" = 'docker' ];
then
  deploy_to_docker
elif [ "$DEPLOY_TO" = 'server' ];
then
  deploy_to_server
else
  echo "Unknown deploy target: $DEPLOY_TO"
  exit 1
fi

echo "Done."