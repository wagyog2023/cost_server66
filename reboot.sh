#!/usr/bin/env bash

echo -e "\033[34m--------------------wsgi process--------------------\033[0m"

ps -ef | grep nb_uwsgi.ini | grep -v grep

sleep 0.5

echo -e '\n--------------------going to close--------------------'

ps -ef | grep nb_uwsgi.ini | grep -v grep | awk '{print $2}' | xargs kill -9

sleep 0.5

echo -e '\n----------check if the kill action is correct----------'

# 注意修改以下这行
# 使用nohup和&来确保在后台运行并且终端关闭后仍然继续运行
nohup /envs/nb/bin/uwsgi --ini nb_uwsgi.ini >/dev/null 2>&1 &

echo -e '\n\033[42;1m----------------------started...----------------------\033[0m'

sleep 1

ps -ef | grep nb_uwsgi.ini | grep -v grep