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

    def __init__(self, account_name, account):
        pprint(account)
        self.session = imaplib.IMAP4_SSL(account['host'])
        rv, data = self.session.login(account['user'], account['pass'])
        pprint(rv)
        pprint(data)
        return

    def read_folder(folder_name = None):
        return

    def move_msg(msg, dest_folder):
        return

class ImapMover:

    mail_accounts = []
    filter_rules  = []

    def read_section(self, cfgfile, cfg, section_name, required_fields):

        if not section_name in cfg:
            raise ValueError("missing \"%s\" in %s" % ( section_name, cfgfile ))

        data = cfg[section_name]

        if not data:
            raise ValueError("empty \"%s\" in %s" % ( section_name, cfgfile ))

        records = data.items()

        for record_name, record in records:
            for field in required_fields:
                if not field in record:
                    raise ValueError( "missing \"%s\" in record \"%s\" in section \"%s\" in %s"
                                  % ( field, record_name, section_name, cfgfile ))

        return records

    def read_config(self, cfgfile):

        fd = open(cfgfile, 'r')
        cfg = yaml.load(fd)

        self.mail_accounts = self.read_section(cfgfile, cfg, 'mail_accounts', ['host','user','pass'      ])
        self.filter_rules  = self.read_section(cfgfile, cfg, 'filter_rules' , ['match_rule','dest_folder'])

    def match_rule(self, msg, rule):

        # ???
        return

    def run(self):

        for account_name, account in self.mail_accounts:
            session = MailSession(account_name, account)
            return
            msgs = session.read_folder()
            for msg in msgs:
                for rule_name, rule in self.filter_rules:
                    if self.match_rule(msg, rule):
                        session.move_msg(msg, rule.dest_folder)

def main():
    mover = ImapMover()
    fname = sys.argv[1] if len(sys.argv) > 1 else os.path.splitext(os.path.basename(sys.argv[0]))[0] + '.yml'
    mover.read_config(fname)
    mover.run()

if __name__ == "__main__":
    main()

## END ##
