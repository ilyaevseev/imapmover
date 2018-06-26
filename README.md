# ImapMover

* Read INBOX messages from IMAP mailbox
* Check message content against filter rules
* Move matching message to selected folder

### Configuration file:

* When command line is empty, "imapmover.yml" is readed from the current folder
* Otherwise filename is taken from command line

## Configuration format:

* See example in [imapmover.yml](imapmover.yml)
* See also [Complete idiot's introduction to yaml](https://github.com/Animosity/CraftIRC/wiki/Complete-idiot's-introduction-to-yaml)
* Required sections: mail_accounts and filter_rules (both should contain at least one record)
* Required fields:
  * for mail accounts: host,user,pass
  * for filters: match_rule, dest_folder

### Thanks:

* https://gist.github.com/robulouski/7441883
* https://eax.me/python-imap/
* https://docs.python.org/2/library/imaplib.html
* https://islascruz.org/blog/2017/01/27/attachments-python-imap/
* http://code.activestate.com/recipes/302086-strip-attachments-from-an-email-message/
* StackOverflow :-)
