# -*- coding: utf-8 -*-
#
# 后台daemon进程，启动后台处理进程，并检查进程监控状态
#

import sys
import time, shutil, os
from api.utils import helper
from config.settings import REDIS_CONFIG


APP_DIR=''
LOG_DIR=''

def start_processor(pname, param=''):
    cmd0="nohup python3 %s/%s.pyc %s >> %s/ner_%s.log 2>&1 &" % \
        (APP_DIR, pname, param, LOG_DIR, pname+param.replace(' ',''))
    print('start process: ', cmd0)
    os.system(cmd0)

def get_processor_pid(pname):
    cmd0='pgrep -f "%s"' % pname
    pid=os.popen(cmd0).readlines()
    if len(pid)>0:
        return pid[0].strip()
    else:
        return None

def kill_processor(pname):
    cmd0='kill -9 `pgrep -f "%s"`' % pname
    os.system(cmd0)
    time.sleep(1)

if __name__=='__main__':
    if len(sys.argv)<3:
        print("usage: daemon.py <APP_DIR> <LOG_DIR>")
        sys.exit(2)

    APP_DIR=sys.argv[1]
    LOG_DIR=sys.argv[2]

    print("DAEMON: %s started" % helper.time_str())
    print("APP_DIR=%s\nLOG_DIR=%s" % (APP_DIR, LOG_DIR))

    #
    #启动后台进程
    #
    kill_processor('%s/dispatcher' % APP_DIR)
    for i in range(REDIS_CONFIG['REQUEST-QUEUE-NUM']):
        start_processor('dispatcher', str(i+1))

    try:    
        _count=_ins=0
        while 1:                        
            # 检查processor进程 dispatcher
            pid=get_processor_pid('%s/dispatcher' % APP_DIR)
            if pid==None:
                # 进程已死, 重启进程
                kill_processor('%s/dispatcher' % APP_DIR)
                for i in range(REDIS_CONFIG['REQUEST-QUEUE-NUM']):
                    start_processor('dispatcher', str(i+1))
                _ins+=1
                print("%s\tdispatcher restart" % helper.time_str())

                        
            time.sleep(5)
            if _count>1000:
                if _ins>0:
                    print("%s  HEARTBEAT: error %d" % (helper.time_str(), _ins))
                else:
                    print("%s  HEARTBEAT: fine." % (helper.time_str()))
                _count=_ins=0
            sys.stdout.flush()

    except KeyboardInterrupt:
        print('\nCtrl-C!')

    print("DAEMON: %s exited" % helper.time_str())
