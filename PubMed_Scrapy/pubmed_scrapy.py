import requests
import re
import pandas as pd
import os
from tqdm import tqdm
import time
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup

"""
基于PubMed搜索作者名爬取结果paper的相关信息
"""


class Content:
    def __init__(self):
        self.resultDf = pd.DataFrame()

    def get_info(self, info):
        self.resultDf = self.resultDf.append(info, ignore_index=True)
        # print('get info successfully')

    def get_result(self):
        return self.resultDf


class Website:
    """网站结构基类"""

    def __init__(self, name, url, searchUrl, resultListing, resultUrl, absoluteUrl, titleTag, abstractTag,
                 keywordsTag, unitTag, authorsTag, periodicalNameTag, publishTimeTag, authorNsupTag):
        """

        :param name:            网站名称
        :param url:             网站URL
        :param searchUrl:       网站搜索界面的URL
        :param resultListing:   搜索可点击结果标签
        :param resultUrl:       可点击结果的URL
        :param absoluteUrl:     可点击结果是否为绝对地址
        :param titleTag:        获取文章标题的selector
        :param abstractTag:     获取文章摘要的selector
        :param authorNsupTag    作者名与上标的selector
        """
        self.name = name
        self.url = url
        self.searchUrl = searchUrl
        self.resultListing = resultListing
        self.resultUrl = resultUrl
        self.absoluteUrl = absoluteUrl
        self.titleTag = titleTag
        self.abstractTag = abstractTag
        self.keywordsTag = keywordsTag
        self.unitTag = unitTag
        self.authorsTag = authorsTag
        self.periodicalNameTag = periodicalNameTag
        self.publishTimeTag = publishTimeTag
        self.authorNsupTag = authorNsupTag


class WebCrawler:
    def __init__(self):
        pass

    @staticmethod
    def turn_page(url):
        """
        实现网页的搜索结果界面的翻页
        :param url: 搜索结果界面
        :return: list 储存所有结果界面的bs列表
        """
        bses = []
        driver = webdriver.Firefox(executable_path='../driver/geckodriver')
        driver.get(url)
        while True:
            try:
                time.sleep(1)
                bs = BeautifulSoup(driver.page_source, 'html.parser')
                bses.append(bs)
                nextButton = driver.find_element_by_css_selector('div.pagination:nth-child(2) > a:nth-child(4)')
                nextButton.click()
                time.sleep(2)
            except NoSuchElementException:
                driver.close()
                break

        return bses

    @staticmethod
    def get_page(url):
        session = requests.Session()
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
                                        AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36'}
        try:
            req = session.get(url, headers=headers)
        except requests.exceptions.RequestException:
            return None
        bs = BeautifulSoup(req.text, 'html.parser')
        return bs

    @staticmethod
    def safe_get(pageObj, selector):
        selectedElems = pageObj.select(selector)
        if selectedElems is not None and len(selectedElems) > 0:
            return '\n'.join([selectedElem.get_text() for selectedElem in selectedElems])
        return ''

    @staticmethod
    def get_unit(units, targetAuthor):
        unitDic = dict()
        numbers = []
        infos = []
        unit = []
        # print(targetAuthor)
        try:
            for number in units.find_all('dt'):
                numbers.append(number.get_text())
            for info in units.find_all('dd'):
                infos.append(info.get_text())
            for num, info in zip(numbers, infos):
                unitDic[num] = info
            for target in targetAuthor[0].split(','):
                unit.append(unitDic[target])
            unit = ','.join(unit)
        except AttributeError:
            print('论文无单位记录')
            unit = ''
        except KeyError:
            print('目标作者无对应单位')
            unit = ''
        except IndexError:
            print('未找到指定作者名')
            unit = ''
        except Exception as e:
            print("发生未知错误{}".format(e))
            unit = ''
        return unit

    def search(self, topic, site, siteName, doctorName):
        """
        根据主题搜索网站并记录找到的所有页面
        :param topic:   搜索的主题
        :param site:    Website对象
        :param siteName: 医生在搜索结果下的名字
        :param doctorName: 医生中文名
        """
        bses = self.turn_page(site.searchUrl + topic)
        content = Content()
        for bs in bses:
            if bs is None:
                print('获取目标网页出现错误')
                return
            searchResults = bs.select(site.resultListing)
            for result in tqdm(searchResults):
                # 获取搜索结果URL
                url = result.select(site.resultUrl)[0].attrs["href"]
                if site.absoluteUrl:
                    bs = self.get_page(url)
                else:
                    bs = self.get_page(site.url + url)
                if bs is None:
                    print("Something was wrong with that page or Url. Skipping")
                    return
                title = self.safe_get(bs, site.titleTag)
                abstract = self.safe_get(bs, site.abstractTag)
                periodicalName = self.safe_get(bs, site.periodicalNameTag)
                keywords = self.safe_get(bs, site.keywordsTag)
                publishTime = self.safe_get(bs, site.publishTimeTag)
                timeRegex = re.compile(r'(\d{4}\s[\w]{1,3}\s\d+|\d{4}\s[\w]{1,3})')  # 正则日期形如"2018 Jul 3"或"2018 Jun"
                publishTime = timeRegex.findall(publishTime)
                try:
                    publishTime = publishTime[0]
                except IndexError:
                    publishTime = ''
                author = self.safe_get(bs, site.authorsTag)
                author = ','.join(author.split('\n'))
                authors = self.safe_get(bs, site.authorNsupTag)
                authorsRegex = re.compile(r'(?<={}).*?(?=,\s|\.)'.format(siteName))  # 正则目标医生角标
                targetAuthor = authorsRegex.findall(authors)
                units = bs.select_one(site.unitTag)
                unit = self.get_unit(units, targetAuthor)
                if title != '' and author != '':
                    infoDic = {'医生名': doctorName,
                               '论文显示名': siteName,
                               '文章标题': title,
                               '作者': author,
                               '摘要': abstract,
                               '链接': site.url + url,
                               '期刊名': periodicalName,
                               '发表日期': publishTime,
                               '关键词': keywords,
                               '单位': unit}
                    content.get_info(infoDic)
        return content.get_result()


if __name__ == '__main__':
    crawler = WebCrawler()
    website = Website(url='https://www.ncbi.nlm.nih.gov',
                      name='ncbi',
                      searchUrl='https://www.ncbi.nlm.nih.gov/pubmed/?term=',
                      resultListing='div.rprt',
                      resultUrl='div.rslt a',
                      absoluteUrl=False,
                      titleTag='div.rprt_all h1',
                      abstractTag='div.abstr div',
                      keywordsTag='div.keywords p',
                      periodicalNameTag='div.cit a',
                      publishTimeTag='div.cit',
                      authorsTag='div.auths a',
                      authorNsupTag='div.auths',
                      unitTag='div.afflist')

    finalResult = pd.DataFrame()
    paperResult = crawler.search('Hue+yue', website, 'Yue H', 'Yue Hua')
    paperResult.to_excel('result.xlsx', index=False)
