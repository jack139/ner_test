# -*- coding: utf-8 -*-

from datetime import datetime
from ner.inference import inference
from api import logger

logger = logger.get_logger(__name__)


# NER识别
def ner(request_id, original_text):
    #start_time = datetime.now()

    entities = inference(original_text)

    logger.info("entities : %d"%len(entities))

    #print('[Time taken: {!s}]'.format(datetime.now() - start_time))
    return entities
