#!/usr/bin/python

from pprint import pprint

import re
import os
import sys
import errno
import time

# Parse configuration file:
import yaml

# Read emails from IMAP mailbox:
import imaplib
import email
import email.header
import email.utils

# Store parsed emails to Dropbox:
import dropbox
from dropbox.exceptions import ApiError


class Log:

    __level = -1

    @staticmethod
    def init_loglevel():
        if Log.__level >= 0: return
        Log.__level = 0
        if not 'VERBOSE' in os.environ: return
        val = os.environ['VERBOSE']
        if not val.isdigit(): return
        Log.__level = val

    @staticmethod
    def verbose(level, msg):
        Log.init_loglevel()
        if level > Log.__level: return
        print("<%d> %s" % (level, msg))

class Destination:
    """Abstract base class"""

    topdir = '.'

    def path2full(self, path):
        p = path[1:] if path[0] == os.sep else path
        return os.path.join(self.topdir, p)

class LocalDestination(Destination):

    def __init__(self, args = None, hint = None):
        topdir = args['top'] if (args and ('top' in args)) else '.'
        self.topdir = os.getcwd() if (not topdir or topdir == '.') else topdir

    def mkdir(self, dirpath):
        p = self.path2full(dirpath)
        try:
            os.makedirs(p)
            Log.verbose(2, "Created local directory: " + p)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
            Log.verbose(6, "Local directory already exist: " + p)

    def putfile(self, filepath, data):

        p = self.path2full(filepath)

        if os.path.exists(p):
            Log.verbose(1, "Local file already exist, skipped: " + filepath)
            return False

        Log.verbose(2, "Write local file: " + p)
        f = open(p, 'wb')
        f.write(data)
        f.close
        return True

class DropboxDestination(Destination):

    token = None
    dbx   = None

    def __init__(self, args, hint):

        topdir = args['top'] if (args and ('top' in args)) else '/'
        self.topdir = '/' if (not topdir or topdir == '.') else topdir

        if not args or not 'token' in args:
            raise LookupError("missing \"token\" field for dropbox destination")

        Log.verbose(2, "Connect to dropbox")
        self.dbx = dropbox.Dropbox(args['token'])
        Log.verbose(6, "Connect to dropbox: success")

    def mkdir(self, dirpath):

        p = self.path2full(dirpath)
        try:
            self.dbx.files_create_folder(p)
            Log.verbose(2, "Dropbox folder created: " + p)
        except ApiError as e:
            Log.verbose(2, "Cannot create dropbox folder, may be already exist: " + p)
            #pprint(e)

    def putfile(self, filepath, data):

        p = self.path2full(filepath)
        try:
            Log.verbose(2, "Write file to dropbox: " + p)
            self.dbx.files_upload(data, p)
            return True
        except ApiError as e:
            Log.verbose(2, "Cannot create dropbox file: " + p)
            return False

class MailSession:

    session = None
    MASKLEN = 5

    def __init__(self, account):
        Log.verbose(2, "Connect to IMAP server: " + account['host'])
        self.session = imaplib.IMAP4_SSL(account['host'])
        self.session.login(account['user'], account['pass'])
        Log.verbose(6, "Connect to IMAP server: success")

    def read_folder(self, folder_name = 'INBOX'):

        Log.verbose(4, "Select IMAP folder: " + folder_name)
        #pprint(self.session.list())  # ..rv, folders
        self.session.select(folder_name)

        Log.verbose(6, "Search unseen messages")
        rv, msgids = self.session.search(None, '(UNSEEN)')
        msgids = msgids[0].split()  #..string containing numeric ids => return as array
        msgs = []

        Log.verbose(2, "Fetch %d message headers" % (len(msgids)))
        for msgid in msgids:
            Log.verbose(5, "Fetch message header: " + str(msgid))
            rv,data = self.session.fetch(msgid, '(RFC822)')
            txt = data[0][1]
            msg = email.message_from_bytes(txt) if callable(getattr(email,"message_from_bytes", None)) else email.message_from_string(txt)
            msg.__setitem__('__MSGID__', msgid)
            msgs.append(msg);

        Log.verbose(4, "Fetch message headers: done")
        return msgs

    def email_addr_match(self, actual, needed):

        return (actual == needed) or re.search('<' + needed + '>', actual, re.I)

    def attachment_match(self, msgpart, suffix, mask):

        typ = msgpart.get_content_maintype()
        if typ != 'application' and not re.search('^application/', typ, re.I):
            return False

        fname = msgpart.get_filename()
        if not fname:
            return False

        if not re.search('.' + suffix + '$', fname, flags = re.IGNORECASE):
            return False

        if isinstance(mask, str):  # ..can be str or int
            return re.search(mask, fname, re.IGNORECASE)

        if isinstance(mask, int):
            return len(fname) >= (mask + self.MASKLEN - 1)

        return False

    def any_attachment_match(self, msg, suffix, mask):

        for part in msg.walk():
            if self.attachment_match(part, suffix, mask):
                return True  # ..found

        return False  # ..not found

    def build_filename_suffix(self, msgpart):

        t = msgpart.get_content_type()
        if t == 'text/plain' : return 'txt'
        if t == 'text/html'  : return 'html'
        return 'bin'

    def build_dirname(self, msgsubj, mask):

        if isinstance(mask,str):
            return mask
        if isinstance(mask,int):
            if mask <= 0: mask = 0
            return msgsubj[mask - 1 : mask + self.MASKLEN - 1]

    def build_timestamp(self, datetimestr, format = '%Y-%m-%d-%H%M%S'):

        parsed = email.utils.parsedate(datetimestr)
        return time.strftime(format, parsed) if parsed else time.strftime(format)

    def get_destination(self, rule, destinations):

        if not 'destination' in rule:
            Log.verbose(6, "Use local destination")
            return LocalDestination()

        destname = rule['destination']

        if not destinations:
            raise LookupError("rule uses destination %s, but no destinations defined" % (destname))

        if not destname in destinations:
            raise LookupError("rule uses unknown destination \"%s\"" % (destname))

        Log.verbose(6, "Use destination: " + destname)
        return destinations[destname]

    def try_rule(self, msg, rule, destinations):
        """
        Try to match message against rule.
        On success, move message to IMAP folder selected by rule, and return True.
        Otherwise return False.
        """

        if not self.email_addr_match(msg['From'], rule['from']):
            return False

        if 'mask' in rule:
            if not self.any_attachment_match(msg, rule['suffix'], rule['mask']):
                return False

        msgid = msg['__MSGID__']

        Log.verbose(1, "Fetch message %s: \"%s\" from \"%s\" by rule \"%s\"" %
                      ( msgid,
                        msg['Subject'] if msg['Subject'] else 'NOSUBJ',
                        msg['From'   ] if msg['From'   ] else 'NOFROM',
                        rule['name'] ) )

        msgdir = rule['dest_folder'] if 'dest_folder' in rule else self.build_dirname(msg['Subject'], rule['mask'])

        dest = self.get_destination(rule, destinations)
        dest.mkdir(msgdir)

        n = 0
        for part in msg.walk():

            data = part.get_payload(decode=True)
            if not data:   # ..skip multipart/mixed or multipart/alternative
                continue

            filename = part.get_filename()
            if not filename:
                n = n + 1
                filename = "part%d.%s" % ( n, self.build_filename_suffix(part) )
            filename = '%s__%s' % ( self.build_timestamp(msg['Date']), filename )

            dest.putfile(os.path.join(msgdir, filename), data)

        Log.verbose(3, "Set flag to message: " + msgid)
        self.session.store(msgid, '+FLAGS', '\\Flagged')

        return True

class ImapMover:

    mail_accounts = []
    filter_rules  = []
    destinations  = []

    def read_section(self, cfgfile, cfg, section_name, required_fields):

        if not section_name in cfg:
            raise LookupError("missing \"%s\" in %s" % ( section_name, cfgfile ))

        records = cfg[section_name]

        if not records:
            raise LookupError("empty \"%s\" in %s" % ( section_name, cfgfile ))

        if not isinstance(records, dict):
            raise TypeError("wrong section \"%s\" in \"%s\""
                              % ( section_name, cfgfile ))

        result = []

        for record_name in sorted(records):

            record = records[record_name]

            if not isinstance(record, dict):
                raise TypeError("wrong record \"%s\" in section \"%s\" in \"%s\""
                                  % ( record_name, section_name, cfgfile ))

            for field in required_fields:
                if not field in record:
                    raise LookupError( "missing \"%s\" in record \"%s\" in section \"%s\" in %s"
                                  % ( field, record_name, section_name, cfgfile ))

            record['name'] = record_name
            result.append(record)

        return result

    def read_filter_rules(self, cfgfile, cfg):

        rules = self.read_section(cfgfile, cfg, 'filter_rules' , ['from','suffix'])
        for rule in rules:
            if not 'mask' in rule and not 'dest_folder' in rule:
                raise LookupError("missing \"dest_folder\" or \"mask\" in rule \"%s\" in \"%s\"" %
                                   (rule['name'], cfgfile))
        return rules

    def read_destinations(self, cfgfile, cfg):

        secname = 'destinations'
        if not secname in cfg:
            return False

        destinations = cfg[secname]
        if not isinstance(destinations, dict):
            raise TypeError("wrong section \"%s\" in \"%s\"" % ( secname, cfgfile ))

        result = {}

        for destname in destinations:

            dest = destinations[destname]
            hint = "\"%s\" in \"%s\" in \"%s\"" % ( destname, secname, cfgfile )

            if not isinstance(dest, dict):
                raise TypeError("wrong section " + hint)
            if not 'type' in dest:
                raise LookupError("missing type in " + hint)

            typ = dest['type']
            if typ == 'local':
                result[destname] = LocalDestination(dest, hint)
            elif typ == 'dropbox':
                result[destname] = DropboxDestination(dest, hint)
            else:
                raise ValueError("invalid type \"%s\" in %s" % (typ, hint))

        return result

    def read_config(self, cfgfile):

        Log.verbose(2, "Read config: " + cfgfile)
        fd = open(cfgfile, 'r')
        cfg = yaml.load(fd)

        self.mail_accounts = self.read_section(cfgfile, cfg, 'mail_accounts', ['host','user','pass'])
        self.filter_rules  = self.read_filter_rules(cfgfile, cfg)
        self.destinations  = self.read_destinations(cfgfile, cfg)
        Log.verbose(6, "Read config: done")

    def run(self):

        for account in self.mail_accounts:
            session = MailSession(account)
            msgs = session.read_folder()
            for msg in msgs:
                for rule in self.filter_rules:
                    if session.try_rule(msg, rule, self.destinations):
                        break  #..skip remaining rules

def main():
    mover = ImapMover()
    fname = sys.argv[1] if len(sys.argv) > 1 else os.path.splitext(os.path.basename(sys.argv[0]))[0] + '.yml'
    mover.read_config(fname)
    mover.run()
    Log.verbose(1, "Done.")

if __name__ == "__main__":
    main()

## END ##
