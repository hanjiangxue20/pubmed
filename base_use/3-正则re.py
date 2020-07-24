# -*- coding: utf-8 -*-
# @Author   : chengnian920@gmail.com
# @Time     : 2020/7/16 17:53
# @File     : 3-正则re.py

import json
import bs4
import requests


def tencent():
    url = r"https://careers.tencent.com/search.html?&start=10#a"
    user_agent = 'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT6.1;Trident / 5.0'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers)
    print(response.text)

    # create css selector


if __name__ == '__main__':
    tencent()
