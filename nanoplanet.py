import argparse
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import bleach
import dateutil.parser
import feedparser
import requests
import yaml
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from jinja2 import Template

logger = logging.getLogger(__name__)


def generate_feed(planetname, planetlink, items, lang="en", description="Feed",
                  feed_type="rss", filename="feed.xml"):
    """
    Generate an RSS or Atom feed from items list.
    feed_type: "rss" or "atom"
    """
    fg = FeedGenerator()
    fg.title(planetname)
    fg.link(href=planetlink, rel='alternate')
    fg.link(href=planetlink+filename, rel='self')
    fg.description(description)
    fg.language(lang)
    fg.id(planetlink)
    fg.updated(datetime.now(timezone.utc))

    for entry in items:
        fe = fg.add_entry()
        fe.title(entry['title'])
        fe.link(href=entry['link'])
        fe.description(entry['description'])
        fe.author(name=entry['name'])
        fe.id(entry['link'])

        if 'pubdate' in entry:
            fe.published(dateutil.parser.parse(entry['pubdate']))
            fe.updated(dateutil.parser.parse(entry['pubdate']))
        else:
            fe.updated(datetime.now(timezone.utc))

        fe.pubDate(dateutil.parser.parse(entry['pubdate']))

    if feed_type == "rss":
        fg.rss_file(filename)
    elif feed_type == "atom":
        fg.atom_file(filename)
    else:
        raise ValueError("Unsupported feed_type. Use 'rss' or 'atom'.")


def download_rss(url, timeout):
    """Download RSS feed from the given URL."""
    response = requests.get(url=url, timeout=timeout)
    response.raise_for_status()
    return response.content


def sanitize_content(content):
    """Sanitize the content using bleach."""
    allowed_tags = list(bleach.sanitizer.ALLOWED_TAGS) + ['h1', 'h2', 'h3', 'p', 'ul', 'ol', 'li', 'strong', 'em', 'cite', 'code', 'span', 'u', 'b', 'i' ]
    allowed_attributes = bleach.sanitizer.ALLOWED_ATTRIBUTES
    sanitized_content = bleach.clean(content, tags=allowed_tags, attributes=allowed_attributes, strip=True)
    return sanitized_content


def expand_urls(content, base_url):
    soup = BeautifulSoup(content, 'html.parser')
    for anchor in soup.find_all('a'):
        if 'href' in anchor.attrs:
            href = anchor['href']
            if href.startswith('/'):
                absolute_url = urljoin(base_url, href)
                anchor['href'] = absolute_url
    return str(soup)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Microplanet - very simple planet generator')
    parser.add_argument(
        '-v', '--verbose', required=False,
        default=False, action='store_true',
        help="Provide verbose output")
    parser.add_argument(
        '-c', '--config', required=False,
        default="planetconfig.yaml",
        help="Configuration file"
    )
    args = parser.parse_args()
    return args


def jinjarenderer(file, name, channels, items, date):
    with open(file, "r", encoding="utf8") as tfile:
        template = tfile.read()
    t = Template(template)
    res = t.render(name=name, Channels=channels, Items=items, date=date)
    return res


def main():
    args = parse_arguments()

   # set verbosity
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # load config file
    try:
        with open(args.config, "r", encoding="utf-8") as config:
            data = yaml.load(config, Loader=yaml.SafeLoader)
    except Exception as e:
        logger.error("Couldn't read config file %s", e)

    # read config data
    planetname = data.get('planet', {}).get('name')
    planetlink = data.get('planet', {}).get('link')
    timeout = data.get('planet', {}).get('timeout')
    template_files = data.get('planet', {}).get('template_files')
    feeds = data.get('feeds')
    howmany = data.get('planet', {}).get('items_for_planet')
    rss_filename = data.get('planet', {}).get('rss_filename')
    feed_lang = data.get('planet', {}).get('feed_lang', 'en')
    feed_description = data.get('planet', {}).get('feed_description', 'Feed')

    all_entries = {}
    channels = []

    # process (read) all feeds
    for feed in feeds:
        name = data.get('feeds',{}).get(feed).get('name')
        rss_url = feed
        try:
            logger.debug("Fetching feed %s", rss_url)
            rss_data = download_rss(rss_url, timeout)
            feed = feedparser.parse(rss_data)
            channels.append({'name': name, 'title':feed.feed.title, 'link':feed.feed.link})
            for entry in feed.entries:
                try:
                    title = sanitize_content(entry.title)
                    link = sanitize_content(entry.link)
                    datepub = sanitize_content(entry.published)
                    description = sanitize_content(entry.description)
                    pubdate = dateutil.parser.parse(datepub).astimezone(timezone.utc)
                    all_entries[pubdate] = {}
                    all_entries[pubdate]['title'] = title
                    all_entries[pubdate]['link'] = link
                    all_entries[pubdate]['description'] = description
                    all_entries[pubdate]['name'] = name
                    all_entries[pubdate]['blogtitle'] = sanitize_content(feed.feed.title)
                    all_entries[pubdate]['feedlink'] = sanitize_content(feed.feed.link)
                except Exception as e:
                    logger.error("Error in entry: %s", entry)
                    logger.error("Exception occured on feed %s %s %s", name, feed, e)
        except Exception as e:
            logger.error("Exception occured on feed %s %s %s", name, feed, e)

    # sort all entries by date
    datetime_objects = list(all_entries.keys())
    sorted_datetime_objects = sorted(datetime_objects, reverse=True)

    # prepare entries to be rendered
    items = []
    for dobj in sorted_datetime_objects[:howmany]:
        link = all_entries[dobj]['link']
        modified_description = expand_urls(content=all_entries[dobj]['description'], base_url=link)
        items.append({
            'blogtitle': all_entries[dobj]['blogtitle'],
            'feedlink': all_entries[dobj]['feedlink'],
            'name': all_entries[dobj]['name'],
            'description': modified_description,
            'title': all_entries[dobj]['title'],
            'link': link,
            'pubdate': dobj.isoformat()
        })

    # generate output files
    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for file in template_files:
        filename = file.replace(".tmpl", "")
        content = jinjarenderer(file=file, name=planetname, channels=channels, items=items, date=date)

        with open (filename, "w", encoding="utf8") as f:
            f.write(content)

    # generate feed files
    if rss_filename:
        generate_feed(planetname=planetname, planetlink=planetlink, items=items, lang=feed_lang,
                      feed_type="rss", filename=rss_filename, description=feed_description)

if __name__ == "__main__":
    main()
