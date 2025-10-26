python \
  truthsocial_scraper.py \
  --limit 1 \
  --lark-webhook https://open.larksuite.com/open-apis/bot/v2/hook/e1803d73-77fc-49a9-a392-5648e601cf88 \
  --state-file truthsocial_last_id.json \
  >> truthsocial.log 2>&1


*/5 * * * * /usr/bin/env python truthsocial_scraper.py --limit 1 --lark-webhook https://open.larksuite.com/open-apis/bot/v2/hook/e1803d73-77fc-49a9-a392-5648e601cf88 --state-file truthsocial_last_id.json >> /Users/jan/Documents/7788/soical-sraper/truthsocial.log 2>&1
