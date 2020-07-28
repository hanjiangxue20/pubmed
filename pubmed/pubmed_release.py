# -*- coding: utf-8 -*-
# @Author   : chengnian920@gmail.com
# @Time     : 2020/7/18 21:52
# @File     : pubmed.py
import random
import requests
import time
import os
import csv
import logging
from logging.handlers import TimedRotatingFileHandler
import configparser
import threading
from queue import Queue
from lxml import etree
from contextlib import closing
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

cf = configparser.RawConfigParser()
cf.read('config.ini', encoding="utf-8")
max_size = cf.get('Pubmed', 'max_size')
host = cf.get('Pubmed', 'host')
download_host = cf.get('Pubmed', 'download_host')
thread_num = int(cf.get('Pubmed', 'thread_num'))
timeout = int(cf.get('Pubmed', 'timeout'))
is_output_csv = cf.get('Pubmed', 'is_output_csv')

user_agent_list = [
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/64.0.3282.186 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.62 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36",
    "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)",
    "Mozilla/5.0 (Macintosh; U; PPC Mac OS X 10.5; en-US; rv:1.9.2.15) Gecko/20110303 Firefox/3.6.15",
]
headers = {'User-Agent': random.choice(user_agent_list), }

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
        """
        构造爬取线程
        :param search_queue: 搜索结果队列
        :param data_queue: 数据队列
        """
        super(ThreadCrawl, self).__init__()
        self.search_queue = search_queue
        self.data_queue = data_queue
        self.headers = headers

    def run(self):
        while True:
            if self.search_queue.empty():
                break
            try:
                article = self.search_queue.get(False)
                if self.is_file_exist(article['PMID']):  # 已经下载过该文件，跳过
                    continue
                if article['Is_free_resources']:
                    try:
                        response = requests.get(host + '/{}'.format(article['PMID']), headers=self.headers,
                                                timeout=timeout,
                                                verify=False)  # 文章详情页
                        self.data_queue.put({article['PMID']: response})
                    except Exception as e:
                        logger.error('pmid:{}跳转详情页失败:{}'.format(article['PMID'], e))
                else:
                    logger.info('论文pmid:{}不支持下载,地址:{}'.format(article['PMID'], host + '/{}'.format(article['PMID'])))
            except Exception as e:
                logger.error('爬取异常：{}'.format(e))

    @staticmethod
    def is_file_exist(pmid):
        return os.path.exists(os.path.join("download", pmid + '.pdf'))


class ThreadParse(threading.Thread):
    def __init__(self, data_queue, output_csv, lock):
        """
        构造解析线程
        :param data_queue: 数据队列
        :param output_csv: 结果输出csv
        :param lock: 锁
        """
        super(ThreadParse, self).__init__()
        self.data_queue = data_queue
        self.output_csv = output_csv
        self.lock = lock
        self.headers = headers

    def run(self):
        while True:
            if self.data_queue.empty():
                break
            try:
                data = self.data_queue.get(False)
                self.parse(data)
            except Exception as e:
                logger.error('解析失败:{}'.format(e))

    def parse(self, data):
        """
        解析html
        :param data: http response
        :return:
        """
        (pmid, response), = data.items()
        html = etree.HTML(response.content)
        try:
            full_text_links_list = html.xpath('//div[@class="full-view"]//div[@class="full-text-links-list"]/a')
            if full_text_links_list:
                link = full_text_links_list[-1]
                if link.xpath('@data-ga-action="PMC"'):  # 优先选择PMC下载地址
                    file_download_page_url = link.xpath('@href')[0]
                    response_download_page = requests.get(file_download_page_url, headers=self.headers, timeout=timeout,
                                                          verify=False)
                    time.sleep(random.randint(1, 5) * 0.1)
                    html_download_page = etree.HTML(response_download_page.content)
                    file_url = html_download_page.xpath('//div[@class="format-menu"]//a[contains(text(),"PDF")]/@href')
                    if file_url:
                        self.download(pmid, download_host + file_url[0])
                        return True
                elif link.xpath('@data-ga-action="Elsevier Science"'):  # Elsevier Science
                    file_download_page_url = link.xpath('@href')[0]
                    logger.info('pmid:{}  Elsevier Science下载页面：{}'.format(pmid, file_download_page_url))
                    pass  # todo  针对非PMC站点文章，获取下载地址url情况比较多，暂时没有处理非PMC站点文章
                elif link.xpath('@data-ga-action="Ediciones Doyma, S.L."'):  # Ediciones Doyma, S.L.
                    file_download_page_url = link.xpath('@href')[0]
                    logger.info('pmid:{} Ediciones Doyma, S.L. 下载页面：{}'.format(pmid, file_download_page_url))
                    pass
                elif link.xpath('@data-ga-action="Publishing M2Community"'):  # Publishing M2Community
                    file_download_page_url = link.xpath('@href')[0]
                    doi = file_download_page_url.split('/')[-1]
                    url = 'https://www.e-ce.org/upload/pdf/' + doi.replace('.', '-') + '.pdf'
                    logger.info('pmid:{} Publishing M2Community下载页面：{}'.format(pmid, file_download_page_url))
                    # self.download(pmid, url)  # todo  服务器url地址通用性不太好，没有使用
                else:
                    file_download_page_url = link.xpath('@href')[0]
                    logger.info('pmid:{}非PMC站点请手动下载：{} 下载地址：{}'.format(pmid, response.url, file_download_page_url))
                    return False
            else:
                logger.error('pmid:{}获取下载地址为空'.format(pmid))
        except Exception as e:
            logger.error('pmid:{}跳转下载页失败:{}'.format(pmid, e))

    def download(self, pmid, url):
        """
        下载文件
        :param pmid: pmid
        :param url: 下载地址url
        :return:
        """
        file_name = pmid + '.pdf'
        file_path = os.path.join('download', file_name)
        logger.info('准备下载论文pmid:{},下载地址:{}'.format(pmid, url))
        with closing(requests.get(url, stream=True, headers=self.headers, timeout=timeout + 300, verify=False)) as r:
            if r.status_code in (200, 299):
                try:
                    with open(file_path, 'wb') as f:
                        f.write(r.content)
                    logger.info('下载论文{}成功'.format(file_name))
                    return True
                except Exception as e:
                    logger.error('保存论文{}失败，原因{}'.format(file_name, e))
            else:
                logger.warning('下载{}时服务器响应错误'.format(file_name))
                return False

    @staticmethod
    def save_to_csv(self):
        pass


def main(query_url_input=None):
    """
    主函数
    :param query_url_input: PubMed  URL
    :return:
    """
    logger.info('复制PubMed查询链接，其它参数可到config.ini参照修改^_^')
    global f, writer
    search_queue = Queue()
    data_queue = Queue()
    lock = threading.Lock()
    output_csv = ''
    if is_output_csv == 'yes':
        output_file = 'article_' + time.strftime('%m%d%H%M%S', time.localtime()) + '.csv'
        f = open(output_file, 'a', encoding='utf-8', newline='')
        head = ["PMID", "Title", "Authors", "Citation", "First_author", "Journal_or_book", "Publication_year",
                "Is_free_resources"]
        writer = csv.DictWriter(f, head)
        writer.writeheader()
    try:
        if query_url_input:
            query_url = query_url_input
        else:
            query_url = cf.get('Pubmed', 'query_url')
        new_query_url = query_url + '&size={}'.format(max_size)
        logger.info('检索地址：{}'.format(new_query_url))
        logger.info('正在检索链接...')
        response = requests.get(new_query_url, headers=headers, timeout=timeout, verify=False)
        html = etree.HTML(response.text)
        results = html.xpath('//div[@class="search-results-chunk results-chunk"]/article')
    except Exception as e:
        logger.error('Request error:{}'.format(e))
        results = []
    try:
        logger.info('总共查询到{}条记录，正在解析中...'.format(len(results)))
        for r in results:
            data_article_id = r.xpath('.//a[@class="docsum-title"]/@data-article-id')[0]
            title = (''.join(r.xpath('.//a[@class="docsum-title"]//text()'))).strip()
            authors = ''.join(r.xpath('.//span[@class="docsum-authors full-authors"]//text()'))
            first_author = authors.split(',')[0]
            full_journal_citation = ''.join(
                r.xpath('.//span[@class="docsum-journal-citation full-journal-citation"]//text()'))
            short_journal_citation = ''.join(
                r.xpath('.//span[@class="docsum-journal-citation short-journal-citation"]//text()'))
            journal_or_book, publication_year, _ = short_journal_citation.split('.')
            publication_year = publication_year.split()[0]
            free_resources = r.xpath('.//span[@class="free-resources spaced-citation-item citation-part"]/text()')
            is_free_resources = True if free_resources else False

            result = {
                "PMID": data_article_id,
                "Title": title,
                "Authors": authors,
                "Citation": full_journal_citation,
                "First_author": first_author,
                "Journal_or_book": journal_or_book,
                "Publication_year": publication_year,
                "Is_free_resources": is_free_resources,
            }
            search_queue.put(result)
            if is_output_csv == 'yes':
                writer.writerow(result)
        if is_output_csv == 'yes':
            f.close()
        threadcrawl = []
        for i in range(thread_num):
            thread = ThreadCrawl(search_queue, data_queue)
            thread.start()
            threadcrawl.append(thread)

        for thread in threadcrawl:
            thread.join()

        logger.info("准备执行下载操作...")
        threadparse = []
        for i in range(thread_num):
            thread = ThreadParse(data_queue, output_csv, lock)
            thread.start()
            threadparse.append(thread)

        for thread in threadparse:
            thread.join()
        logger.info('文件下载执行完成！请到{}路径下查看!'.format(os.path.abspath('download')))

    except Exception as e:
        logger.error('解析失败:{}'.format(e))


if __name__ == '__main__':
    while True:
        query_url_input = input('请复制PubMed查询网址链接后回车:')
        main(query_url_input)
