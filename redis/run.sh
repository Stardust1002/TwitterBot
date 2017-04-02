#!/bin/bash

echo "##### CONTAINER LAUNCHING.."
if ! docker start redis; then
echo "# CONTAINER NOT INSTALLED YET"
echo "# DOCKERFILE BUILDING.."
docker build -t bot/redis ./redis/
docker rmi redis
fi
if ! docker run --name redis -p 127.0.0.1:6379:6379 -d bot/redis; then
echo "# CONTAINER ALREADY RUNNING"
fi