# -*- coding: utf-8 -*-

from flask import Flask
from flask_restful import Api

from api.resources import *
from api.resources.demo import demo_app
from config.settings import BIND_ADDR, BIND_PORT, DEBUG_MODE

app = Flask(__name__)
api = Api(app)

@app.route('/')
def hello_world():
    return 'Hello World!'

# demo
app.register_blueprint(demo_app)

# OCR识别api，同步调用，异步处理（使用消息队列）
api.add_resource(NER, '/ner/ner')

if __name__ == '__main__':
    # 外部可见，出错时带调试信息（debug=True）
    # 转生产时，接口需要增减校验机制，避免非授权调用 ！！！！！！
    app.run(host=BIND_ADDR, port=BIND_PORT, debug=DEBUG_MODE)
