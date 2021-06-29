# coding:utf-8

import sys, time, os, shutil
import json, random, hashlib, base64
import threading
import functools

import redis

from . import sm2
from config.settings import REDIS_CONFIG
from .. import logger

logger = logger.get_logger(__name__)


# 检查文件类型是否可接受上传
ALLOWED_EXTENSIONS = [
    set(['jpg', 'jpeg', 'png']), # 图片文件
]
def allowed_file(filename, category=0):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS[category]

# 返回指定长度的随机字符串
def ranstr(num):
    H = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    salt = ''
    for i in range(num):
        salt += random.choice(H)
    return salt

# 按格式输出时间字符串
ISOTIMEFORMAT=['%Y-%m-%d %X', '%Y-%m-%d', '%Y%m%d', '%Y%m%d%H%M%S']
def time_str(t=None, format=0):
    return time.strftime(ISOTIMEFORMAT[format], time.localtime(t))


###### about 签名

# 生成参数字符串
def gen_param_str(param1):
    param = param1.copy()
    name_list = sorted(param.keys())
    if 'data' in name_list: # data 按 key 排序
        param['data'] = json.dumps(param['data'], sort_keys=True).replace(' ','')
    return '&'.join(['%s=%s'%(str(i), str(param[i])) for i in name_list if str(param[i])!=''])

# 检查signature修饰器
def signature_required(view_func):
    from config.settings import SECRET_KEY, DEBUG_MODE
    
    @functools.wraps(view_func)
    def verify_signature(*args,**kwargs):
        if DEBUG_MODE:
            return view_func(*args,**kwargs)  ## !!!!!!!!!!!!!!!!!!!!!!!! 测试时，关闭签名校验

        from flask_restful import request

        ret_json = {
            "appId"     : '',
            "code"      : 9000,
            "success"   : False,
            "signType"  : "plain",
            "encType"   : "plain",
            "data"      : {},
            "timestamp" : int(time.time()),
        }

        try:
            # 获取入参
            body_data = request.get_data().decode('utf-8') # bytes to str
            json_data = json.loads(body_data)

            #print(json_data)

            # 请求写入临时文件，测试使用
            #with open('/tmp/cardnum/%d.txt'%ret_json['timestamp'], 'w') as f:
            #    f.write(json.dumps(json_data))

            appid = ret_json['appId'] = json_data['appId']
            unixtime = json_data['timestamp']
            signature = json_data.get('signData', '').replace('\r','').replace('\n','') # 去掉回车换行
            sign_type = json_data['signType']
            enc_type = json_data.get('encType', 'plain')
            version = json_data.get('version', '1')

            #json_data['data'] = json.loads(json_data['data']) # data 也是 json

            # 调用时间不能超过前后5分钟
            #if abs(int(time.time())-int(unixtime))>300:
            #    logger.error("verify_signature: 调用时间错误") 
            #    ret_json["code"] = 9802
            #    ret_json["data"] = {"msg": "调用时间错误"}
            #    return ret_json

            # 检查参数
            if sign_type not in ['SM2', 'SHA256', 'plain']:
                logger.error("verify_signature: 未知的签名类型") 
                ret_json["code"] = 9803
                ret_json["data"] = {"msg": "未知的签名类型"}
                return ret_json                

            if enc_type!='plain':
                logger.error("verify_signature: 未知的加密类型") 
                ret_json["code"] = 9804
                ret_json["data"] = {"msg": "未知的加密类型"}
                return ret_json                

            # 固定参数不参与计算参数字符串
            json_data.pop('signData')
            json_data.pop('encData', None) # 可为空
            json_data.pop('extra', None) # 可为空

            # 获取私钥
            if appid in SECRET_KEY.keys():
                secret = SECRET_KEY[appid]
            else:
                logger.error("verify_signature: appid错误") 
                ret_json["code"] = 9805
                ret_json["data"] = {"msg": "appid错误"}
                return ret_json                


        except Exception as e:
            print(body_data)
            logger.error("verify_signature: 异常: %s : %s" % (e.__class__.__name__, e), exc_info=True)
            ret_json["code"] = 9801
            ret_json["data"] = {"msg": "签名参数有错误"}
            return ret_json

        # 生成参数字符串
        param_str = gen_param_str(json_data)

        sign_str = '%s&key=%s' % (param_str, secret)

        #print(sign_str)
        # 请求写入临时文件，测试使用
        #with open('/tmp/cardnum/%d.txt'%ret_json['timestamp'], 'a') as f:
        #    f.write('\n')
        #    f.write(sign_str)

        logger.info("verify_signature: sign_type= "+sign_type) 
        start = time.time()

        if sign_type=='SHA256':
            signature_str =  base64.b64encode(hashlib.sha256(sign_str.encode('utf-8')).hexdigest().encode('utf-8')).decode('utf-8')
        elif sign_type=='SM2': # SM2 
            try:
                if sm2.SM2withSM3_verify_base64(signature, sign_str):
                    signature_str = signature 
                else:
                    signature_str = None # 未验签通过 
            except Exception as e:
                logger.error("SM2: 异常: %s : %s" % (e.__class__.__name__, e), exc_info=True)
                signature_str = None # 未验签通过 
        elif sign_type=='plain': # 不验签
            signature_str = signature 

        print(signature_str, signature)
        print("signature elapsed ====> {:.2f}s".format(time.time() - start))

        if signature==signature_str:
            return view_func(*args,**kwargs)
        else:
            print(sign_str)
            logger.error("verify_signature: 无效signature") 
            ret_json["code"] = 9800
            ret_json["data"] = {"msg": "无效签名"}
            return ret_json

    return verify_signature


# 生成request_id
def gen_request_id():
    return '%s%s'%(time_str(format=3)[2:],hashlib.md5(ranstr(10).encode('utf-8')).hexdigest())



########## 异步接口调用


# redis订阅
def redis_subscribe(queue_id):
    rc = redis.StrictRedis(host=REDIS_CONFIG['SERVER'], 
            port=REDIS_CONFIG['PORT'], db=1, password=REDIS_CONFIG['PASSWD'])
    ps = rc.pubsub()
    ps.subscribe(queue_id)  #从liao订阅消息
    logger.info('subscribe to : '+str((queue_id))) 
    return ps


# 从订阅接收, 值收一条
def redis_sub_receive(pubsub, queue_id):
    #for item in pubsub.listen():        #监听状态：有消息发布了就拿过来
    #    logger.debug('subscribe 2: '+str((queue_id, item))) 
    #    if item['type'] == 'message':
    #        #print(item)
    #        break

    start = time.time()
    while 1:
        item = pubsub.get_message()
        if item:
            logger.info('reveived: type='+item['type']) 
            if item['type'] == 'message':
                break

        # 检查超时
        if time.time()-start > REDIS_CONFIG['MESSAGE_TIMEOUT']:
            item = { 'data' : json.dumps({"code": 9997, 'data': {"msg": "消息队列超时"}}).encode('utf-8') }
            break

        # 释放cpu
        time.sleep(0.001)

    return item


# redis发布
def redis_publish(queue_id, data):
    logger.info('publish: '+queue_id) 
    msg_body = json.dumps(data)

    rc = redis.StrictRedis(host=REDIS_CONFIG['SERVER'], 
            port=REDIS_CONFIG['PORT'], db=1, password=REDIS_CONFIG['PASSWD'])
    return rc.publish(queue_id, msg_body)


# 返回　请求队列　随机id
def choose_queue_redis():
    # 随机返回
    return random.randint(1, REDIS_CONFIG['REQUEST-QUEUE-NUM'])

# redis发布到请求队列
def redis_publish_request(request_id, data):
    msg_body = {
        'request_id' : request_id, # request id
        'data' : data,
    }

    # 设置发送的queue
    queue = REDIS_CONFIG['REQUEST-QUEUE']+str(choose_queue_redis())
    print('queue:', queue)

    return redis_publish(queue, msg_body)
