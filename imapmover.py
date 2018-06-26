#!/usr/bin/python

from pprint import pprint

import re
import os
import sys
import time
import yaml
import imaplib
import email
import email.header
import email.utils

class MailSession:

    session = None
    MASKLEN = 5

    def __init__(self, account):
        self.session = imaplib.IMAP4_SSL(account['host'])
        self.session.login(account['user'], account['pass'])

    def read_folder(self, folder_name = 'INBOX'):
        #pprint(self.session.list())  # ..rv, folders
        self.session.select(folder_name)

        rv, msgids = self.session.search(None, '(UNSEEN)')
        msgids = msgids[0].split()  #..string containing numeric ids => return as array
        msgs = []

        for msgid in msgids:
            rv,data = self.session.fetch(msgid, '(RFC822)')
            txt = data[0][1]
            msg = email.message_from_string(txt)
            msg.__setitem__('__MSGID__', msgid)
            msgs.append(msg);

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

    def try_rule(self, msg, rule):
        """
        Try to match message against rule.
        On success, move message to IMAP folder selected by rule, and return True.
        Otherwise return False.
        """

        if not self.email_addr_match(msg['From'], rule['from']):
            return False

        if not self.any_attachment_match(msg, rule['suffix'], rule['mask']):
            return False

        print '%s - %s => %s' % ( msg['From'], msg['Subject'], rule['name'] )

        msgdir = rule['destdir'] if 'destdir' in rule else self.build_dirname(msg['Subject'], rule['mask'])
        try:
            os.makedirs(msgdir)
        except OSError as e:
            if e.errno != errno.EEXIST: raise

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

            filepath = os.path.join(msgdir, filename)
            if os.path.exists(filepath):
                continue
            try:
                f = open(filepath, 'w')
                f.write(data)
                f.close
            except OSError as e:
                print(e)

        self.session.store(msg['__MSGID__'], '+FLAGS', '\\Flagged')

        return True

class ImapMover:

    mail_accounts = []
    filter_rules  = []

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

    def read_config(self, cfgfile):

        fd = open(cfgfile, 'r')
        cfg = yaml.load(fd)

        self.mail_accounts = self.read_section(cfgfile, cfg, 'mail_accounts', ['host','user','pass'])
        self.filter_rules  = self.read_section(cfgfile, cfg, 'filter_rules' , ['from','suffix','mask','dest_folder'])

    def run(self):

        for account in self.mail_accounts:
            session = MailSession(account)
            msgs = session.read_folder()
            for msg in msgs:
                for rule in self.filter_rules:
                    if session.try_rule(msg, rule):
                        break  #..skip remaining rules

def main():
    mover = ImapMover()
    fname = sys.argv[1] if len(sys.argv) > 1 else os.path.splitext(os.path.basename(sys.argv[0]))[0] + '.yml'
    mover.read_config(fname)
    mover.run()

if __name__ == "__main__":
    main()

## END ##
