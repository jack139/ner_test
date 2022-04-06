#! -*- coding: utf-8 -*-
# 用GlobalPointer做中文命名实体识别

import os
import json
import numpy as np
import logging
import tensorflow as tf

from bert4keras.layers import EfficientGlobalPointer as GlobalPointer
from bert4keras.models import build_transformer_model
from bert4keras.tokenizers import Tokenizer
from bert4keras.snippets import open, to_array
from keras.models import Model

from config.settings import NER_CHECKPOINT


maxlen = 512

# 标签： 要与训练时顺序一致
categories = ['检验和检查', '治疗和手术', '疾病和诊断', '症状和体征', '药物', '解剖部位']

# bert配置
config_path = os.path.join(NER_CHECKPOINT, 'bert_config.json')
#checkpoint_path = os.path.join(NER_CHECKPOINT, '../../nlp_model/chinese_bert_L-12_H-768_A-12/bert_model.ckpt')
checkpoint_path = os.path.join(NER_CHECKPOINT, 'pack_best_f1_0.82966.weights')
dict_path = os.path.join(NER_CHECKPOINT, 'vocab.txt')

# 建立分词器
tokenizer = Tokenizer(dict_path, do_lower_case=True)

# set logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S")
chlr = logging.StreamHandler()
chlr.setFormatter(formatter)
logger.addHandler(chlr)

# GPU内存控制
GPU_MEMORY = 0.1
GPU_RUN = False
gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=GPU_MEMORY)
# 是否强制使用 CPU
if GPU_RUN:
    config = tf.ConfigProto(allow_soft_placement=True, gpu_options=gpu_options)
else:
    config = tf.ConfigProto(device_count = {'CPU' : 1, 'GPU' : 0}, gpu_options=gpu_options)


# 建立默认session
graph = tf.Graph()  # 解决多线程不同模型时，keras或tensorflow冲突的问题
session = tf.Session(graph=graph, config=config)
with graph.as_default():
    with session.as_default():

        logger.info("loading model...")

        model = build_transformer_model(config_path)
        output = GlobalPointer(len(categories), 64)(model.output)

        model = Model(model.input, output)
        #model.summary()

        logger.info(f"loading weights: {checkpoint_path}")
        model.load_weights(checkpoint_path)


        class NamedEntityRecognizer(object):
            """命名实体识别器
            """
            def recognize(self, text, threshold=0):
                tokens = tokenizer.tokenize(text, maxlen=maxlen)
                mapping = tokenizer.rematch(text, tokens)
                token_ids = tokenizer.tokens_to_ids(tokens)
                segment_ids = [0] * len(token_ids)
                token_ids, segment_ids = to_array([token_ids], [segment_ids])
                scores = model.predict([token_ids, segment_ids])[0]
                scores[:, [0, -1]] -= np.inf
                scores[:, :, [0, -1]] -= np.inf
                entities = []
                for l, start, end in zip(*np.where(scores > threshold)):
                    entities.append(
                        (mapping[start][0], mapping[end][-1], categories[l])
                    )
                return entities


        NER = NamedEntityRecognizer()


# 模型推理
def inference(original_text):
    d = []
    pos_offset = 0
    while pos_offset<len(original_text):
        if len(original_text[pos_offset:])>maxlen: # 大于 maxlen 的进行截短处理
            for n in range(maxlen, 0, -1):
                if original_text[pos_offset:][n] in ['；', '，', '。', ',', '）', '、', ';']:
                    break
            text1 = original_text[pos_offset:][:n]
        else:
            text1 = original_text[pos_offset:]

        with graph.as_default(): # 解决多线程不同模型时，keras或tensorflow冲突的问题
            with session.as_default():
                entities = NER.recognize(text1)

        for e in entities:
            d.append({
                'start_pos': e[0]+pos_offset,
                #'end_pos': e[1],
                'label': e[2],
                'value': text1[e[0]:e[1]+1]
            })

        pos_offset += len(text1)

    # 按起始位置排序
    d = sorted(d, key=lambda x: x['start_pos'])

    return d


if __name__ == '__main__':
    
    # 原始输入：不限制长度，会被自动分段，以“，”和“。”分割，建议间隔不要大于100字。
    original_text = ",2009年12月底出现黑便,,于当地行胃镜检查并行病理检查示:叒胃体中下部溃疡,叒病理示中分化腺癌,叒无腹胀、泛酸、嗳气、恶心、呕吐、叒无头晕、叒心悸、乏力等症,叒2010年1月13日于我院胃胰科行胃癌根治术,叒2010年1月18日,我院病理:切缘未见癌,叒胃体可见3x2x1cm3溃疡型肿物,叒镜上为中分化腺癌侵及胃壁全层至浆膜层,网膜未见癌,叒肝总动脉旁(0/1)、叒胃大弯(0/1)淋巴结未见癌,叒贲门左(3/3)、叒胃小弯(8/9)、幽门上(2/2)淋巴结可见腺癌转移,,免疫组化:cea(+)、叒p53(+)、叒pr(-)、叒er-b(+)、叒er(+++)、叒共计,ln:叒13/16转移,叒术后于2010年2月-2010年8月行术后化疗6程,叒具体用药为艾素100mg叒静点+叒希罗达1500mg叒bid叒po,2014年6月初出现右侧下上肢活动受限,叒7月份症状逐渐加重,叒7月10日就诊于*****,叒,行mri检查提示:胃癌术后多发脑转移,叒行甘露醇及地塞米松、叒洛赛克治疗后效果不佳。遂于我院就诊,2014-8-5行奥沙利铂150mg叒d1+叒替吉奥叒50mg叒bid叒d1-14化疗一程,2014-08-18开始行三维适形全脑放疗,剂量30gy/10f。2014-09-19始行替吉奥叒50mg叒bid叒d1-14单药化疗一程。本次为行上一程化疗收入我科,叒我科以“胃癌术后脑转移叒rtxnxm1叒iv期”收入,叒入科以来,叒精神饮食尚可,叒无恶心、叒呕吐,二便正常,体重无明显减低。"

    entities = inference(original_text)

    print(len(original_text), original_text)
    print(entities)

    # 核对结果是否与原始文本对应
    for i in entities:
        ori_value = original_text[i['start_pos']:i['start_pos']+len(i['value'])]
        if ori_value != i['value']:
            print("?", i, ori_value)
