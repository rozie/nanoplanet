import argparse
import logging
import sys
from datetime import datetime, timezone

import bleach
import dateutil.parser
import feedparser
import requests
import yaml
from jinja2 import Template

logger = logging.getLogger(__name__)


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


def jinjarenderer(file, name, channels, items):
    with open(file, "r", encoding="utf8") as tfile:
        template = tfile.read()
    t = Template(template)
    res = t.render(name=name, Channels=channels, Items=items)
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
        with open(args.config, "r") as config:
            data = yaml.load(config, Loader=yaml.SafeLoader)
    except Exception as e:
        logger.error("Couldn't read config file %s", e)
    
    # read config data
    planetname = data.get('planet', {}).get('name')
    link = data.get('planet', {}).get('link')
    timeout = data.get('planet', {}).get('timeout')
    template_files = data.get('planet', {}).get('template_files')
    feeds = data.get('feeds')
    howmany = data.get('planet', {}).get('items_for_planet')

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
            logger.error("Exception occured on feed %s %s %s", name, feed, e)
    
    # sort all entries by date
    datetime_objects = [d for d in all_entries.keys()]
    sorted_datetime_objects = sorted(datetime_objects, reverse=True)

    # prepare entries to be rendered
    items = []
    for dobj in sorted_datetime_objects[:howmany]:
        items.append({
            'blogtitle': all_entries[dobj]['blogtitle'],
            'feedlink': all_entries[dobj]['feedlink'],
            'name': all_entries[dobj]['name'],
            'description': all_entries[dobj]['description'],
            'title': all_entries[dobj]['title'],
            'link': all_entries[dobj]['link']
        })

    # generate output files
    for file in template_files:
        filename = file.replace(".tmpl", "")
        content = jinjarenderer(file=file, name=planetname, channels=channels, items=items)

        with open (filename, "w", encoding="utf8") as f:
            f.write(content)

if __name__ == "__main__":
    main()
