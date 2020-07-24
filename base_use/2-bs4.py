# -*- coding: utf-8 -*-
# @Author   : chengnian920@gmail.com
# @Time     : 2020/7/16 17:46
# @File     : 2-bs4.py
import json
import bs4
import requests
from lxml import etree

url = 'http://www.qiushibaike.com/8hr/page/' + str(1) + '/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.8'
}
try:
    response = requests.get(url, headers=headers)
    html = etree.HTML(response.text)
    result = html.xpath('//div[contains(@class,"recommend-article")]/ul/li')
    print(result)
    for r in result:
        imgUrl=r.xpath('.//img/@src')[0]
        print(imgUrl)
except Exception as e:
    print('Error:', e)
