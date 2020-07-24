#!/usr/bin/env python
# -*- coding:utf-8 -*-

# 使用了线程库
import threading
# 队列
from queue import Queue
# 解析库
from lxml import etree
# 请求处理
import requests
# json处理
import json
import time

total = 0


class ThreadCrawl(threading.Thread):
    def __init__(self, threadName, pageQueue, dataQueue):
        # threading.Thread.__init__(self)
        # 调用父类初始化方法
        super(ThreadCrawl, self).__init__()
        # 线程名
        self.threadName = threadName
        # 页码队列
        self.pageQueue = pageQueue
        # 数据队列
        self.dataQueue = dataQueue
        # 请求报头
        self.headers = {"User-Agent": "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0;"}

    def run(self):
        print("启动 " + self.threadName)
        while not CRAWL_EXIT:
            try:
                # 取出一个数字，先进先出
                # 可选参数block，默认值为True
                # 1. 如果对列为空，block为True的话，不会结束，会进入阻塞状态，直到队列有新的数据
                # 2. 如果队列为空，block为False的话，就弹出一个Queue.empty()异常，
                page = self.pageQueue.get(False)
                url = "http://www.qiushibaike.com/8hr/page/" + str(page) + "/"
                content = requests.get(url, headers=self.headers, verify=False).text
                # time.sleep(1)
                self.dataQueue.put(content)
                # print len(content)
            except Exception as e:
                print('craw error {}'.format(e))
        print("结束 " + self.threadName)


class ThreadParse(threading.Thread):
    def __init__(self, threadName, dataQueue, filename, lock):
        super(ThreadParse, self).__init__()
        # 线程名
        self.threadName = threadName
        # 数据队列
        self.dataQueue = dataQueue
        # 保存解析后数据的文件名
        self.filename = filename
        # 锁
        self.lock = lock

    def run(self):
        print("启动" + self.threadName)
        while not PARSE_EXIT:
            try:
                html = self.dataQueue.get(False)
                self.parse(html)
            except:
                pass
        print("退出" + self.threadName)

    def parse(self, html):
        # 解析为HTML DOM
        global total
        html = etree.HTML(html)
        result = html.xpath('//div[contains(@class,"recommend-article")]/ul')
        for site in result:
            try:
                imgUrl = site.xpath('.//img/@src')[0]
                title = site.xpath('.//img/@alt')[0]
                result = {
                    'imgUrl': imgUrl,
                    'title': title,
                }
                print(result)
                # with self.lock:
                #     # print 'write %s' % json.dumps(result)
                #     self.filename.write(json.dumps(result, ensure_ascii=False).encode('utf-8').strip() + b"\n")
                with self.lock:
                    total += 1

            except Exception as e:
                print('site in result', e)


CRAWL_EXIT = False
PARSE_EXIT = False


def main():
    # 页码的队列，表示20个页面
    pageQueue = Queue(5)
    # 放入1~10的数字，先进先出
    for i in range(1, 6):
        pageQueue.put(i)

    # 采集结果(每页的HTML源码)的数据队列，参数为空表示不限制
    dataQueue = Queue()

    filename = open("duanzi2.json", "a")
    # 创建锁
    lock = threading.Lock()

    # 三个采集线程的名字
    crawlList = ["采集线程1号", "采集线程2号", "采集线程3号"]
    # 存储三个采集线程的列表集合
    threadcrawl = []
    for threadName in crawlList:
        thread = ThreadCrawl(threadName, pageQueue, dataQueue)
        thread.start()
        threadcrawl.append(thread)

    # 三个解析线程的名字
    parseList = ["解析线程1号", "解析线程2号", "解析线程3号"]
    # 存储三个解析线程
    threadparse = []
    for threadName in parseList:
        thread = ThreadParse(threadName, dataQueue, filename, lock)
        thread.start()
        threadparse.append(thread)

    # 等待pageQueue队列为空，也就是等待之前的操作执行完毕
    while not pageQueue.empty():
        pass

    # 如果pageQueue为空，采集线程退出循环
    global CRAWL_EXIT
    CRAWL_EXIT = True

    print("pageQueue为空")

    for thread in threadcrawl:
        thread.join()
        print("1")

    while not dataQueue.empty():
        pass

    global PARSE_EXIT
    PARSE_EXIT = True

    for thread in threadparse:
        thread.join()
        print("2")

    with lock:
        # 关闭文件
        filename.close()
    print("谢谢使用！total:{}".format(total))


if __name__ == "__main__":
    main()
