import time
import types

from miro import feed
from miro import item
from miro import feedparserutil
from miro import dialogs
import framework
from miro import signals
from miro.plat import resources

class UnicodeFeedTestCase(framework.EventLoopTest):
    def setUp(self):
        super(UnicodeFeedTestCase, self).setUp()
        signals.system.connect('new-dialog', self.onNewDialog)
        self.choice = None
        self.num_dialogs = 0

    def onNewDialog(self, obj, dialog):
        self.assertNotEqual(self.choice, None)
        self.num_dialogs += 1
        # print "rundialog called from %s" % dialog.title
        dialog.choice = self.choice
        # a bit of a hack to avoid using eventloop
        dialog.callback(dialog)

    def make_feed(self, url):
        my_feed = feed.Feed(url)
        self.process_idles()
        return my_feed

    def force_feed_parser_callback(self, my_feed):
        # a hack to get the feed to update without eventloop
        feedimpl = my_feed.actualFeed
        feedimpl.feedparser_callback(
            feedparserutil.parse(feedimpl.initialHTML))

    def is_proper_feed_parser_dict(self, parsed, name="top"):
        if isinstance(parsed, types.DictionaryType):
            for (key, value) in parsed.items():
                self.is_proper_feed_parser_dict(value, key)
        elif (isinstance(parsed, types.ListType) or
              isinstance(parsed, types.TupleType)):
            for value in parsed:
                self.is_proper_feed_parser_dict(value, name)
        elif isinstance(parsed, types.StringType):
            self.assert_(name in ["base", "type", "encoding", "version",
                                  "href", "rel"])
        elif isinstance(parsed, time.struct_time):
            self.assert_(name in ["updated_parsed", "published_parsed"])
        elif isinstance(parsed, types.IntType):
            self.assert_(name in ["updated_parsed", "bozo"])
        else:
            self.assert_((isinstance(parsed, types.UnicodeType) or
                          isinstance(parsed, types.NoneType)))

    def test_valid_utf_feed(self):
        self.filename = self.make_temp_path(".xml")
        handle = open(self.filename, "wb")
        handle.write(u'''<?xml version="1.0"?>
<rss version="2.0">
   <channel>
 <title>Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\
\u516b\u4e5d</title>
      <description>Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\
\u4e03\u516b\u4e5d</description>
      <language>zh-zh</language>
     <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>
      <generator>Weblog Editor 2.0</generator>
      <managingEditor>editor@example.com</managingEditor>
      <webMaster>webmaster@example.com</webMaster>
      <item>

         <title>\u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\
</title>
     <link>http://participatoryculture.org/boguslink</link>
         <description>\u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\
\u4e5d</description>
        <enclosure url="file://crap" length="0" type="video/mpeg"/>
         <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>
      </item>
   </channel>
</rss>'''.encode('utf-8'))

        handle.close()

        my_feed = self.make_feed(u"file://" + self.filename)
        self.force_feed_parser_callback(my_feed)

        self.is_proper_feed_parser_dict(my_feed.actualFeed.parsed)

        # We need to explicitly check that the type is unicode because
        # Python automatically converts bytes strings to unicode
        # strings using the current system character set
        self.assertEqual(type(my_feed.get_title()), unicode)
        self.assertEqual(
            (u"Chinese Numbers \u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d"
             u"\u4e03\u516b\u4e5d"), my_feed.get_title())

        i = item.Item.make_view().get_singleton()
        self.assertEqual(type(i.get_title()), unicode)
        self.assertEqual(
            u"\u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d",
            i.get_title())

        self.assertEqual(type(i.get_description()), unicode)
        self.assertEqual(
            u"\u25cb\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d",
            i.get_description())

    # This is a latin1 feed that claims to be UTF-8
    def test_invalid_latin1_feed(self):
        self.filename = self.make_temp_path(".xml")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0"?>
<rss version="2.0">
   <channel>
      <title>H\xe4ppy Birthday</title>
      <description>H\xe4ppy Birthday</description>
 <language>zh-zh</language>
      <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>
      <generator>Weblog Editor 2.0</generator>
      <managingEditor>editor@example.com</managingEditor>
      <webMaster>webmaster@example.com</webMaster>
      <item>
         <title>H\xe4ppy Birthday</title>
         <link>http://participatoryculture.org/boguslink</link>
         <description>H\xe4ppy Birthday</description>
         <enclosure url="file://crap" length="0" type="video/mpeg"/>
         <pubDate>Fri, 25 Aug 2006 17:39:21 GMT</pubDate>
      </item>
   </channel>
</rss>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        my_feed.update()
        self.assertEqual(my_feed.items.count(), 1)
        my_item = list(my_feed.items)[0]
        self.assertEqual(len(my_item.get_title()), 14)
        self.assertEqual(my_item.get_title(), u"H\xe4ppy Birthday")

    # This is latin1 HTML that claims to be Latin 1
    def test_latin1_html(self):
        self.filename = self.make_temp_path(".html")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; \
charset=iso-8859-1" />
  <title>H\xe4ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov">H\xe4ppy Birthday</a>
   </body>
</html>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        self.assertEqual(self.num_dialogs, 1)
        my_feed.update()
        self.assertEqual(my_feed.items.count(), 1)
        my_item = list(my_feed.items)[0]
        self.assertEqual(len(my_item.get_title()), 14)
        self.assertEqual(my_item.get_title(), u"H\xe4ppy Birthday")

    # This is latin1 HTML that claims to be UTF-8
    def test_invalid_latin1_html(self):
        self.filename = self.make_temp_path(".html")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0" encoding="utf-8"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
      <title>H\xe4ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov">H\xe4ppy Birthday</a>
   </body>
</html>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        self.assertEqual(self.num_dialogs,1)
        my_feed.update()
        self.assertEqual(my_feed.items.count(),1)
        my_item = list(my_feed.items)[0]
        self.assertEqual(len(my_item.get_title()),14)
        self.assertEqual(my_item.get_title(), u"H\xe4ppy Birthday")

    # This is utf-8 HTML that claims to be utf-8
    def test_utf8_html(self):
        self.filename = self.make_temp_path(".html")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0" encoding="utf-8"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
      <title>H\xc3\xa4ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov">\
H\xc3\xa4ppy Birthday</a>
   </body>
</html>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        self.assertEqual(self.num_dialogs,1)
        my_feed.update()
        self.assertEqual(my_feed.items.count(),1)
        my_item = list(my_feed.items)[0]
        self.assertEqual(len(my_item.get_title()),14)
        self.assertEqual(my_item.get_title(), u"H\xe4ppy Birthday")

    def test_utf8_html_links(self):
        self.filename = self.make_temp_path(".html")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0" encoding="utf-8"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
      <title>H\xc3\xa4ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/H\xc3\xa4ppy.mov">\
H\xc3\xa4ppy Birthday</a>
   </body>
</html>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        self.assertEqual(self.num_dialogs, 1)
        my_feed.update()
        # Either the item isn't added or it's added with an ascii URL
        if my_feed.items.count() > 0:
            self.assertEqual(my_feed.items.count(), 1)
            my_item = list(my_feed.items)[0]
            my_url = my_item.get_url()
            self.assertEqual(str(my_url), my_url)

    def test_latin1_html_links(self):
        self.filename = self.make_temp_path(".html")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
 <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
   <title>H\xe4ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/H\xe4ppy.mov">\
H\xe4ppy Birthday</a>
   </body>
</html>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        self.assertEqual(self.num_dialogs, 1)
        my_feed.update()
        # Either the item isn't added or it's added with an ascii URL
        if my_feed.items.count() > 0:
            self.assertEqual(my_feed.items.count(), 1)
            my_item = list(my_feed.items)[0]
            my_url = my_item.get_url()
            self.assertEqual(str(my_url), my_url)

    def test_invalid_latin1_html_links(self):
        self.filename = self.make_temp_path(".html")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; \
charset=iso-8859-1" />
      <title>H\xc3\xa4ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/H\xc3\xa4ppy.mov">\
H\xc3\xa4ppy Birthday</a>
   </body>
</html>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        self.assertEqual(self.num_dialogs, 1)
        my_feed.update()
        # Either the item isn't added or it's added with an ascii URL
        if my_feed.items.count() > 0:
            self.assertEqual(my_feed.items.count(), 1)
            my_item = list(my_feed.items)[0]
            my_url = my_item.get_url()
            self.assertEqual(str(my_url), my_url)

    def test_utf8_html_thumbs(self):
        self.filename = self.make_temp_path(".html")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0" encoding="utf-8"?>
<html>
   <head>
 <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
      <title>H\xc3\xa4ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov">\
<img src="http://www.wccatv.com/files/video/H\xc3\xa4ppy.png"/>\
H\xc3\xa4ppy Birthday</a>
   </body>
</html>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        self.assertEqual(self.num_dialogs, 1)
        my_feed.update()

        self.assertEqual(my_feed.items.count(), 1)
        my_item = list(my_feed.items)[0]
        my_url = my_item.get_url()
        self.assertEqual(str(my_url), my_url)

        thumb = my_item.get_thumbnail_url()
        if thumb is not None:
            self.assertEqual(str(thumb), thumb)

    def test_latin1_html_thumbs(self):
        self.filename = self.make_temp_path(".html")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
  <meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
    <title>H\xe4ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov">\
<img src="http://www.wccatv.com/files/video/H\xe4ppy.png"/>\
H\xe4ppy Birthday</a>
   </body>
</html>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        self.assertEqual(self.num_dialogs, 1)
        my_feed.update()

        self.assertEqual(my_feed.items.count(), 1)
        my_item = list(my_feed.items)[0]
        my_url = my_item.get_url()
        self.assertEqual(str(my_url), my_url)

        thumb = my_item.get_thumbnail_url()
        if thumb is not None:
            self.assertEqual(str(thumb), thumb)

    def test_invalid_latin1_html_thumbs(self):
        self.filename = self.make_temp_path(".html")
        handle = open(self.filename, "wb")
        handle.write('''<?xml version="1.0" encoding="iso-8859-1"?>
<html>
   <head>
       <meta http-equiv="Content-Type" content="text/html; \
charset=iso-8859-1" />
 <title>H\xc3\xa4ppy Birthday</title>
   </head>
   <body>
   <a href="http://www.wccatv.com/files/video/hbml.mov">\
<img src="http://www.wccatv.com/files/video/H\xc3\xa4ppy.png"/>\
H\xc3\xa4ppy Birthday</a>
   </body>
</html>''')
        handle.close()

        self.choice = dialogs.BUTTON_YES

        my_feed = self.make_feed(u"file://" + self.filename)

        self.assertEqual(self.num_dialogs, 1)
        my_feed.update()

        self.assertEqual(my_feed.items.count(), 1)
        my_item = list(my_feed.items)[0]
        my_url = my_item.get_url()
        self.assertEqual(str(my_url), my_url)

        thumb = my_item.get_thumbnail_url()
        if thumb is not None:
            self.assertEqual(str(thumb), thumb)

    def test_democracy_now_bug(self):
        url = resources.url("testdata/democracy-now-unicode-bug.xml")
        my_feed = self.make_feed(url)
        self.force_feed_parser_callback(my_feed)
        for item in my_feed.items:
            u'booya' in item.get_title().lower()
