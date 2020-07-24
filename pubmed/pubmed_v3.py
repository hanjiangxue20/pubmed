# -*- coding: utf-8 -*-
# @Author   : chengnian920@gmail.com
# @Time     : 2020/7/16 21:52
# @File     : pubmed.py
import requests
import json
import time
import os
import logging
from logging.handlers import TimedRotatingFileHandler
import configparser
import threading
# import pandas as pd
from queue import Queue
from lxml import etree
from contextlib import closing

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

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36',
}

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
        while not CRAWL_EXIT:
            try:
                article = self.search_queue.get(False)
                if article['is_free_resources']:
                    try:
                        # 文章详情页
                        response = requests.get(host + '/{}'.format(article['PMID']), headers=headers, verify=False)
                        self.data_queue.put({article['PMID']: response.text})
                    except Exception as e:
                        logger.error('跳转详情页失败:{}'.format(e))
                else:
                    continue
            except Exception as e:
                print('craw error {}'.format(e))

    def get_file_url(self):
        article = self.search_queue.get(False)
        if article['is_free_resources']:
            try:
                response = requests.get(host + '/{}'.format(article['PMID']), headers=headers, verify=False)
                html = etree.HTML(response.text)
                file_download_page_url = html.xpath('//span[@class="identifier pmc"]/a/@href')[0]  # PMCID链接
                response_download_page = requests.get(file_download_page_url, headers=headers, verify=False)
                html_download_page = etree.HTML(response_download_page.text)
                file_url = html_download_page.xpath('//a[@id="jr-pdf-sw"]/@href')[0]
                self.data_queue.put({article['PMID']: download_host + file_url})
                print("id:{} v:{}".format(article['PMID'], download_host + file_url))
            except Exception as e:
                logger.error('跳转下载页失败:{}'.format(e))


class ThreadParse(threading.Thread):
    def __init__(self, data_queue, filename, lock):
        super(ThreadParse, self).__init__()
        # 数据队列
        self.data_queue = data_queue
        # 保存解析后数据的文件名
        self.filename = filename
        # 锁
        self.lock = lock

    def run(self):
        while not PARSE_EXIT:
            try:
                data = self.data_queue.get(False)
                self.parse(data)
            except:
                pass

    def parse(self, data):
        # 解析为HTML DOM
        (pmid, html), = data.items()
        html = etree.HTML(html)
        try:
            file_download_page_url = html.xpath('//span[@class="identifier pmc"]/a/@href')[0]  # PMCID链接
            response_download_page = requests.get(file_download_page_url, headers=headers, verify=False)
            html_download_page = etree.HTML(response_download_page.text)
            file_url = html_download_page.xpath('//a[@id="jr-pdf-sw"]/@href')[0]
            self.download(pmid, download_host + file_url)
            print("id:{} v:{}".format(pmid, download_host + file_url))
            # self.download_queue.put({pmid: download_host + file_url})
        except Exception as e:
            logger.error('跳转下载页失败:{}'.format(e))

    def download(self, pmid, url):
        file_name = pmid + '.pdf'
        if os.path.isfile(os.path.join('download', file_name)):
            return  # 已经下载过该文件，跳过
        with closing(requests.get(url, stream=True, headers=headers, timeout=60, verify=False)) as r:
            r_code = r.status_code
            if r_code in (200, 299):
                try:
                    with open(os.path.join('download', file_name), 'wb') as f:
                        for data in r.iter_content(1024):
                            f.write(data)
                except Exception as e:
                    logger.error('save file {} failed'.format(file_name))
            else:
                logger.info('download file {} failed'.format(file_name))


#
# class ThreadDownload(threading.Thread):
#     def __init__(self,download_queue):
#         super(ThreadDownload, self).__init__()


def main():
    search_queue = Queue()
    data_queue = Queue()
    lock = threading.Lock()
    try:
        new_query_url = query_url + '&size={}'.format(max_size)
        logger.info(new_query_url)
        response = requests.get(new_query_url, headers=headers, verify=False)
        html = etree.HTML(response.text)
        results = html.xpath('//div[@class="search-results-chunk results-chunk"]/article')
    except Exception as e:
        logger.error('Request error:{}'.format(e))
        results = []
    try:
        logger.info('总共查询到{}条记录！'.format(len(results)))
        for r in results:
            ref = r.xpath('.//a[@class="docsum-title"]/@ref')[0]
            data_full_article_url = r.xpath('.//a[@class="docsum-title"]/@data-full-article-url')[0]
            data_article_id = r.xpath('.//a[@class="docsum-title"]/@data-article-id')[0]
            title = (''.join(r.xpath('.//a[@class="docsum-title"]//text()'))).strip()
            authors = ''.join(r.xpath('.//span[@class="docsum-authors full-authors"]//text()'))
            full_journal_citation = ''.join(
                r.xpath('.//span[@class="docsum-journal-citation full-journal-citation"]//text()'))
            short_journal_citation = ''.join(
                r.xpath('.//span[@class="docsum-journal-citation short-journal-citation"]//text()'))
            journal_or_book, publication_year, _ = short_journal_citation.split('.')
            free_resources = r.xpath('.//span[@class="free-resources spaced-citation-item citation-part"]/text()')
            is_free_resources = True if free_resources else False
            result = {
                "PMID": data_article_id,
                "title": title,
                "authors": authors,
                "citation": full_journal_citation,
                "first_author": authors.split(',')[0],
                "journal_or_book": journal_or_book,
                "publication_year": publication_year.split()[0],
                "ref": ref,
                "data_full_article_url": data_full_article_url,
                "is_free_resources": is_free_resources,
            }
            search_queue.put(result)
            print(result)
        threadcrawl = []
        for i in range(int(thread_num)):
            thread = ThreadCrawl(search_queue, data_queue)
            thread.start()
            threadcrawl.append(thread)
        threadparse = []
        for i in range(int(thread_num)):
            thread = ThreadParse(data_queue, 'demo', lock)
            thread.start()
            threadparse.append(thread)

        # 等待search_queue队列为空，也就是等待之前的操作执行完毕
        while not search_queue.empty():
            pass

        # 如果search_queue为空，采集线程退出循环
        global CRAWL_EXIT
        CRAWL_EXIT = True
        print("search_queue为空")

        for thread in threadcrawl:
            thread.join()
            print("1")

        while not data_queue.empty():
            pass

        global PARSE_EXIT
        PARSE_EXIT = True

        for thread in threadparse:
            thread.join()
            print("2")
        print('end')

    except Exception as e:
        logger.error('解析失败:{}'.format(e))


if __name__ == '__main__':
    main()
