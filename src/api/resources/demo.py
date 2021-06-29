# coding:utf-8

import os
from flask import Flask, Blueprint, render_template, request
import urllib3, json, base64, time, hashlib
from datetime import datetime
from api.utils import helper
from config.settings import BIND_PORT
from .. import logger

logger = logger.get_logger(__name__)


demo_app = Blueprint('demo', __name__)


# 接口演示
@demo_app.route("/ner/demo", methods=["GET"])
def demo_get():
    return render_template('demo.html')

@demo_app.route("/ner/demo", methods=["POST"])
def demo_post():
    text = request.form['text']
    api_url, params, status, rdata, timespan = call_api("ner", text)
    return render_template('result.html', 
        result=rdata, status=status, 
        timespan=timespan, params=params, api_url=api_url)


# 调用接口
def call_api(cate, text):
    hostname = '127.0.0.1'
    cate = cate

    body = {
        'version'  : '1',
        'signType' : 'SHA256', 
        #'signType' : 'SM2',
        'encType'  : 'plain',
        'data'     : {
            'text'    : text,
        }
    }

    appid = '66A095861BAE55F8735199DBC45D3E8E'
    unixtime = int(time.time())
    body['timestamp'] = unixtime
    body['appId'] = appid

    param_str = helper.gen_param_str(body)
    sign_str = '%s&key=%s' % (param_str, '43E554621FF7BF4756F8C1ADF17F209C')

    if body['signType'] == 'SHA256':
        signature_str =  base64.b64encode(hashlib.sha256(sign_str.encode('utf-8')).hexdigest().encode('utf-8')).decode('utf-8')
    else: # SM2
        signature_str = sm2.SM2withSM3_sign_base64(sign_str)

    #print(sign_str)

    body['signData'] = signature_str

    body_str = json.dumps(body)
    #print(body)

    pool = urllib3.PoolManager(num_pools=2, timeout=180, retries=False)

    host = 'http://%s:%s'%(hostname, BIND_PORT)
    if cate == 'ner':
        url = host+'/ner/ner'
    else:
        url = host+'/ner/ner' # 都一样，目前没其他的

    start_time = datetime.now()
    r = pool.urlopen('POST', url, body=body_str)
    #print('[Time taken: {!s}]'.format(datetime.now() - start_time))

    print(r.status)
    if r.status==200:
        rdata = json.dumps(json.loads(r.data.decode('utf-8')), ensure_ascii=False, indent=4)
    else:
        rdata = r.data

    body2 = json.dumps(body, ensure_ascii=False, indent=4)
    return url, body2, r.status, rdata, \
        '{!s}s'.format(datetime.now() - start_time)
