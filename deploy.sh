#/bin/bash

OPTIONS_SHORT="t:p:"
OPTIONS_LONG="to:port:,help"

DEPLOY_TO="pypi";
PROJECT="django-common-task-system";
PORT=8000;

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
  echo "Deploying to server..."
  cid=`docker ps -a | grep $PROJECT | awk '{print $1}'`
  for c in $cid
    do
        docker stop $c
        docker rm $c
    done
  docker build -t $PROJECT .
  docker run -d --name $PROJECT -p $PORT:8000 django-common-task-system
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