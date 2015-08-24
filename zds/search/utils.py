# coding: utf-8

import os
import zipfile
import json as json_reader
from bs4 import BeautifulSoup
from datetime import datetime
from django.db import transaction
from zds.tutorialv2.utils import get_content_from_json, BadManifestError
from zds.utils.templatetags.emarkdown import emarkdown
from zds.tutorialv2.models.models_versioned import Container, Extract

from zds.search.models import SearchIndexExtract, SearchIndexContainer, SearchIndexContent, \
    SearchIndexTag, SearchIndexAuthors


def get_file_content_in_zip(archive, path):
    """Get file content in a zip archive

    :param archive: a zip archive
    :type archive: zipfile.ZipFile
    :param path: path to the file
    :type path: str
    :return: content of the archive
    :raise KeyError: if the file is not in the archive
    """

    content = unicode(archive.read(path), 'utf-8')
    return content


def filter_keyword(html):
    """Try to find important words in an html string. Search in all i and strong and each title

    :return: list of important words
    """
    bs = BeautifulSoup(html)

    keywords = u''
    for tag in bs.findAll(['h1', 'h2', 'h3', 'i', 'strong']):
        keywords += u' ' + tag.text

    return keywords


def filter_text(html):
    """Filter word from the html version of the text

    :param html: The content which words must be extract
    :return: extracted words
    """
    bs = BeautifulSoup(html)
    return u' '.join(bs.findAll(text=True))


def index_extract(extract, search_index_content, archive):
    search_index_extract = SearchIndexExtract()
    search_index_extract.search_index_content = search_index_content
    search_index_extract.title = extract.title
    search_index_extract.url_to_redirect = extract.get_absolute_url_online()

    html = u''

    if extract.text:
        try:
            html = emarkdown(get_file_content_in_zip(archive, extract.text))
        except KeyError:
            pass

    if html:
        search_index_extract.extract_content = filter_text(html)
        search_index_extract.keywords = filter_keyword(html)

    search_index_extract.save()


def index_container(container, search_index_content, archive):

    search_index_container = SearchIndexContainer()
    search_index_container.search_index_content = search_index_content
    search_index_container.title = container.title
    search_index_container.url_to_redirect = container.get_absolute_url_online()

    # index introduction and conclusion:
    if container.introduction:
        try:
            introduction_html = emarkdown(get_file_content_in_zip(archive, container.introduction))
            all_html = introduction_html
            search_index_container.introduction = filter_text(introduction_html)
        except KeyError:
            pass

    if container.conclusion:
        try:
            conclusion_html = emarkdown(get_file_content_in_zip(archive, container.conclusion))
            all_html = u'{}{}'.format(all_html, conclusion_html)
            search_index_container.conclusion = filter_text(conclusion_html)
        except KeyError:
            pass

    if all_html != u'':
        search_index_container.keywords = filter_keyword(all_html)

    # index children:
    search_index_container.level = 'part'

    for child in container.children:
        if isinstance(child, Extract):
            search_index_container.level = 'chapter'  # only a chapter can contain extracts
            index_extract(child, search_index_content, archive)
        else:
            index_container(child, search_index_content, archive)

    search_index_container.save()


def index_content(versioned, search_index_content, archive):

    for child in versioned.children:
        if isinstance(child, Container):
            index_container(child, search_index_content, archive)
        else:
            index_extract(child, search_index_content, archive)


@transaction.atomic
def reindex_content(published_content):
    """Index the new published version. Lot of IO, memory and cpu will be used, be warned when you use this function.
    Only loop on this function if you know what you are doing !

    IO complexity is 2 + (2*number of containers) + number of extracts.
    Database query complexity is on deletion 1+number of containers+number of extracts,
                                 on addition 1+number of containers+number of extracts.

    :param published_content: Database representation of the public version of the content
    :type published_content: PublishedContent
    :return:
    """

    # We just delete all index that correspond to the content
    SearchIndexContent.objects.filter(publishable_content__pk=published_content.content_pk).delete()

    # Load the manifest:
    if not published_content.have_zip():
        raise Exception(
            'Unable to index content with id {} due to the absence of ZIP file'.format(published_content.content_pk))

    zip_path = os.path.join(
        published_content.get_extra_contents_directory(), published_content.content_public_slug + '.zip')

    archive = zipfile.ZipFile(zip_path)
    try:
        manifest = get_file_content_in_zip(archive, 'manifest.json')
    except KeyError:
        raise Exception(
            'Unable to index content with id {} due to the absence of manifest in ZIP file'
            .format(published_content.content_pk))

    json_ = json_reader.loads(manifest)
    try:
        versioned = get_content_from_json(json_, None, '')
    except BadManifestError as e:
        raise Exception(e.message)
    except Exception:
        raise Exception('Unable to index content with id {} due to an error while opening manifest'
                        .format(published_content.content_pk))

    published_content.content.insert_data_in_versioned(versioned)

    # Index the content:
    search_index_content = SearchIndexContent()
    search_index_content.publishable_content = published_content.content
    search_index_content.pubdate = published_content.publication_date or datetime.now()
    search_index_content.update_date = published_content.content.update_date or datetime.now()

    if published_content.content.licence:
        search_index_content.licence = published_content.content.licence.title
    else:
        search_index_content.licence = ''

    if published_content.content.image:
        search_index_content.url_image = published_content.content.image.get_absolute_url()
    else:
        search_index_content.url_image = ''

    search_index_content.title = versioned.title
    search_index_content.description = versioned.description

    search_index_content.save()

    # Subcategory
    for subcategory in published_content.content.subcategory.all():
        search_index_tag = SearchIndexTag()
        search_index_tag.title = subcategory.title
        search_index_tag.save()

        search_index_content.tags.add(search_index_tag)

    # Authors
    for author in published_content.content.authors.all():
        search_index_authors = SearchIndexAuthors()
        search_index_authors.username = author.username
        search_index_authors.save()

        search_index_content.authors.add(search_index_authors)

    search_index_content.url_to_redirect = published_content.get_absolute_url_online()

    # Save introduction and conclusion:
    all_html = u''

    if versioned.introduction:
        try:
            introduction_html = emarkdown(get_file_content_in_zip(archive, versioned.introduction))
            all_html = introduction_html
            search_index_content.introduction = filter_text(introduction_html)
        except KeyError:
            pass

    if versioned.conclusion:
        try:
            conclusion_html = emarkdown(get_file_content_in_zip(archive, versioned.conclusion))
            all_html = u'{}{}'.format(all_html, conclusion_html)
            search_index_content.conclusion = filter_text(conclusion_html)
        except KeyError:
            pass

    if all_html != u'':
        search_index_content.keywords = filter_keyword(all_html)

    search_index_content.type = published_content.content_type.lower()
    search_index_content.save()

    search_index_content.type = published_content.content_type.lower()
    search_index_content.save()

    # Also index children
    index_content(versioned, search_index_content, archive)

    # no need to index the next time
    published_content.content.must_reindex = False
    published_content.content.save()
