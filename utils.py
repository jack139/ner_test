import random
import numpy as np

##########################
####### Vocabulary #######
##########################
            
def load_vocabulary(path):
    vocab = open(path, "r", encoding="utf-8").read().strip().split("\n")
    print("load vocab from: {}, containing words: {}".format(path, len(vocab)))
    w2i = {}
    i2w = {}
    for i, w in enumerate(vocab):
        w2i[w] = i
        i2w[i] = w
    return w2i, i2w


    
###################################################
####### DataProcessor 4: for Multitask-BERT #######
###################################################
    
class DataProcessor_MTL_BERT(object):
    def __init__(self, 
                 input_seq_path, 
                 output_seq_bio_path,
                 output_seq_attr_path,
                 w2i_char, 
                 w2i_bio, 
                 w2i_attr,
                 shuffling=False):
        
        if type(input_seq_path)==type(""): # 传入文件名
            with open(input_seq_path, "r", encoding="utf-8") as f:
                lines1 = f.read().strip().split("\n")
            with open(output_seq_bio_path, "r", encoding="utf-8") as f:
                lines2 = f.read().strip().split("\n")
            with open(output_seq_attr_path, "r", encoding="utf-8") as f:
                lines3 = f.read().strip().split("\n")
        else: # 传入的是 列表
            lines1 = input_seq_path
            lines2 = output_seq_bio_path
            lines3 = output_seq_attr_path
        
        inputs_seq = []
        outputs_seq_bio = []
        outputs_seq_attr = []
        for line1, line2, line3 in zip(lines1, lines2, lines3):   
            words = []
            bios = []
            attrs = []
            for word, bio, attr in zip(line1.split(" "), line2.split(" "), line3.split(" ")):
                if word != "[SPA]":
                    words.append(word)
                    bios.append(bio)
                    attrs.append(attr)
                    
            words.insert(0, "[CLS]")
            words.append("[SEP]")
            seq = [w2i_char[word] if word in w2i_char else w2i_char["[UNK]"] for word in words]
            inputs_seq.append(seq)
                
            bios.insert(0, "O")
            bios.append("O")
            seq = [w2i_bio[bio] for bio in bios]
            outputs_seq_bio.append(seq)
            
            attrs.insert(0, "null")
            attrs.append("null")
            seq = [w2i_attr[attr] for attr in attrs]
            outputs_seq_attr.append(seq)
                
        assert len(inputs_seq) == len(outputs_seq_bio)
        assert all(len(input_seq) == len(output_seq_bio) for input_seq, output_seq_bio in zip(inputs_seq, outputs_seq_bio))
        assert len(inputs_seq) == len(outputs_seq_attr)
        assert all(len(input_seq) == len(output_seq_attr) for input_seq, output_seq_attr in zip(inputs_seq, outputs_seq_attr))
        
        self.w2i_char = w2i_char
        self.w2i_bio = w2i_bio
        self.w2i_attr = w2i_attr
        self.inputs_seq = inputs_seq
        self.outputs_seq_bio = outputs_seq_bio
        self.outputs_seq_attr = outputs_seq_attr
        self.ps = list(range(len(inputs_seq)))
        self.shuffling = shuffling
        if shuffling: random.shuffle(self.ps)
        self.pointer = 0
        self.end_flag = False
        print("DataProcessor load data num: " + str(len(inputs_seq)) + " shuffling: " + str(shuffling))
        
    def refresh(self):
        if self.shuffling: random.shuffle(self.ps)
        self.pointer = 0
        self.end_flag = False
    
    def get_batch(self, batch_size):
        inputs_seq_batch = []
        inputs_mask_batch = []
        inputs_segment_batch = []
        outputs_seq_bio_batch = []
        outputs_seq_attr_batch = []
        lens = []
        
        while (len(inputs_seq_batch) < batch_size) and (not self.end_flag):
            p = self.ps[self.pointer]
            inputs_seq_batch.append(self.inputs_seq[p].copy())
            l = len(self.inputs_seq[p])
            inputs_mask_batch.append([1] * l)
            inputs_segment_batch.append([0] * l)
            outputs_seq_bio_batch.append(self.outputs_seq_bio[p].copy())
            outputs_seq_attr_batch.append(self.outputs_seq_attr[p].copy())
            lens.append(l)
            self.pointer += 1
            if self.pointer >= len(self.ps): self.end_flag = True
        
        max_seq_len = max(lens)
        for input_seq, input_mask, input_segment, output_seq_bio, output_seq_attr, l in zip(inputs_seq_batch, 
                                                                                            inputs_mask_batch, 
                                                                                            inputs_segment_batch, 
                                                                                            outputs_seq_bio_batch,
                                                                                            outputs_seq_attr_batch,
                                                                                            lens):
            input_seq.extend([self.w2i_char["[PAD]"]] * (max_seq_len - l))
            input_mask.extend([0] * (max_seq_len - l))
            input_segment.extend([0] * (max_seq_len - l))
            output_seq_bio.extend([self.w2i_bio["O"]] * (max_seq_len - l))
            output_seq_attr.extend([self.w2i_attr["null"]] * (max_seq_len - l))
            
        return (np.array(inputs_seq_batch, dtype="int32"),
                np.array(inputs_mask_batch, dtype="int32"),
                np.array(inputs_segment_batch, dtype="int32"),
                np.array(outputs_seq_bio_batch, dtype="int32"),
                np.array(outputs_seq_attr_batch, dtype="int32"))
    

    
######################################
####### extract_kvpairs_by_bio #######
######################################

def extract_kvpairs_in_bio(bio_seq, word_seq):
    assert len(bio_seq) == len(word_seq)
    pairs = set()
    pre_bio = "O"
    v = ""
    for i, bio in enumerate(bio_seq):
        if (bio == "O"):
            if v != "": pairs.add((pre_bio[2:], v))
            v = ""
        elif (bio[0] == "B"):
            if v != "": pairs.add((pre_bio[2:], v))
            v = word_seq[i]
        elif (bio[0] == "I"):
            if (pre_bio[0] == "O") or (pre_bio[2:] != bio[2:]):
                if v != "": pairs.add((pre_bio[2:], v))
                v = ""
            else:
                v += word_seq[i]
        pre_bio = bio
    if v != "": pairs.add((pre_bio[2:], v))
    return pairs

def extract_kvpairs_in_bioes(bio_seq, word_seq, attr_seq):
    assert len(bio_seq) == len(word_seq) == len(attr_seq)
    pairs = set()
    v = ""
    for i in range(len(bio_seq)):
        word = word_seq[i]
        bio = bio_seq[i]
        attr = attr_seq[i]
        if bio == "O":
            v = ""
        elif bio == "S":
            v = word
            pairs.add((attr, v))
            v = ""
        elif bio == "B":
            v = word
        elif bio == "I":
            if v != "": 
                v += word
        elif bio == "E":
            if v != "":
                v += word
                pairs.add((attr, v))
            v = ""
    return pairs


############################
####### cal_f1_score #######
############################

def cal_f1_score(preds, golds):
    assert len(preds) == len(golds)
    p_sum = 0
    r_sum = 0
    hits = 0
    for pred, gold in zip(preds, golds):
        p_sum += len(pred)
        r_sum += len(gold)
        for label in pred:
            if label in gold:
                hits += 1
    p = hits / p_sum if p_sum > 0 else 0
    r = hits / r_sum if r_sum > 0 else 0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
    return p, r, f1

