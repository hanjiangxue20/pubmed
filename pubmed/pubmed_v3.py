# -*- coding: utf-8 -*-
# @Author   : chengnian920@gmail.com
# @Time     : 2020/7/16 21:52
# @File     : pubmed.py
import random
import requests
import json
import time
import os
import csv
import logging
from logging.handlers import TimedRotatingFileHandler
import configparser
import threading
# import pandas as pd
from queue import Queue
from lxml import etree
from contextlib import closing
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

cf = configparser.RawConfigParser()
cf.read('config.ini', encoding="utf-8")
query_url = cf.get('Pubmed', 'query_url')
max_size = cf.get('Pubmed', 'max_size')
host = cf.get('Pubmed', 'host')
download_flag = cf.get('Pubmed', 'download_flag')
download_host = cf.get('Pubmed', 'download_host')
thread_num = cf.get('Pubmed', 'thread_num')
CRAWL_EXIT = False
PARSE_EXIT = False

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

if not os.path.exists('download'):
    os.mkdir('download')
if not os.path.exists('log'):
    os.mkdir('log')
# 创建一个日志logger
logger = logging.getLogger('mylogger')
logger.setLevel(logging.DEBUG)
handler_file = TimedRotatingFileHandler(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'log', 'log.log'),
                                        backupCount=7, interval=1, when='midnight')
handler_file.setLevel(logging.DEBUG)
handler_console = logging.StreamHandler()
handler_console.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s][%(thread)d][%(levelname)s] ## %(message)s')
handler_file.setFormatter(formatter)
handler_console.setFormatter(formatter)
logger.addHandler(handler_file)
logger.addHandler(handler_console)


class ThreadCrawl(threading.Thread):
    def __init__(self, search_queue, data_queue):
        super(ThreadCrawl, self).__init__()
        # 搜索结果队列
        self.search_queue = search_queue
        # 数据队列
        self.data_queue = data_queue
        # 请求报头
        self.headers = headers

    def run(self):
        while True:
            if self.search_queue.empty():
                break
            try:
                article = self.search_queue.get(False)
                if self.is_file_exist(article['PMID']):  # 已经下载过该文件，跳过
                    continue
                if article['is_free_resources']:
                    try:
                        logger.info(host + '/{}'.format(article['PMID']))
                        response = requests.get(host + '/{}'.format(article['PMID']), headers=headers, timeout=60,
                                                verify=False)  # 文章详情页
                        time.sleep(0.1)
                        self.data_queue.put({article['PMID']: response.content})
                    except Exception as e:
                        logger.error('跳转详情页失败:{}'.format(e))
                else:
                    logger.debug('论文pmid:{}不支持下载,地址:{}'.format(article['PMID'], host + '/{}'.format(article['PMID'])))
            except Exception as e:
                logger.error('craw error {}'.format(e))

    @staticmethod
    def save_result_to_csv(article):
        pass

    @staticmethod
    def is_file_exist(pmid):
        return os.path.exists(os.path.join("download", pmid + '.pdf'))


class ThreadParse(threading.Thread):
    def __init__(self, data_queue, output_csv, lock):
        super(ThreadParse, self).__init__()
        # 数据队列
        self.data_queue = data_queue
        # 保存解析后数据的文件名
        self.output_csv = output_csv
        # 锁
        self.lock = lock

    def run(self):
        while True:
            if self.data_queue.empty():
                break
            try:
                logger.info('剩余下载{}个文件，请稍后...'.format(self.data_queue.qsize()))
                data = self.data_queue.get(False)
                self.parse(data)
            except Exception as e:
                logger.error('解析失败:{}'.format(e))

    def parse(self, data):
        (pmid, html), = data.items()
        html = etree.HTML(html)
        try:
            file_download_page_url = html.xpath('//span[@class="identifier pmc"]/a/@href')[0]  # PMCID链接
            logger.info('pmid:{} 下载页面地址:{}'.format(pmid, file_download_page_url))
            response_download_page = requests.get(file_download_page_url, headers=headers, timeout=120, verify=False)
            time.sleep(0.1)
            html_download_page = etree.HTML(response_download_page.content)
            # file_url = html_download_page.xpath('//a[@id="jr-pdf-sw"]/@href')[0]
            file_url = html_download_page.xpath('//div[@id="rightcolumn"]/div[2]/div/ul/li[4]/a/@href')[0]
            self.download(pmid, download_host + file_url)
            # print("id:{} v:{}".format(pmid, download_host + file_url))
        except Exception as e:
            logger.error('pmid:{}跳转下载页失败error:{}'.format(pmid, e))

    def download(self, pmid, url):
        file_name = pmid + '.pdf'
        file_path = os.path.join('download', file_name)
        logger.info('准备下载论文pmid:{},下载地址:{}'.format(pmid, url))
        with closing(requests.get(url, stream=True, headers=headers, timeout=600, verify=False)) as r:
            time.sleep(0.1)
            r_code = r.status_code
            if r_code in (200, 299):
                try:
                    with open(file_path, 'wb') as f:
                        for data in r.iter_content(1024 * 1024):
                            # data = r.content
                            f.write(data)
                    logger.info('下载论文{}成功'.format(file_name))
                    return True
                except Exception as e:
                    logger.error('保存论文{}失败，原因{}'.format(file_name, e))
            else:
                logger.info('下载{}时服务器响应错误'.format(file_name))
                return False


def main():
    search_queue = Queue()
    data_queue = Queue()
    lock = threading.Lock()
    # output_csv = open('csv_article_' + time.strftime('%m%d%H%M%S', time.localtime()) + '.csv', 'w')
    output_csv=''
    # writer = csv.writer(output_csv)
    # writer.writerow(
    #     ["PMID", "Title", "Authors", "Citation", "First Author", "Journal/Book", "Publication Year", "status"])

    try:
        new_query_url = query_url + '&size={}'.format(max_size)
        logger.info(new_query_url)
        logger.info('正在检索链接...')
        response = requests.get(new_query_url, headers=headers, timeout=120, verify=False)
        time.sleep(0.1)
        html = etree.HTML(response.text)
        results = html.xpath('//div[@class="search-results-chunk results-chunk"]/article')
    except Exception as e:
        logger.error('Request error:{}'.format(e))
        results = []
    try:
        logger.info('总共查询到{}条记录！'.format(len(results)))
        for r in results:
            data_article_id = r.xpath('.//a[@class="docsum-title"]/@data-article-id')[0]
            # title = (''.join(r.xpath('.//a[@class="docsum-title"]//text()'))).strip()
            # authors = ''.join(r.xpath('.//span[@class="docsum-authors full-authors"]//text()'))
            # first_author = authors.split(',')[0]
            # full_journal_citation = ''.join(
            #     r.xpath('.//span[@class="docsum-journal-citation full-journal-citation"]//text()'))
            # short_journal_citation = ''.join(
            #     r.xpath('.//span[@class="docsum-journal-citation short-journal-citation"]//text()'))
            # journal_or_book, publication_year, _ = short_journal_citation.split('.')
            # publication_year = publication_year.split()[0]
            free_resources = r.xpath('.//span[@class="free-resources spaced-citation-item citation-part"]/text()')
            is_free_resources = True if free_resources else False

            result = {
                "PMID": data_article_id,
                # "title": title,
                # "authors": authors,
                # "citation": full_journal_citation,
                # "first_author": first_author,
                # "journal_or_book": journal_or_book,
                # "publication_year": publication_year,
                "is_free_resources": is_free_resources,
            }
            print(result)
            search_queue.put(result)
        threadcrawl = []
        for i in range(int(thread_num)):
            thread = ThreadCrawl(search_queue, data_queue)
            thread.start()
            threadcrawl.append(thread)

        for thread in threadcrawl:
            thread.join()

        logger.info("获取下载地址成功,准备下载...")
        threadparse = []
        for i in range(int(thread_num)):
            thread = ThreadParse(data_queue, output_csv, lock)
            thread.start()
            threadparse.append(thread)

        for thread in threadparse:
            thread.join()
        logger.info('文件下载执行完成！请到{}路径下查看。'.format(os.path.abspath('download')))

    except Exception as e:
        logger.error('解析失败:{}'.format(e))


if __name__ == '__main__':
    main()
