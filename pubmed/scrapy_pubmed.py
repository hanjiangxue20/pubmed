# -*- coding: utf-8 -*-
# @Author   : chengnian920@gmail.com
# @Time     : 2020/7/19 21:09
# @File     : scrapy_pubmed.py
import configparser
import threading
import time
import json
from queue import Queue

import requests
from lxml import etree

data_queue = Queue()
exitFlag_Parser = False
lock = threading.Lock()
total = 0

cf = configparser.ConfigParser()
cf.read('config.ini', encoding="utf-8")
query_url = cf.get('Pubmed', 'query_url')
max_size = cf.get('Pubmed', 'max_size')
host = cf.get('Pubmed', 'host')
download_flag = cf.get('Pubmed', 'download_flag')
download_host = cf.get('Pubmed', 'download_host')

class PubmedSpiderThread(threading.Thread):
    """
    抓取线程类
    """

    def __init__(self, threadID, queue):
        super(PubmedSpiderThread, self).__init__()
        self.threadID = threadID
        self.queue = queue

    def run(self):
        print('Starting ' + self.threadID)
        self.spider()
        print('Exiting ', self.threadID)

    def spider(self):
        while True:
            if self.queue.empty():
                break
            else:
                page = self.queue.get()
                print('spider=', self.threadID, ',page=', str(page))
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36',
                    'Accept-Language': 'zh-CN,zh;q=0.8'
                }
                timeout = 4
                while timeout > 0:
                    timeout -= 1
                    try:
                        response = requests.get(query_url, headers=headers)
                        data_queue.put(response.text)
                        break
                    except Exception as e:
                        print('Error:', e)
                if timeout < 0:
                    print('time out', query_url)


class PubmedParserThread(threading.Thread):
    """
    页面解析类
    """

    def __init__(self, threadID, queue, lock, file):
        self.threadID = threadID
        self.queue = queue
        self.lock = lock
        self.file = file
        super(PubmedParserThread, self).__init__()

    def run(self):
        print('Start parser ', self.threadID)
        global total, exitFlag_Parser
        while not exitFlag_Parser:
            try:
                item = self.queue.get(block=False)
                if not item:
                    pass
                self.paser_data(item)
                self.queue.task_done()
                print('Thread paser=', self.threadID, ',total=', total)
            except Exception as e:
                print('Error:{}'.format(e))

    def paser_data(self, item):
        global total
        try:
            html = etree.HTML(item)
            result = html.xpath('//div[contains(@class,"recommend-article")]')
            for site in result:
                try:
                    imgUrl = site.xpath('.//img/@src')[0]
                    title = site.xpath('.//h2')[0].text
                    content = site.xpath('.//div[@class="content"]/span')[0].text.strip()
                    vote = None
                    comments = None
                    try:
                        vote = site.xpath('.//i')[0].text
                        comments = site.xpath('.//i')[1].text
                    except:
                        pass
                    result = {
                        'imgUrl': imgUrl,
                        'title': title,
                        'content': content,
                        'vote': vote,
                        'comments': comments,
                    }

                    with self.lock:
                        # print 'write %s' % json.dumps(result)
                        self.f.write(json.dumps(result, ensure_ascii=False).encode('utf-8') + "\n")

                except Exception as e:
                    print('site in result', e)
        except Exception as e:
            print('parse_data', e)

        with self.lock:
            total += 1


def main():
    output = open('data.json', 'a')
    pageQueue = Queue(50)
    for page in range(1, 2):
        pageQueue.put(page)
        # 初始化采集线程
    crawlthreads = []
    crawlList = ["crawl-1", "crawl-2", "crawl-3"]

    for threadID in crawlList:
        thread = PubmedSpiderThread(threadID, pageQueue)
        thread.start()
        crawlthreads.append(thread)
    print('craw end')
    # 初始化解析线程parserList
    parserthreads = []
    parserList = ["parser-1", "parser-2", "parser-3"]
    # 分别启动parserList
    for threadID in parserList:
        thread = PubmedParserThread(threadID, data_queue, lock, output)
        thread.start()
        parserthreads.append(thread)

    # 等待队列清空
    while not pageQueue.empty():
        pass

    # 等待所有线程完成
    for t in crawlthreads:
        t.join()

    while not data_queue.empty():
        pass
    # 通知线程是时候退出

    exitFlag_Parser = True

    for t in parserthreads:
        t.join()
    print("Exiting Main Thread")
    with lock:
        output.close()


if __name__ == '__main__':
    main()
