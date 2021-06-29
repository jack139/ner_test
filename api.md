
## api 文档

### 1. 全局接口定义

输入参数

| 参数      | 类型   | 说明                          | 示例        |
| --------- | ------ | ----------------------------- | ----------- |
| appId     | string | 应用渠道编号                  |             |
| version   | string | 版本号                        |             |
| signType  | string | 签名算法，目前使用国密SM2算法 | SM2或SHA256 |
| signData  | string | 签名数据，具体算法见下文      |             |
| encType   | string | 接口数据加密算法，目前不加密  | plain       |
| timestamp | int    | unix时间戳（秒）              |             |
| data      | json   | 接口数据，详见各接口定义      |             |

> 签名/验签算法：
>
> 1. 筛选，获取参数键值对，剔除signData、encData、extra三个参数。data参数按key升序排列进行json序列化。
> 2. 排序，按key升序排序。
> 3. 拼接，按排序好的顺序拼接请求参数
>
> ```key1=value1&key2=value2&...&key=appSecret```，key=appSecret固定拼接在参数串末尾，appSecret需替换成应用渠道所分配的appSecret。
>
> 4. 签名，使用制定的算法进行加签获取二进制字节，使用 16进制进行编码Hex.encode得到签名串，然后base64编码。
> 5. 验签，对收到的参数按1-4步骤签名，比对得到的签名串与提交的签名串是否一致。

签名示例：

```json
请求参数：
{
    "appid":"19E179E5DC29C05E65B90CDE57A1C7E5",
    "version": "1",
    "signType": "SM2",
    "signData": "...",
    "encType": "plain",
    "timestamp":1591943910,
    "data": {
    	"user_id":"gt",
    	"face_id":"5ed21b1c262daabe314048f5"
    }
}

密钥：
appSecret="D91CEB11EE62219CD91CEB11EE62219C"
SM2_privateKey="JShsBOJL0RgPAoPttEB1hgtPAvCikOl0V1oTOYL7k5U="

待加签串：
appid=19E179E5DC29C05E65B90CDE57A1C7E5&data={"user_id":"gt","face_id":"5ed21b1c262daabe314048f5"}&encType=plain&signType=SM2&timestamp=1591943910&version=1&key=D91CEB11EE62219CD91CEB11EE62219C

SHA256加签结果：
"10e13147546debbea157ec793170968c6c614f4eb13ccd9b7a9c193bf1b3bd78"

base64后结果：
"MTBlMTMxNDc1NDZkZWJiZWExNTdlYzc5MzE3MDk2OGM2YzYxNGY0ZWIxM2NjZDliN2E5YzE5M2JmMWIzYmQ3OA=="

SM2加签结果：


```

返回结果

| 参数      | 类型    | 说明                                                         | 示例  |
| --------- | ------- | ------------------------------------------------------------ | ----- |
| appId     | string  | 应用渠道编号                                                 |       |
| code      | string  | 接口返回状态代码                                             |       |
| signType  | string  | 签名算法，plain： 不用签名，SM2：使用SM2算法                 | plain |
| encType   | string  | 接口数据加密算法，目前不加密                                 | plain |
| success   | boolean | 成功与否                                                     |       |
| timestamp | int     | unix时间戳                                                   |       |
| data      | json    | 成功时返回结果数据；出错时，data.msg返回错误说明。详见具体接口 |       |

> 成功时：code为0， success为True，data内容见各接口定义；
>
> 出错时：code返回错误代码，具体定义见各接口说明

返回示例

```json
{
    "appId": "19E179E5DC29C05E65B90CDE57A1C7E5", 
    "code": 0, 
    "signType": "plain",
    "encType": "plain",
    "success": true,
    "timestamp": 1591943910,
    "data": {
       "msg": "success", 
       ...
    }
}
```

全局出错代码

| 编码 | 说明                               |
| ---- | ---------------------------------- |
| 9800 | 无效签名                           |
| 9801 | 签名参数有错误                     |
| 9802 | 调用时间错误，unixtime超出接受范围 |



### 2. 医疗文本NER

> 建议：输入文本不要含空格、回车换行、制表符等。逗号或句号之间的字数最好不大于100。
> 目前可识别：手术、解剖部位、药物、实验室检验、疾病和诊断、影像检查、症状。

请求URL

> http://127.0.0.1:5000/ner/ner

请求方式

> POST

输入参数

| 参数  | 必选 | 类型   | 说明               |
| ----- | ---- | ------ | ------------------ |
| text | 是   | string | 医疗文本 |

请求示例

```json
{
    "text": ",2009年12月底出现黑便,,于当地行胃镜检查并行病理检查示:叒胃体中下部溃疡"
}
```

返回结果

| 参数        | 必选 | 类型   | 说明             |
| ----------- | ---- | ------ | ---------------- |
| entities | 是   | string | 识别出实体清单 |
| + label |  | string | 实体类型 |
| + value |  | string | 实体文本 |
| + start_pos |  | int | 在原文中起始位置 |
| request_id  | 是   | string | 此次请求id       |

返回示例

```json
{
    "data": {
        "msg": "success",
        "entities": [
            {
                "label": "疾病和诊断",
                "value": "胃体中下部溃疡",
                "start_pos": 33
            }
        ],
        "request_id": "210629151110345e56759dbd0e74374e67f2225b7f1b"
    },
}
```

出错代码

| 编码 | 说明                              |
| ---- | --------------------------------- |
| 9001 | 缺少参数                          |

