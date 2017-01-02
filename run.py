#!/usr/bin/env python
#encoding:utf-8
__author__ = 'bianji'
import threading
import redis
import datetime
import time
import signal
import sys
import memcache
from flask import Flask,render_template,request
from flask.ext.socketio import SocketIO,emit
from gevent import monkey
from config import *
monkey.patch_all()
app = Flask(__name__)
app.config['SECRET_KEY'] = 'redis monitor example'
socketio = SocketIO(app)

TABLE_MAX_ROWS = 10
INFO_INTERVAL = 2
all_thread = []

@app.before_request
def before_request():
    print '%s connection...' % request.remote_addr

class RedisInfo(threading.Thread):
    def __init__(self,host,port,password=None):
        super(RedisInfo, self).__init__()
        self.host = host
        self.port = port
        self.password = password
        self.client = redis.StrictRedis(host=self.host, port=self.port, password=self.password)
        self.status = {}
        self.table = []
        self.table_row = []
        self.qps = []
        self.nowtime = datetime.datetime.now()
        self.last_total_commands_processed = 0
        self.last_expired_keys = 0
        self.last_evicted_keys = 0
        self.last_keyspace_hits = 0
        self.last_keyspace_misses = 0
        self.commands_per_seconds = 0
        self.used_cpu_user = 0
        self.used_cpu_sys = 0
        self.mem_rss = 0
        self.mem = 0
        self.event = threading.Event()

    def run_command(self,*args):
        command = args[0].lower()
        if command == 'del':
            command = 'delete'
        try:
            method = getattr(self.client,command)
            result = method(*args[1:])
            print result
            if not result:
                result = 'KEY NOT FOUND'
            socketio.emit('command_result',{'data':result},namespace='/test')
        except Exception as e:
            socketio.emit('command_result',{'data':e.message},namespace='/test')


    def run(self):
        while 1:
            try:
                redis_info = self.client.info()
                self.nowtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
                # status
                self.status['redis_server_ip'] = '%s:%s' % (self.host, self.port)
                self.status['redis_version'] = redis_info['redis_version']
                self.status['redis_mode'] = redis_info['redis_mode'] if 'redis_mode' in redis_info else ''
                self.status['process_id'] = redis_info['process_id']
                self.status['uptime_in_seconds'] = redis_info['uptime_in_seconds']
                self.status['uptime_in_days'] = redis_info['uptime_in_days']
                self.status['role'] = redis_info['role']
                self.status['connected_slaves'] = redis_info['connected_slaves']
                self.status['rdb_bgsave_in_progress'] = redis_info['rdb_bgsave_in_progress'] if 'rdb_bgsave_in_progress' in redis_info else ''
                self.status['rdb_last_save_time'] = redis_info['rdb_last_save_time'] if 'rdb_last_save_time' in redis_info else ''

                #table
                self.table_row = []
                self.table_row.append(self.nowtime)
                self.used_cpu_user = round(redis_info['used_cpu_user_children'] / 1000,2)
                self.used_cpu_sys = round(redis_info['used_cpu_sys_children'] / 1000,2)
                self.table_row.append(self.used_cpu_user)
                self.table_row.append(self.used_cpu_sys)
                self.table_row.append(redis_info['connected_clients'])
                self.table_row.append(redis_info['blocked_clients'])
                self.mem = round(redis_info['used_memory'] / 1024 / 1024, 2)
                self.table_row.append('%sM' % self.mem)
                self.mem_rss = round(redis_info['used_memory_rss'] / 1024 / 1024, 2)
                self.table_row.append('%sM' % self.mem_rss)
                keys = sum([v['keys'] for k, v in redis_info.items() if k.startswith('db') and 'keys' in v])
                self.table_row.append(keys)
                if len(self.table) == 0:
                    self.table_row.append(0)
                    self.table_row.append(0)
                    self.table_row.append(0)
                    self.table_row.append(0)
                    self.table_row.append(0)
                else:
                    self.commands_per_seconds = (redis_info['total_commands_processed'] - self.last_total_commands_processed) / INFO_INTERVAL
                    self.table_row.append(self.commands_per_seconds)
                    self.qps.append({'time':self.nowtime.split(' ')[1],'data':self.commands_per_seconds})
                    self.table_row.append((redis_info['expired_keys'] - self.last_expired_keys) / INFO_INTERVAL)
                    self.table_row.append((redis_info['evicted_keys'] - self.last_evicted_keys) / INFO_INTERVAL)
                    self.table_row.append((redis_info['keyspace_hits'] - self.last_keyspace_hits) / INFO_INTERVAL)
                    self.table_row.append((redis_info['keyspace_misses'] - self.last_keyspace_misses) / INFO_INTERVAL)

                self.last_total_commands_processed = redis_info['total_commands_processed']
                self.last_expired_keys = redis_info['expired_keys']
                self.last_evicted_keys = redis_info['evicted_keys']
                self.last_keyspace_hits = redis_info['keyspace_hits']
                self.last_keyspace_misses = redis_info['keyspace_misses']
                if redis_info['aof_enabled']:
                    aof_size = round(redis_info['aof_current_size'] / 1024 / 1024,2)
                    self.table_row.append('%sM' % aof_size)
                else:
                    self.table_row.append(0)

                self.table.append(self.table_row)
                if len(self.table) > TABLE_MAX_ROWS:
                    self.table.pop(0)
                if len(self.qps) > 5:
                    self.qps.pop(0)
                table_result = list(reversed(self.table))
                socketio.emit('result',{
                    'type':'redis','stat' : self.status, 'table' : table_result, 'server' : '%s:%s' % (self.host, self.port),
                    'qps':self.qps
                },namespace='/test')
            except Exception as ex:
                print ex.message
            time.sleep(2)

class MemcacheInfo(threading.Thread):
    def __init__(self,host,port):
        super(MemcacheInfo,self).__init__()
        self.host = host
        self.port = port
        self.server = self.host + ':' + self.port
        self.client = memcache.Client([self.server])
        self.status = {}
        self.nowtime = datetime.datetime.now()
        self.table_row = []
        self.table = []
        self.hits = []

    def run_command(self,*args):
        command = args[0].lower()
        print args
        if command == 'del':
            command = 'delete'
        try:
            method = getattr(self.client,command)
            result = method(str(*args[1:]))
            print result
            if not result:
                result = 'KET NOT FOUND'
            socketio.emit('command_result',{'data':result},namespace='/test')
        except Exception as e:
            socketio.emit('command_result',{'data':e.message},namespace='/test')

    def run(self):
        while 1:
            try:
                memcache_info = self.client.get_stats()
                self.nowtime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
                self.status['memcache_server_ip'] = memcache_info[0][0].split(' ')[0]
                self.status['version'] = memcache_info[0][1].get('version')
                self.status['thread'] = memcache_info[0][1].get('threads')
                self.status['pid'] = memcache_info[0][1].get('pid')
                self.status['total_memory'] = '%dM' % (int(memcache_info[0][1].get('limit_maxbytes')) / 1024 / 1024)
                self.status['uptime'] = '%d天' % (int(memcache_info[0][1].get('uptime')) / 86400)
                self.status['libevent'] = memcache_info[0][1].get('libevent')

                #table
                self.table_row = []
               # self.table_row.append(self.server)
                self.table_row.append(self.nowtime)
                self.table_row.append(memcache_info[0][1].get('cmd_get'))
                self.table_row.append(memcache_info[0][1].get('cmd_set'))
                self.get_hits = int(memcache_info[0][1].get('get_hits'))
                self.table_row.append(self.get_hits)
                self.get_misses = int(memcache_info[0][1].get('get_misses'))
                self.table_row.append(self.get_misses)
                #print type(self.get_hits)
                self.usage_memory = '%dM' % (int(memcache_info[0][1].get('bytes')) / 1024 / 1024)
                self.table_row.append(self.usage_memory)
                self.table_row.append(memcache_info[0][1].get('curr_connections'))
                self.table_row.append(format(float(self.get_hits) / (self.get_hits + self.get_misses),'.2%'))
                self.table_row.append(format(float(self.usage_memory.rstrip('M')) / int(self.status['total_memory'].rstrip('M')),'.2%'))
                self.hits.append({'time':self.nowtime.split(' ')[1],'data':round(float(self.get_hits) / (self.get_hits + self.get_misses) *100,2)})

                self.table.append(self.table_row)
                if len(self.table) > TABLE_MAX_ROWS:
                    self.table.pop(0)
                if len(self.hits) > 5:
                    self.hits.pop(0)
                table_result = list(reversed(self.table))
                socketio.emit('result',{
                    'type':'memcache','stat' : self.status, 'table' : table_result, 'server' : '%s:%s' % (self.host, self.port),
                    'hits':self.hits
                },namespace='/test')
            except Exception as ex:
                 print ex.message
            time.sleep(INFO_INTERVAL)

for key,value in SERVER_LIST.iteritems():
    if key == 'REDIS_SERVER':
        for r in value:
            print r
            r_list = r.split(':')
            if len(r_list) > 2:
                r_info = RedisInfo(r_list[0],r_list[1],r_list[2])
            else:
                r_info = RedisInfo(r_list[0],r_list[1])
            r_info.setDaemon(True)
            r_info.start()
            all_thread.append(r_info)
    elif key == 'MEMCACHE_SERVER':
        for m in value:
            print m
            host,port = m.split(':')
            m_info = MemcacheInfo(host=host,port=port)
            m_info.setDaemon(True)
            m_info.start()
            all_thread.append(m_info)

def signal_handler(signal, frame):
    for t in all_thread:
        t.stop()
    print '\033[93m Now all of info thread are stopped!\033[0m'
    sys.exit(0)

@app.route('/')
def get_index_page():
    return  render_template('index.html')

@socketio.on('connect',namespace='/test')
def test_connect():
    print 'connect'

@socketio.on('disconnect')
def client_disconnect():
    print 'Client disconnected'

@socketio.on('event',namespace='/test')
def client_message(message):
    print message
    if message['data'] == 'redis':
        emit('servers',{'data':SERVER_LIST['REDIS_SERVER']})
    elif message['data'] == 'memcache':
        emit('servers',{'data':SERVER_LIST['MEMCACHE_SERVER']})

@socketio.on('command',namespace='/test')
def command(message):
    c_list = []
    server = message['server']
    cmd = message['command']
    c_list.append(cmd)
    args = message['args'].split(',')
    c_list.extend(args)
    print server,c_list
    th = None
    for t in all_thread:
        if '%s:%s' % (t.host,t.port) == server:
            th = t
    print th.host,th.port
    if th is not None:
        th.run_command(*c_list)
    else:
        pass

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    socketio.run(app,host='0.0.0.0')