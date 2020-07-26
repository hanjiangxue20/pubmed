# -*- coding: utf-8 -*-
# @Author   : chengnian920@gmail.com
# @Time     : 2020/7/19 11:09
# @File     : demo.py
import csv
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

path = 'csv_article_' + time.strftime('%m%d%H%M%S', time.localtime()) + '.csv'


def csv_dict_write(path, head=None, data=None):
    with open(path, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, head)
        writer.writeheader()
        writer.writerows(data)
        return True


head = ['Name', 'Age']

data = [
    {'Name': 'Keys', 'Age': 28},
    {'Name': 'HongPing', 'Age': 29},
    {'Name': 'WenChao', 'Age': 15}
]

data1 = [
    {'Name': 'Keys1', 'Age': 28},
    {'Name': 'HongPing1', 'Age': 29},
    {'Name': 'WenChao1', 'Age': 15}
]

f = open(path, 'a', encoding='utf-8', newline='')
writer = csv.DictWriter(f, head)
writer.writeheader()
for d in data:
    writer.writerow(d)

for d in data1:
    writer.writerow(d)
print('end')