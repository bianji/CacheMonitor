#coding: utf-8
# the format of every redis_server in  REDIS_SERVER should like this: "myip:redisport" or "anotherip:redisport:mypassword"
SERVER_LIST = {
                'REDIS_SERVER' :["10.37.253.38:6380","10.37.253.38:6378"],
                'MEMCACHE_SERVER':["10.37.253.38:11211","10.37.253.74:11211"]
              }
# interval which you monitor the redis info.
INFO_INTERVAL = 2.0
# in the index, the table is set to show 10 rows redis data by default. you can change it.
TABLE_MAX_ROWS = 10
# flaks debug mode
DEBUG = False
SECRET_KEY = 'temporary_secret_key'

