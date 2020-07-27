# -*- coding: utf-8 -*-
# @Author   : chengnian920@gmail.com
# @Time     : 2020/7/19 11:09
# @File     : demo.py
import csv
import os
import random
import time
import requests
from lxml import etree
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

term = 'a'
url = r'https://pubmed.ncbi.nlm.nih.gov/'

session = requests.session()

user_agent_list = [
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.62 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36",
    "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)",
    "Mozilla/5.0 (Macintosh; U; PPC Mac OS X 10.5; en-US; rv:1.9.2.15) Gecko/20110303 Firefox/3.6.15",
]
headers = {'User-Agent': random.choice(user_agent_list)}

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


def parse(pmid, url):
    """
    解析html
    :param data: http response
    :return:
    """
    response = requests.get(url, headers=headers, timeout=600, verify=False)
    time.sleep(1)
    html = etree.HTML(response.content)
    try:
        full_text_links_list = html.xpath('//div[@class="full-view"]//div[@class="full-text-links-list"]/a')
        link = full_text_links_list[-1]
        if link.xpath('@data-ga-action="PMC"'):  # 优先选择PMC下载地址
            file_download_page_url = link.xpath('@href')[0]
            print('pmid:{} PMC下载页面：{}'.format(pmid, file_download_page_url))
            response_download_page = requests.get(file_download_page_url, headers=headers, timeout=300,
                                                  verify=False)
            html_download_page = etree.HTML(response_download_page.content)
            file_url = html_download_page.xpath('//div[@class="format-menu"]//a[contains(text(),"PDF")]/@href')
            if file_url:
                # download(pmid, download_host + file_url[0])
                return True
        elif link.xpath('@data-ga-action="Elsevier Science"'):  # Elsevier Science
            file_download_page_url = link.xpath('@href')[0]
            print('pmid:{}  Elsevier Science下载页面：{}'.format(pmid, file_download_page_url))
            pass  # todo  针对非PMC站点文章，获取下载地址url情况比较多，暂时没有处理非PMC站点文章
        elif link.xpath('@data-ga-action="Ediciones Doyma, S.L."'):  # Ediciones Doyma, S.L.
            file_download_page_url = link.xpath('@href')[0]
            print('pmid:{} Ediciones Doyma, S.L. 下载页面：{}'.format(pmid, file_download_page_url))
            pass
        elif link.xpath('@data-ga-action="Publishing M2Community"'):  # Publishing M2Community
            file_download_page_url = link.xpath('@href')[0]
            doi = file_download_page_url.split('/')[-1]
            url = 'https://www.e-ce.org/upload/pdf/' + doi.replace('.', '-') + '.pdf'
            print('pmid:{} Publishing M2Community下载页面：{}'.format(pmid, file_download_page_url))
            # self.download(pmid, url)  # todo  服务器url地址通用性不太好，没有使用
        else:
            file_download_page_url = link.xpath('@href')[0]
            print('pmid:{}非PMC站点请手动下载：{} 下载地址：{}'.format(pmid, response.url, file_download_page_url))
            return False
    except Exception as e:
        print('pmid:{}跳转下载页失败:{}'.format(pmid, e))


parse('32455846', 'https://pubmed.ncbi.nlm.nih.gov/32455846/')
# parse('32455846','https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7287808/')
