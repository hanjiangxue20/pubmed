# -*- coding: utf-8 -*-
# @Author   : chengnian920@gmail.com
# @Time     : 2020/7/19 11:09
# @File     : demo.py
import os
import time
import requests
from lxml import etree

term = 'a'
url = r'https://pubmed.ncbi.nlm.nih.gov/'

session = requests.session()

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36',
}

response = session.get(url + '?term=' + term + '&size=200', headers=headers, verify=False)
html = etree.HTML(response.text)
results = html.xpath('//div[@class="search-results-chunk results-chunk"]/article')
print(len(results))

cookiejar = response.cookies
cookiedict = requests.utils.dict_from_cookiejar(cookiejar)
print(cookiedict)
# headers.update('Cookie':cookiedict)

print('term={0}&schema={1}&page={2}&no-cache={3}&csrfmiddlewaretoken={4}'.format(term, 'all', 2,
                                                                                 int(time.time() * 1000), ''))
res = session.post('https://pubmed.ncbi.nlm.nih.gov/more/',
                   data='term={0}&schema={1}&page={2}&no-cache={3}&csrfmiddlewaretoken={4}'.format(term, 'all', 2,
                                                                                                   int(
                                                                                                       time.time() * 1000),
                                                                                                   ''),
                   headers=headers,
                   cookies=cookiedict,
                   verify=False)

# print(res.text)
# print(res.status_code)


print(os.path.exists(os.path.join('download','32376397.pdf')))