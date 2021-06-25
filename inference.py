import logging
import tensorflow as tf
import numpy as np
import os

from model_multitask_bert import MyModel
from bert import modeling as bert_modeling
from utils import DataProcessor_MTL_BERT as DataProcessor
from utils import load_vocabulary
from utils import extract_kvpairs_in_bioes
from utils import cal_f1_score

data_path = "./data/data1"

bert_vocab_path = "../nlp_model/chinese_bert_L-12_H-768_A-12/vocab.txt"
bert_config_path = "../nlp_model/chinese_bert_L-12_H-768_A-12/bert_config.json"
bert_ckpt_path = "ckpt/model.ckpt.batch7900_0.7629"

# set logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S")
chlr = logging.StreamHandler()
chlr.setFormatter(formatter)
logger.addHandler(chlr)

logger.info("loading vocab...")

w2i_char, i2w_char = load_vocabulary(bert_vocab_path)
w2i_bio, i2w_bio = load_vocabulary(data_path+"/vocab_bio.txt")
w2i_attr, i2w_attr = load_vocabulary(data_path+"/vocab_attr.txt")

logger.info("loading data...")

input_char_list = [', 2 0 0 9 年 1 2 月 底 出 现 黑 便 , , 于 当 地 行 胃 镜 检 查 并 行 病 理 检 查 示 : 叒 胃 体 中 下 部 溃 疡 , 叒 病 理 示 中 分 化 腺 癌 ,']
output_bio_list = ['O O O O O O O O O O O O O O O O O O O O O O O O O O O O O O O O O B I I I I I E O O O O O B I I I E O']
output_attr_list = ['null null null null null null null null null null null null null null null null null null null null null null null null null null null null null null null null null 疾病和诊断 疾病和诊断 疾病和诊断 疾病和诊断 疾病和诊断 疾病和诊断 疾病和诊断 null null null null null 疾病和诊断 疾病和诊断 疾病和诊断 疾病和诊断 疾病和诊断 null']

data_processor_valid = DataProcessor(
    input_char_list,
    output_bio_list,
    output_attr_list,
    w2i_char,
    w2i_bio, 
    w2i_attr, 
    shuffling=True
)

logger.info("building model...")

bert_config = bert_modeling.BertConfig.from_json_file(bert_config_path)
logger.info(bert_config.to_json_string())
        
model = MyModel(bert_config=bert_config, 
                vocab_size_bio=len(w2i_bio), 
                vocab_size_attr=len(w2i_attr), 
                O_tag_index=w2i_bio["O"],
                use_crf=True)

logger.info("model params:")
params_num_all = 0
for variable in tf.trainable_variables():
    params_num = 1
    for dim in variable.shape:
        params_num *= dim
    params_num_all += params_num
    logger.info("\t {} {} {}".format(variable.name, variable.shape, params_num))
logger.info("all params num: " + str(params_num_all))
        
logger.info("loading bert pretrained parameters...")
tvars = tf.trainable_variables()
(assignment_map, initialized_variable_names) = bert_modeling.get_assignment_map_from_checkpoint(tvars, bert_ckpt_path)
tf.train.init_from_checkpoint(bert_ckpt_path, assignment_map)

logger.info("start training...")

tf_config = tf.ConfigProto(allow_soft_placement=True)
tf_config.gpu_options.allow_growth = True

with tf.Session(config=tf_config) as sess:
    sess.run(tf.global_variables_initializer())
        
    def valid(data_processor, max_batches=None, batch_size=1024):
        preds_kvpair = []
        golds_kvpair = []
        batches_sample = 0
        
        while True:
            (inputs_seq_batch, 
             inputs_mask_batch,
             inputs_segment_batch,
             outputs_seq_bio_batch,
             outputs_seq_attr_batch) = data_processor.get_batch(batch_size)

            feed_dict = {
                model.inputs_seq: inputs_seq_batch,
                model.inputs_mask: inputs_mask_batch,
                model.inputs_segment: inputs_segment_batch
            }
            
            preds_seq_bio_batch, preds_seq_attr_batch = sess.run(model.outputs, feed_dict)
            
            for pred_seq_bio, gold_seq_bio, pred_seq_attr, gold_seq_attr, input_seq, mask in zip(preds_seq_bio_batch,
                                                                                                 outputs_seq_bio_batch,
                                                                                                 preds_seq_attr_batch,
                                                                                                 outputs_seq_attr_batch,
                                                                                                 inputs_seq_batch,
                                                                                                 inputs_mask_batch):
                l = sum(mask) - 2
                pred_seq_bio = [i2w_bio[i] for i in pred_seq_bio[1:-1][:l]]
                gold_seq_bio = [i2w_bio[i] for i in gold_seq_bio[1:-1][:l]]
                char_seq = [i2w_char[i] for i in input_seq[1:-1][:l]]
                pred_seq_attr = [i2w_attr[i] for i in pred_seq_attr[1:-1][:l]]
                gold_seq_attr = [i2w_attr[i] for i in gold_seq_attr[1:-1][:l]]
                
                pred_kvpair = extract_kvpairs_in_bioes(pred_seq_bio, char_seq, pred_seq_attr)
                gold_kvpair = extract_kvpairs_in_bioes(gold_seq_bio, char_seq, gold_seq_attr)
                
                preds_kvpair.append(pred_kvpair)
                golds_kvpair.append(gold_kvpair)
                
            if data_processor.end_flag:
                data_processor.refresh()
                break
            
            batches_sample += 1
            if (max_batches is not None) and (batches_sample >= max_batches):
                break
        
        print(preds_kvpair)
        print(golds_kvpair)
        p, r, f1 = cal_f1_score(preds_kvpair, golds_kvpair)

        logger.info("Valid Samples: {}".format(len(preds_kvpair)))
        logger.info("Valid P/R/F1: {} / {} / {}".format(round(p*100, 2), round(r*100, 2), round(f1*100, 2)))
        
        return (p, r, f1)

    
    p, r, f1 = valid(data_processor_valid, max_batches=10)            
            