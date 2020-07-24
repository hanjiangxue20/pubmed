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
from urllib import parse
from contextlib import closing

file_queue = Queue()
article_queue = Queue()
lock = threading.Lock()
total = 0

cf = configparser.RawConfigParser()
cf.read('config.ini', encoding="utf-8")
query_url = cf.get('Pubmed', 'query_url')
max_size = cf.get('Pubmed', 'max_size')
host = cf.get('Pubmed', 'host')
download_flag = cf.get('Pubmed', 'download_flag')
download_host = cf.get('Pubmed', 'download_host')
thread_num = cf.get('Pubmed', 'thread_num')
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36',
}
session = requests.session()

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


def download(file_name, file_url):
    if os.path.isfile(os.path.join('download', file_name)):
        return  # 已经下载过该文件，跳过
    with closing(requests.get(file_url, stream=True, headers=headers, timeout=60, verify=False)) as r:
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


def parser_loop():
    while True:
        if not article_queue.empty():
            break
        article = article_queue.get()
        print(article['PMID'])
        if article['is_free_resources']:
            try:
                print('enter parser')
                response = session.get(host + '/{}'.format(article['PMID']), headers=headers, verify=False)
                html = etree.HTML(response.text)
                file_download_page_url = html.xpath('//span[@class="identifier pmc"]/a/@href')[0]  # PMCID
                response_download_page = session.get(file_download_page_url, headers=headers, verify=False)
                html_download_page = etree.HTML(response_download_page.text)
                # file_url = html_download_page.xpath('//a[@id="jr-pdf-sw"]/@href')[0]
                file_url = html_download_page.xpath('//div[@id="rightcolumn"]/div[2]/div/ul/li[4]/a/@href')[0]
                print("id:{} v:{}".format(article['PMID'], file_url))
                file_queue.put({article['PMID']: download_host + file_url})
            except Exception as e:
                logger.error('跳转下载页失败:{}'.format(e))
                break


def download_loop():
    while True:
        if not file_queue.empty():
            break
        file_dict = file_queue.get()
        (file_name, file_url), = file_dict.items()
        try:
            logger.info('start download {}.pdf:{}'.format(file_name, file_url))
            download(file_name + '.pdf', file_url)
            logger.info('download {}.pdf success'.format(file_name))
        except Exception as e:
            logger.error('download {} failed {}'.format(file_name, e))
            break


def pubmed_spider():
    try:
        new_query_url = query_url + '&size={}'.format(max_size)
        logger.info(new_query_url)
        response = session.get(new_query_url, headers=headers, verify=False)
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
            # print("id:{} v:{}".format(data_article_id, data_full_article_url))
            article_queue.put({
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
            })
        print('article_queue:{}'.format(article_queue.qsize()))
        print(article_queue.get()['PMID'])

        if download_flag:
            logger.info('获取下载链接...')
            parser_thread = threading.Thread(target=parser_loop, )
            parser_thread.start()
            parser_thread.join()

            threads = []
            for i in range(int(thread_num)):
                download_thread = threading.Thread(target=download_loop, )
                download_thread.start()
                threads.append(download_thread)
            for t in threads:
                t.join()

        if file_queue.empty():
            logger.info('下载完成')
    except Exception as e:
        logger.error('解析失败:{}'.format(e))


class ThreadCrawl(threading.Thread):
    def __init__(self, queue):
        super(ThreadCrawl, self).__init__()
        self.queue = queue


if __name__ == '__main__':
    pubmed_spider()
