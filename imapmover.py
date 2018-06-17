#!/usr/bin/python

from pprint import pprint

import os
import sys
import yaml
import imaplib
import email
import email.header

class MailSession:

    session = None

    def __init__(self, account):
        self.session = imaplib.IMAP4_SSL(account['host'])
        self.session.login(account['user'], account['pass'])

    def read_folder(self, folder_name = 'INBOX'):
        #pprint(self.session.list())  # ..rv, folders
        self.session.select(folder_name)
        rv, msgids = self.session.search(None, 'ALL')
        return msgids[0].split()  #..string containing numeric ids => return as array

    def try_rule(self, msgid, rule):
        """
        Try to match message against rule.
        On success, move message to IMAP folder selected by rule, and return True.
        Otherwise return False.
        """

        print("msgid = %s, name = %s, rule = %s, dest = %s"
                % ( msgid, rule['name'], rule['match_rule'], rule['dest_folder'] ))
        # ???
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

        self.mail_accounts = self.read_section(cfgfile, cfg, 'mail_accounts', ['host','user','pass'      ])
        self.filter_rules  = self.read_section(cfgfile, cfg, 'filter_rules' , ['match_rule','dest_folder'])

    def run(self):

        for account in self.mail_accounts:
            session = MailSession(account)
            msgids = session.read_folder()
            for msgid in msgids:
                for rule in self.filter_rules:
                    if session.try_rule(msgid, rule):
                        break  #..skip remaining rules

def main():
    mover = ImapMover()
    fname = sys.argv[1] if len(sys.argv) > 1 else os.path.splitext(os.path.basename(sys.argv[0]))[0] + '.yml'
    mover.read_config(fname)
    mover.run()

if __name__ == "__main__":
    main()

## END ##
