from flask import Blueprint, render_template
import newspaper
import csv
import urllib
from urllib import request
from urllib.parse import urlparse
import textract
import os
from collections import OrderedDict
import datetime
from bs4 import BeautifulSoup
import re
from sqlalchemy.orm import object_session
from idetect.model import Content


def scrape_article(article):
    session = object_session(article)
    # Update the retrieval date and retrieval_attempts
    article.retrieval_date = datetime.datetime.now()
    article.retrieval_attempts += 1
    session.commit()
    # Attempt to scrape article
    content, publish_date, title, content_type, authors, domain = scrape(
        article.url)
    if content == 'retrieval_failed':  # If the scraper fails 'nicely', raise an Exception
        raise Exception("Retrieval Failed")
    else:  # Update the relevant attributes and create content
        article.domain = domain
        article.publication_date = publish_date
        article.title = title
        article.authors = authors
        content = Content(article=[article],
                          content=content, content_type=content_type)
        session.add(content)
        session.commit()


def scrape(url, scrape_pdfs=True):
    """
    Scrapes content and metadata from an url
    Parameters
    ----------
    url: the url to be scraped
    scrape_pdfs: determines whether pdf files will be scraped or not
                 default: True

    Returns
    -------
    article: An article object prepared by scraping the url.


    """
    pdf_check = is_pdf_consolidated_test(url)
    if pdf_check and scrape_pdfs:
        article = pdf_article(pdf_check)
        return article
    elif not pdf_check:
        article = html_article(url)
        return article
    else:
        pass


# PDF helper functions


def is_pdf_simple_tests(url):
    '''Test a url to see if it is a pdf by looking at url and content headers
    If so, return the relevant pdf url for parsing
    '''
    # Simple url-based test
    if re.search(r'\.pdf$', url):
        return url

    # Test based on headers
    try:
        page = request.urlopen(url)
        content_type = page.getheader('Content-Type')
        if content_type == 'application/pdf':
            return url
    except (urllib.error.HTTPError, urllib.error.URLError, UnicodeEncodeError, ValueError):
        pass


def is_pdf_iframe_test(url):
    '''Test a url to see if the page contains an iframe
    and if the iframe content is pdf or not; if True, return the pdf url
    '''
    try:
        page = request.urlopen(url)
        soup = BeautifulSoup(page, "html.parser")
        iframes = soup.find_all('iframe')
        if len(iframes) > 0:
            for frame in iframes:
                if 'src' in frame.attrs.keys():
                    src = frame.attrs['src']
                    # should probably replace with something more robust
                    if 'http' in src:
                        if is_pdf_simple_tests(src):
                            return src
    except (urllib.error.HTTPError, urllib.error.URLError, UnicodeEncodeError, ValueError):
        pass


def is_pdf_consolidated_test(url):
    '''Run a series of tests to determine if it is a pdf
    If True, return the relevant url
    '''

    # Carry out simple tests based upon url and content type
    pdf_attempt_1 = is_pdf_simple_tests(url)
    if pdf_attempt_1:
        return pdf_attempt_1

    # Carry out additional test based by looking for iframe
    pdf_attempt_2 = is_pdf_iframe_test(url)
    if pdf_attempt_2:
        return pdf_attempt_2

    return False


def remove_newline(text):
    ''' Removes new line and &nbsp characters.
    '''
    text = text.replace('\n', ' ')
    text = text.replace('\xa0', ' ')
    return text


def format_date(date_string):
    '''Formats date string from http headers
    Returns standardized date format as string
    '''
    try:
        dt = datetime.datetime.strptime(
            date_string, "%a, %d %b %Y %H:%M:%S %Z")
        formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, AttributeError):
        formatted_date = None
    return formatted_date


def html_article(url):
    """Downloads and extracts content plus metadata for html page
    Parameters
    ----------
    url: url of page to be scraped

    Returns
    -------
    article: An object of class Article containing the content and metadata.
    """

    a = newspaper.Article(url)
    a.download()
    if a.download_state == 2:
        a.parse()
        article_domain = a.source_url
        article_title = a.title
        article_authors = a.authors
        article_pub_date = a.publish_date
        article_text = remove_newline(a.text)
        # tag the type of article
        # currently default to text but should be able to determine img/video
        # etc
        article_content_type = 'text'
        return article_text, article_pub_date, article_title, article_content_type, article_authors, article_domain
    else:  # Temporary fix to deal with https://github.com/codelucas/newspaper/issues/280
        return "retrieval_failed", None, "", datetime.datetime.now(), "", ""


def get_pdf(url):
    ''' Takes a pdf url, downloads it and saves it locally.'''
    try:
        response = request.urlopen(url)  # not sure if this is needed?
        publish_date = response.getheader('Last-Modified')
        pdf_file = open('file_to_convert.pdf', 'wb')
        pdf_file.write(response.read())
        pdf_file.close()
        return os.path.join('./', 'file_to_convert.pdf'), publish_date
    except (urllib.error.HTTPError, urllib.error.URLError, UnicodeEncodeError, ValueError) as e:
        return '', ''


def get_body_text(url):
    ''' This function will extract all text from the url passed in
    '''
    filepath, publish_date = get_pdf(url)
    if filepath == '':
        return '', None
    else:
        text = str(textract.process(filepath, method='pdfminer'), 'utf-8')
        text = text.replace('\n', ' ')  # can replace with a call to
        text = text.replace('\xa0', ' ')  # the helper function.
        publish_date = format_date(publish_date)
        return text, publish_date


def pdf_article(url):
    try:
        article_text, article_pub_date = get_body_text(url)
        if article_text == '':
            return "retrieval_failed", None, "", datetime.datetime.now(), "", ""
        else:
            article_domain = urlparse(url).hostname
            article_content_type = 'pdf'
            # improve parsing of pdfs to extract these?
            article_title = ''
            article_authors = ''
            return article_text, article_pub_date, article_title, article_content_type, article_authors, article_domain
    except:
        return "retrieval_failed", None, "", datetime.datetime.now(), "", ""
