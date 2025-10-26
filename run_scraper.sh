#!/bin/bash
export PATH=/Users/jan/Documents/7788/soical-sraper/venv/bin:/usr/local/bin:/usr/bin
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890

/Users/jan/Documents/7788/soical-sraper/venv/bin/python \
  /Users/jan/Documents/7788/soical-sraper/truthsocial_scraper.py \
  --limit 1 \
  --lark-webhook https://open.larksuite.com/open-apis/bot/v2/hook/e1803d73-77fc-49a9-a392-5648e601cf88 \
  --state-file /Users/jan/Documents/7788/soical-sraper/tem/truthsocial_last_id.json \
  >> /Users/jan/Documents/7788/soical-sraper/truthsocial.log 2>&1
