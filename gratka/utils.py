#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import logging
import unicodedata

import requests
from scrapper_helpers.utils import caching, key_sha1

try:
    from __builtin__ import unicode
except ImportError:
    unicode = lambda x, *args: x


log = logging.getLogger(__file__)


def html_decode(s):
    """
    Returns the ASCII decoded version of the given HTML string. This does
    NOT remove normal HTML tags like <p>.
    """
    html_codes = (
        ("'", '&#39;'),
        ('"', '&quot;'),
        ('>', '&gt;'),
        ('<', '&lt;'),
        ('&', '&amp;')
    )
    for code in html_codes:
        s = s.replace(code[1], code[0])
    return s


@caching(key_func=key_sha1)
def get_url_from_mapper(filters):
    """
    Sends a request to Gratka's URL mapper which returns a valid URL given the supplied key-value pairs
    :param filters: see :meth:`gratka.category.get_category` for reference
    :return: A valid Gratka.pl URL as string
    """
    paramlist = []
    for k, v in filters.items():
        if isinstance(v, list):
            for element in v:
                paramlist.append((k, str(element)))
        else:
            paramlist.append((k, str(v)))

    url = "http://www.gratka.pl/mapper/"

    payload = "\r\n".join([
        "------WebKitFormBoundary7MA4YWxkTrZu0gW\r\nContent-Disposition: form-data; name=\"{0}\"\r\n\r\n{1}"
        .format(p[0], p[1])
        for p in paramlist

    ])
    headers = {
        'content-type': "multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW",
        'cache-control': "no-cache",
    }
    response = requests.request("POST", url, data=payload.encode("utf-8"), headers=headers)
    return json.loads(response.text)["redirectUrl"]


def replace_all_in_list(list, dic):
    """
    This method returns the input list, but replaces its elements according to the input dictionary.
    :param list: input list
    :param dic: dictionary containing the changes. key is the character that's supposed to be changed and value is
    the desired value
    :rtype: list
    :return: List with the according elements replaced
    """
    for i, element in enumerate(list):
        list[i] = dic.get(element, element)
    return list


def replace_all(text, dic):
    """
    This method returns the input string, but replaces its characters according to the input dictionary.
    :param text: input string
    :param dic: dictionary containing the changes. key is the character that's supposed to be changed and value is
                the desired value
    :rtype: string
    :return: String with the according characters replaced
    """
    for i, j in dic.items():
        text = text.replace(i, j)
    return text


def normalize_text(text, lower=True, replace_spaces='_'):
    """
    This method returns the input string, but normalizes is it for use in the url.
    :param text: input string
    :rtype: string
    :return: Normalized string. lowercase, no diacritics, '-' instead of ' '
    """
    try:
        unicoded = unicode(text, 'utf8')
    except TypeError:
        unicoded = text
    if lower:
        unicoded = unicoded.lower()
    normalized = unicodedata.normalize('NFKD', unicoded)
    encoded_ascii = normalized.encode('ascii', 'ignore')
    decoded_utf8 = encoded_ascii.decode("utf-8")
    if replace_spaces:
        decoded_utf8 = decoded_utf8.replace(" ", replace_spaces)
    return decoded_utf8


def get_region_from_autosuggest(region_part):
    """
    This method makes a request to the Gratka api, asking for the best fitting region for the supplied region_part
    string.
    :param region_part: input string, it should be a part of an existing region in Poland, either city, street,
                        district or voivodeship
    :rtype: dict
    :return: A dictionary which contents depend on the API response.
    """
    if not region_part:
        return {}
    url = u"http://www.gratka.pl/b-dom/ajax/podpowiedzi-lokalizacja/?tekst={0}".format(region_part)
    response = json.loads(get_response_for_url(url).text)[0]

    region_dict = {}

    if "powiat" in response:
        region_dict["county"] = normalize_text(response["powiat"])
    if "miejscowosc" in response:
        region_dict["city"] = normalize_text(response["miejscowosc"])
    if "ulica" in response:
        region_dict["street"] = normalize_text(response["ulica"])
    if "dzielnica" in response:
        region_dict["district"] = normalize_text(response["dzielnica"])
    if "id_wojewodztwo" in response:
        region_dict["estate_region"] = response["id_wojewodztwo"]
    print(region_dict)
    return region_dict


def get_url(region, page=1, **filters):
    """
    This method builds a ready-to-use url based on the input parameters.
    :param region: see :meth:`gratka.category.get_category` for reference
    :param page: page number
    :param filters: see :meth:`gratka.category.get_category` for reference
    :rtype: string
    :return: the url
    """
    if not (
        'estate_region' in filters or
        'city' in filters or
        'street' in filters or
        'district' in filters or
        'county' in filters
    ):
        region_dict = get_region_from_autosuggest(region)
        filters = dict(list(filters.items()) + list(region_dict.items()))
    url = get_url_from_mapper(filters)
    page_position = (url.count(",") - 1) // 2 + 1
    if page_position > 0:
        url = url.split(",")
        url[1] += "," + str(page)
        url[page_position] += "," + "s"
        url = ",".join(url)
    else:
        url = url.split(".")
        url[-2] += ",," + str(page) + "," + "s"
        url = ".".join(url)
    return url


@caching(key_func=key_sha1)
def get_response_for_url(url):
    """
    :param url: an url, most likely from the :meth:`gratka.utils.get_url` method
    :return: a requests.response object
    """
    return requests.get(url)